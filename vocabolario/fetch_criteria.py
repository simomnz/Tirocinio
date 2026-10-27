# legge la user story dal sistema e salva i criteri di accettazione come file .feature

import base64
import html
import json
import os
import re
import sys
import urllib.request

# Credenziali
OP_URL = os.environ.get("OP_URL", "http://127.0.0.1:8090")
OP_TOKEN = os.environ.get("OP_TOKEN", "")                      

TAIGA_URL = os.environ.get("TAIGA_URL", "https://api.taiga.io")
TAIGA_USER = os.environ.get("TAIGA_USER", "")
TAIGA_PASS = os.environ.get("TAIGA_PASS", "")
TAIGA_SLUG = os.environ.get("TAIGA_SLUG", "simomnz-prova-api")

JIRA_URL = os.environ.get("JIRA_URL", "https://simomnz.atlassian.net")
JIRA_USER = os.environ.get("JIRA_USER", "")
JIRA_TOKEN = os.environ.get("JIRA_TOKEN", "")
JIRA_PROJECT = os.environ.get("JIRA_PROJECT", "KAN")


# chiama un indirizzo e restituisce la risposta letta come JSON
def get(address, headers=None, data=None):
    request = urllib.request.Request(address, data=data, headers=headers or {})   # manda una POST se data e' piena altrimenti una GET
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


# intestazione di autenticazione con un utente e secret
def basic(user, secret):
    pair = (user + ":" + secret).encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(pair).decode("ascii")}   


# aggiunge per JIRA la sigla del progetto
def normalize(system, key):
    if system == "jira" and "-" not in key:
        return JIRA_PROJECT + "-" + key
    return key



# scarica la user story da OpenProject
def from_openproject(key):
    data = get(OP_URL + "/api/v3/work_packages/" + key, basic("apikey", OP_TOKEN))   # utente fisso "apikey" e il token come password
    return (data["subject"],
            data["description"]["raw"],                        # prende il testo scritto dal PO
            data["_links"]["project"]["title"])


# scarica la user story da Taiga
def from_taiga(key):
    body = json.dumps({"type": "normal",
                       "username": TAIGA_USER,
                       "password": TAIGA_PASS}).encode("utf-8")
    session = get(TAIGA_URL + "/api/v1/auth",
                  {"Content-Type": "application/json"}, body)  #  token valido solo per questa esecuzione

    data = get(TAIGA_URL + "/api/v1/userstories/by_ref?ref=" + key +   # cerca con il numero della TASK
               "&project__slug=" + TAIGA_SLUG,
               {"Authorization": "Bearer " + session["auth_token"]})
    return data["subject"], data["description"] or "", TAIGA_SLUG     # se la descrizione non c'e' diventa una stringa vuota


# VERSIONE 2 DELLA API JIRA, non la 3, per differenza di return della descrizione 

def from_jira(key):
    data = get(JIRA_URL + "/rest/api/2/issue/" + key, basic(JIRA_USER, JIRA_TOKEN))
    return (data["fields"]["summary"],
            data["fields"]["description"] or "",
            key.split("-")[0])                                 # prende KAN da KAN-numero


# dizionario per i sistemi
READERS = {"openproject": from_openproject,
           "taiga": from_taiga,
           "jira": from_jira}



# Pulizia del testo


# toglie dal testo i vari caratteri che i tre sistemi aggiungono 
def clean(text):
    text = html.unescape(text)                                #toglie l'html  

    lines = []
    for line in text.split("\n"):
        
        # salta l'inizio e la fine del blocco di codice sia ``` sia ```gherkin
        
        if re.match(r"^\s*`{3,}\w*\s*$", line):
            continue

        # salta l'acapo in HTML che OpenProject mette dove c'era una riga vuota
        if re.match(r"^\s*<br\s*/?>\s*$", line):               # accetta sia <br> sia <br/>
            continue

        line = line.replace("{noformat}", "")                  # toglie la marcatura dei blocchi di Jira

        line = line.rstrip().replace("\\`", "`")               # yoglie i due spazi finali

        lines.append(line)

    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")         # riduce a due le righe vuote consecutive, per essere tutti e 3 identici


def main():
    if len(sys.argv) < 3:
        print("Usage: fetch_criteria.py <openproject|taiga|jira> <id>",
              file=sys.stderr)                                 # scrive gli errori su stderr
        return 1

    system, key = sys.argv[1], sys.argv[2]
    key = normalize(system, key)                               #sistema e chiave della task
    
    if system not in READERS:
        print("Unknown system: " + system, file=sys.stderr)
        return 1

    title, description, project = READERS[system](key)         # sceglie il sistema dal dizionario e lo chiama
    body = clean(description)

    if not re.search(r"^\s*Scenario", body, re.M):             # si ferma se non trova nemmeno uno Scenario da eseguire
        print("No acceptance criteria found in " + system + " " + key,
              file=sys.stderr)
        return 1

    name = re.sub(r"[^A-Za-z0-9-]+", "-", title).strip("-")    # trasforma il titolo nel nome di file
    path = os.path.join("features", system + "-" + name + ".feature")   # sistema davanti al nome
    
    os.makedirs("features", exist_ok=True)                     # crea la cartella solo se non c'e' gia'
    with open(path, "w", encoding="utf-8") as f:
        f.write("Feature: " + title + "\n\n" + body + "\n")    # costruisce la riga Feature dal titolo della task

    count = len(re.findall(r"^\s*Scenario", body, re.M))       # conta gli Scenario trovati
    print("Written " + path + " (" + str(count) + " scenarios)")
    return 0


if __name__ == "__main__":                                    
    sys.exit(main())                                           