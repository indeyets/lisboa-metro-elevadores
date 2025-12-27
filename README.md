# Lisbon Metro elevator-status CLI

Metropolitano de Lisboa provides information about the status of elevators in
its stations since 2025, but only as a page on its website. This command-line
tool provides a way to do the same in much more accessible way.

No dependencies needed. Implemented in standard Python3 library.

```
Usage:
    ./metro.py update          - Fetch and save elevator data
    ./metro.py show <station>  - Show elevators for a station
```

Example:

```sh
./metro.py show Picoas

Picoas (Linha Amarela)
----------------------------------------
     Elevador Cais sentido Rato/Átrio: OK
     Elevador Cais sentido Odivelas/Átrio: OK
     Elevador Átrio/Superfície(Av. Fontes P. Melo/R. Tomás Ribeiro): OK
```
