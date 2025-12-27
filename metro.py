#!/usr/bin/env python3
"""
Metro Lisboa Elevator Status CLI

Usage:
    ./metro.py update          - Fetch and save elevator data
    ./metro.py show <station>  - Show elevators for a station
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ENDPOINT = "https://www.metrolisboa.pt/wp-admin/admin-ajax.php?action=estado_linha_ajax_2022_nova_action"
DATA_FILE = Path(__file__).parent / "elevadores.json"
GITHUB_URL = "https://github.com/indeyets/lisboa-metro-elevadores"

LINES = {
    "amarela": "Linha Amarela",
    "azul": "Linha Azul",
    "verde": "Linha Verde",
    "vermelha": "Linha Vermelha",
}

# Regex patterns for parsing
LINE_PATTERN = re.compile(
    r'<div id="estadolinha(\w+)"[^>]*class="modal"[^>]*>(.*?)</div>\s*</div>\s*</div>\s*<div id="estadolinha',
    re.DOTALL,
)
LINE_PATTERN_LAST = re.compile(
    r'<div id="estadolinha(\w+)"[^>]*class="modal"[^>]*>(.*?)$', re.DOTALL
)
STATION_PATTERN = re.compile(
    r'<div class="accordionElev__title">(.*?)</div>\s*</div>\s*<div class="accordionElev__content-wrap">',
    re.DOTALL,
)
STATION_NAME_PATTERN = re.compile(r"<div[^>]*>([^<]+)</div>")
TABLE_ROW_PATTERN = re.compile(
    r"<tr[^>]*style='background-color:white'[^>]*>(.*?)</tr>", re.DOTALL
)
TD_PATTERN = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)


def fetch_data():
    """Fetch HTML from Metro Lisboa endpoint."""
    req = urllib.request.Request(
        ENDPOINT, headers={"User-Agent": "MetroElevadores/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def clean_html(text):
    """Remove HTML tags and clean whitespace."""
    text = re.sub(r"<br\s*/?>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_html(html):
    """Parse HTML and extract elevator data using regex."""
    data = {"lines": {}}

    # Find each line section
    for line_id in LINES:
        pattern = re.compile(
            rf'<div id="estadolinha{line_id}"[^>]*>(.*?)(?=<div id="estadolinha|<div id="outMobile"|$)',
            re.DOTALL,
        )
        match = pattern.search(html)
        if not match:
            continue

        line_html = match.group(1)
        data["lines"][line_id] = {"name": LINES[line_id], "stations": {}}

        # Split by accordion items
        accordion_parts = re.split(r'<div class="accordionElev">', line_html)

        for part in accordion_parts[1:]:  # Skip first empty part
            # Extract station name from title
            title_match = re.search(
                r'<div class="accordionElev__title">.*?<div[^>]*>([^<]+)</div>',
                part,
                re.DOTALL,
            )
            if not title_match:
                continue
            station_name = title_match.group(1).strip()
            station_key = station_name.lower()

            # Find table rows with elevator data
            elevators = []
            for row_match in TABLE_ROW_PATTERN.finditer(part):
                row_html = row_match.group(1)
                cells = TD_PATTERN.findall(row_html)

                if len(cells) >= 4:
                    # cells[2] = location, cells[3] = status
                    location = clean_html(cells[2])
                    status_text = clean_html(cells[3]).lower()

                    if "operacional" in status_text:
                        status = "operational"
                    elif "serviço" in status_text or "servico" in status_text:
                        status = "out_of_service"
                    else:
                        continue

                    elevators.append({"location": location, "status": status})

            if elevators:
                data["lines"][line_id]["stations"][station_key] = {
                    "name": station_name,
                    "elevators": elevators,
                }

    return data


def cmd_update():
    """Fetch data and save to JSON file."""
    print("Fetching data from Metro Lisboa...")

    try:
        html = fetch_data()
    except Exception as e:
        print(f"Error fetching data: {e}", file=sys.stderr)
        return 1

    print("Parsing HTML...")
    try:
        data = parse_html(html)
    except Exception as e:
        print(
            f"Error: Failed to parse elevator data: {e}",
            file=sys.stderr,
        )
        print(
            "The website structure may have changed.",
            file=sys.stderr,
        )
        print(
            f"Please report this issue at: {GITHUB_URL}",
            file=sys.stderr,
        )
        return 1

    # Count statistics
    total = 0
    out_of_service = 0
    for line in data["lines"].values():
        for station in line["stations"].values():
            for elev in station["elevators"]:
                total += 1
                if elev["status"] == "out_of_service":
                    out_of_service += 1

    # Validate parsed data
    if total == 0:
        print(
            "Error: Failed to parse elevator data from Metro Lisboa website.",
            file=sys.stderr,
        )
        print(
            "The website structure may have changed.",
            file=sys.stderr,
        )
        print(
            f"Please report this issue at: {GITHUB_URL}",
            file=sys.stderr,
        )
        return 1

    data["updated_at"] = datetime.now().isoformat()

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Saved to {DATA_FILE}")
    print(f"Total elevators: {total}, out of service: {out_of_service}")
    return 0


def cmd_show(station_query):
    """Show elevator status for a station."""
    if not DATA_FILE.exists():
        print("No data file. Run 'update' first.", file=sys.stderr)
        return 1

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    query = station_query.lower()

    # Group by station name to handle interchange stations
    stations_by_name = {}
    for line_id, line in data["lines"].items():
        for station_key, station in line["stations"].items():
            if query in station_key or query in station["name"].lower():
                name = station["name"]
                if name not in stations_by_name:
                    stations_by_name[name] = {
                        "lines": [],
                        "elevators": station["elevators"],
                    }
                stations_by_name[name]["lines"].append(line["name"])

    if not stations_by_name:
        print(f"Station '{station_query}' not found.", file=sys.stderr)
        return 1

    for name, info in stations_by_name.items():
        lines_str = " / ".join(info["lines"])
        print(f"\n{name} ({lines_str})")
        print("-" * 40)

        for elev in info["elevators"]:
            status = "OK" if elev["status"] == "operational" else "OUT OF SERVICE"
            marker = "  " if elev["status"] == "operational" else "X "
            print(f"  {marker} {elev['location']}: {status}")

    # Show last update time
    if "updated_at" in data:
        print(f"\nLast updated: {data['updated_at']}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Metro Lisboa Elevator Status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # update command
    subparsers.add_parser("update", help="Fetch and save elevator data")

    # show command
    show_parser = subparsers.add_parser("show", help="Show elevators for a station")
    show_parser.add_argument("station", nargs="+", help="Station name")

    args = parser.parse_args()

    if args.command == "update":
        return cmd_update()
    elif args.command == "show":
        station = " ".join(args.station)
        return cmd_show(station)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
