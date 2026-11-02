import hashlib
import json
import os
import re
import secrets
import sys


ARCHIVIO = "utenti.json"
PASSWORD_MINIMA = 8
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _carica_utenti():
    if not os.path.exists(ARCHIVIO):
        return {}

    with open(ARCHIVIO, encoding="utf-8") as file:
        return json.load(file)


def _salva_utenti(utenti):
    with open(ARCHIVIO, "w", encoding="utf-8") as file:
        json.dump(utenti, file, indent=2, sort_keys=True)


def _impronta(password, sale):
    return hashlib.sha256(
        (sale + password).encode("utf-8")
    ).hexdigest()


def signup(email, password):
    if not EMAIL.fullmatch(email):
        raise ValueError("Email non valida: " + email)

    if len(password) < PASSWORD_MINIMA:
        raise ValueError(
            "Password troppo corta, minimo 8 caratteri"
        )

    utenti = _carica_utenti()

    if email in utenti:
        raise ValueError("Utente già registrato: " + email)

    sale = secrets.token_hex(16)

    utenti[email] = {
        "sale": sale,
        "impronta": _impronta(password, sale),
        "verified": False,
    }

    _salva_utenti(utenti)

    return {
        "email": email,
        "verified": False,
    }


def verify(email):
    utenti = _carica_utenti()

    if email not in utenti:
        raise ValueError("Utente inesistente: " + email)

    utenti[email]["verified"] = True
    _salva_utenti(utenti)

    return {
        "email": email,
        "verified": True,
    }


def login(email, password):
    utenti = _carica_utenti()

    if email not in utenti:
        raise ValueError("Utente inesistente: " + email)

    utente = utenti[email]

    if _impronta(password, utente["sale"]) != utente["impronta"]:
        raise ValueError("Password errata")

    if not utente["verified"]:
        raise ValueError("Account non verificato: " + email)

    return {
        "email": email,
        "verified": True,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: signup, verify oppure login")
        sys.exit(1)

    comando = sys.argv[1]
    argomenti = sys.argv[2:]

    try:
        if comando == "signup":
            risultato = signup(argomenti[0], argomenti[1])
        elif comando == "verify":
            risultato = verify(argomenti[0])
        elif comando == "login":
            risultato = login(argomenti[0], argomenti[1])
        else:
            raise ValueError("Comando sconosciuto: " + comando)

        print(json.dumps(risultato))
    except (ValueError, IndexError) as errore:
        print(errore, file=sys.stderr)
        sys.exit(1)