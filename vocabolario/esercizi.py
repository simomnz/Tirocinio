# Esercizi di prova, uno per user story.
#
# Due modi d'uso:
#
#   python3 esercizi.py                    menu interattivo
#   python3 esercizi.py sort 3 1 2         direttamente da riga di comando
#   python3 esercizi.py divide 10 2
#   python3 esercizi.py count-lines dati.txt
#   python3 esercizi.py export-csv persone.json uscita.csv
#   python3 esercizi.py make-code

import json
import os
import random
import sys


# User story 1 - Ordinare una lista di numeri

def sort(numeri):
    # sorted() crea una lista nuova, numeri.sort() modificherebbe quella ricevuta
    return sorted(numeri)


# User story 2 - Dividere due numeri

def divide(a, b):
    if b == 0:
        raise ValueError("division by zero")
    return a / b


# User story 3 - Contare le righe di un file

def count_lines(percorso):
    if not os.path.exists(percorso):
        raise ValueError("File not found: " + percorso)

    with open(percorso, encoding="utf-8") as f:
        testo = f.read()

    # un file vuoto ha zero righe, uno senza a capo finale ne ha comunque una
    if testo == "":
        return 0
    return len(testo.rstrip("\n").split("\n"))


# User story 4 - Convertire un file JSON di record in CSV

def export_csv(ingresso, uscita):
    try:
        with open(ingresso, encoding="utf-8") as f:
            record = json.load(f)
    except Exception:
        raise ValueError("Invalid JSON in " + ingresso)

    # senza record non si crea un file vuoto, ci si ferma
    if len(record) == 0:
        raise ValueError("Nothing to export")

    colonne = list(record[0].keys())
    righe = [",".join(str(r[c]) for c in colonne) for r in record]

    with open(uscita, "w", encoding="utf-8") as f:
        f.write("\n".join([",".join(colonne)] + righe))

    return len(record)


# User story 5 - Generare un codice casuale di sei cifre

def make_code():
    return "".join(random.choice("0123456789") for _ in range(6))


# Menu interattivo

def menu():
    while True:
        print()
        print("1  ordinare una lista di numeri")
        print("2  dividere due numeri")
        print("3  contare le righe di un file")
        print("4  convertire un file JSON in CSV")
        print("5  generare un codice")
        print("0  uscire")

        scelta = input("Scelta: ").strip()

        if scelta == "0":
            return

        try:
            if scelta == "1":
                numeri = input("Numeri separati da spazio: ").split()
                print(" ".join(str(n) for n in sort([int(a) for a in numeri])))

            elif scelta == "2":
                a = float(input("Primo numero: "))
                b = float(input("Secondo numero: "))
                print(divide(a, b))

            elif scelta == "3":
                print(count_lines(input("File da leggere: ")))

            elif scelta == "4":
                ingresso = input("File JSON da leggere: ")
                uscita = input("File CSV da creare: ")
                print("Exported", export_csv(ingresso, uscita), "records")

            elif scelta == "5":
                print(make_code())

            else:
                print("Scelta non valida")

        except ValueError as errore:
            # nel menu un errore non chiude il programma, si torna alla scelta
            print("Errore:", errore)


# Riga di comando

def comando_singolo():
    comando = sys.argv[1]
    argomenti = sys.argv[2:]

    if comando == "sort":
        print(" ".join(str(n) for n in sort([int(a) for a in argomenti])))

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
    # senza argomenti parte il menu, altrimenti si esegue il comando chiesto
    if len(sys.argv) < 2:
        menu()
    else:
        try:
            comando_singolo()
        except ValueError as errore:
            print(errore, file=sys.stderr)
            sys.exit(1)
        except IndexError:
            print("Missing arguments", file=sys.stderr)
            sys.exit(1)
