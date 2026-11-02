# Sample exercises, one per user story. Nothing here is part of the
# verification system: it is the code the acceptance criteria are written
# against while the vocabulary is being tried out.
#
#   python3 esercizi.py sort 3 1 2
#   python3 esercizi.py divide 10 2
#   python3 esercizi.py count-lines dati.txt
#   python3 esercizi.py export-csv persone.json uscita.csv
#   python3 esercizi.py make-code

import json
import os
import random
import sys


# User story 1 - Sorting a list of numbers

def sort(numeri):
    # sorted() builds a new list, numeri.sort() would change the one it was given
    return sorted(numeri)


# User story 2 - Dividing two numbers

def divide(a, b):
    if b == 0:
        raise ValueError("division by zero")
    return a / b


# User story 3 - Counting the lines of a file

def count_lines(percorso):
    if not os.path.exists(percorso):
        raise ValueError("File not found: " + percorso)

    with open(percorso, encoding="utf-8") as f:
        testo = f.read()

    # an empty file has no lines, one without a final newline still has one
    if testo == "":
        return 0
    return len(testo.rstrip("\n").split("\n"))


# User story 4 - Turning a JSON file of records into CSV
#
# The column names come from the first record, so every record is expected to
# carry the same keys. A missing key raises, which is the right answer: a CSV
# with holes in it would be worse than no CSV at all.

def export_csv(ingresso, uscita):
    try:
        with open(ingresso, encoding="utf-8") as f:
            record = json.load(f)
    except Exception:
        raise ValueError("Invalid JSON in " + ingresso)

    # with no records nothing is written: an empty file is not an export
    if len(record) == 0:
        raise ValueError("Nothing to export")

    colonne = list(record[0].keys())
    righe = []
    for r in record:
        valori = []
        for c in colonne:
            valori.append(str(r[c]))
        righe.append(",".join(valori))

    with open(uscita, "w", encoding="utf-8") as f:
        f.write("\n".join([",".join(colonne)] + righe))

    return len(record)


# User story 5 - Generating a random six digit code

def make_code():
    codice = ""
    for _ in range(6):
        codice = codice + random.choice("0123456789")
    return codice


# Command line
#
# One command per run, with its arguments after it. There is no interactive
# menu on purpose: the acceptance criteria reach this file either by calling
# the functions above or by running this program with arguments, and neither
# of the two can answer a prompt.

def comando_singolo():
    comando = sys.argv[1]
    argomenti = sys.argv[2:]

    if comando == "sort":
        interi = []
        for a in argomenti:
            interi.append(int(a))

        testo = []
        for n in sort(interi):
            testo.append(str(n))

        print(" ".join(testo))

    elif comando == "divide":
        print(divide(float(argomenti[0]), float(argomenti[1])))

    elif comando == "count-lines":
        print(count_lines(argomenti[0]))

    elif comando == "export-csv":
        print("Exported", export_csv(argomenti[0], argomenti[1]), "records")

    elif comando == "make-code":
        print(make_code())

    else:
        raise ValueError("Unknown command: " + comando)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: esercizi.py <sort|divide|count-lines|export-csv|make-code> [arguments]",
              file=sys.stderr)
        sys.exit(1)

    try:
        comando_singolo()
    except ValueError as errore:
        print(errore, file=sys.stderr)
        sys.exit(1)
    except IndexError:
        # a command called with too few arguments, said plainly instead of a traceback
        print("Missing arguments", file=sys.stderr)
        sys.exit(1)
