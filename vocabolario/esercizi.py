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
#   python3 esercizi.py signup anna@esempio.it SegretoLungo1
#   python3 esercizi.py verify anna@esempio.it
#   python3 esercizi.py login  anna@esempio.it SegretoLungo1
#   python3 esercizi.py pagina             la finta pagina di registrazione

import hashlib
import json
import os
import random
import re
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


# User story 6 - Pagina WEB

# Gli utenti stanno in un file JSON

ARCHIVIO = "utenti.json"
PASSWORD_MINIMA = 8

# controllo @, spazi e punti
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _carica_utenti(percorso=ARCHIVIO):
    if not os.path.exists(percorso):
        return {}                                  # il primo utente crea l'archivio

    with open(percorso, encoding="utf-8") as f:
        return json.load(f)


def _salva_utenti(utenti, percorso=ARCHIVIO):
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump(utenti, f, indent=2, sort_keys=True)


def _impronta(password, sale):
    #si aggiunge il sale per cryptare meglio password uguali
    return hashlib.sha256((sale + password).encode("utf-8")).hexdigest()


def signup(email, password):
    if not EMAIL.match(email):
        raise ValueError("Email non valida: " + email)
    if len(password) < PASSWORD_MINIMA:
        raise ValueError("Password troppo corta, minimo " +
                         str(PASSWORD_MINIMA) + " caratteri")

    utenti = _carica_utenti()
    if email in utenti:
        raise ValueError("Utente già registrato: " + email)

    sale = make_code()                            
    utenti[email] = {"sale": sale,"impronta": _impronta(password, sale), "verified": False}            

    return {"email": email, "verified": False}


def verify(email):
    utenti = _carica_utenti()
    if email not in utenti:
        raise ValueError("Utente inesistente: " + email)

    utenti[email]["verified"] = True
    _salva_utenti(utenti)

    return {"email": email, "verified": True}


def login(email, password):
    utenti = _carica_utenti()
    if email not in utenti:
        raise ValueError("Utente inesistente: " + email)

    utente = utenti[email]

    # prima la password e poi la verifica
    if _impronta(password, utente["sale"]) != utente["impronta"]:
        raise ValueError("Password errata")
    if not utente["verified"]:
        raise ValueError("Account non verificato: " + email)

    return {"email": email, "verified": True}


# Finta pagina web
def pagina():
    while True:
        print("\n+" + "-" * 44 + "+")
        print("|" + " GESTIONE ACCOUNT ".center(44) + "|")
        print("+" + "-" * 44 + "+\n")
        print("  1 - Registrazione (Signup)")
        print("  2 - Accesso (Login)")
        print("  3 - Verifica Email")
        print("  0 - Torna al menu principale\n")

        scelta = input("  Scegli un'opzione: ").strip()

        if scelta == "0":
            break

        elif scelta == "1":
            email = input("  Email: ").strip()
            password = input("  Password: ").strip()
            try:
                signup(email, password)
                print("\n  [ok] Account creato. Usa l'opzione 3 per verificare l'email prima di accedere.")
            except ValueError as errore:
                print("\n  [!] " + str(errore))

        elif scelta == "2":
            email = input("  Email: ").strip()
            password = input("  Password: ").strip()
            try:
                login(email, password)
                print("\n  [ok] Accesso riuscito. Benvenuto " + email + ".")
            except ValueError as errore:
                print("\n  [!] " + str(errore))

        elif scelta == "3":
            email = input("  Email da verificare: ").strip()
            try:
                verify(email)
                print("\n  [ok] Email verificata con successo.")
            except ValueError as errore:
                print("\n  [!] " + str(errore))

        else:
            print("\n  [!] Scelta non valida.")

def menu():
    while True:
        print()
        print("1  ordinare una lista di numeri")
        print("2  dividere due numeri")
        print("3  contare le righe di un file")
        print("4  convertire un file JSON in CSV")
        print("5  generare un codice")
        print("6  Pagina WEB")
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

            elif scelta == "6":
                pagina()

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
