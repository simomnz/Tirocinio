# Legge una user story dal sistema di project management e salva i suoi
# criteri di accettazione come file .feature, pronto per behave.
#
#   python3 fetch_criteria.py openproject 1115
#   python3 fetch_criteria.py taiga 7
#   python3 fetch_criteria.py jira KAN-12

import base64
import html
import json
import os
import re
import sys
import urllib.request

# Credenziali: si possono passare da fuori senza toccare il file
OP_URL = os.environ.get("OP_URL", "http://127.0.0.1:8090")
OP_TOKEN = os.environ.get("OP_TOKEN", "")

TAIGA_URL = os.environ.get("TAIGA_URL", "https://api.taiga.io")
TAIGA_USER = os.environ.get("TAIGA_USER", "")
TAIGA_PASS = os.environ.get("TAIGA_PASS", "")
TAIGA_SLUG = os.environ.get("TAIGA_SLUG", "simomnz-prova-api")

JIRA_URL = os.environ.get("JIRA_URL", "https://simomnz.atlassian.net")
JIRA_USER = os.environ.get("JIRA_USER", "")
JIRA_TOKEN = os.environ.get("JIRA_TOKEN", "")


def get(address, headers=None, data=None):
    request = urllib.request.Request(address, data=data, headers=headers or {})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def basic(user, secret):
    pair = (user + ":" + secret).encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(pair).decode("ascii")}


# ------------------------------------------------------------
# I tre sistemi: ognuno restituisce (titolo, descrizione, progetto)
# ------------------------------------------------------------

def from_openproject(key):
    data = get(OP_URL + "/api/v3/work_packages/" + key, basic("apikey", OP_TOKEN))
    return (data["subject"],
            data["description"]["raw"],
            data["_links"]["project"]["title"])


def from_taiga(key):
    body = json.dumps({"type": "normal",
                       "username": TAIGA_USER,
                       "password": TAIGA_PASS}).encode("utf-8")
    session = get(TAIGA_URL + "/api/v1/auth",
                  {"Content-Type": "application/json"}, body)

    data = get(TAIGA_URL + "/api/v1/userstories/by_ref?ref=" + key +
               "&project__slug=" + TAIGA_SLUG,
               {"Authorization": "Bearer " + session["auth_token"]})
    return data["subject"], data["description"] or "", TAIGA_SLUG


def from_jira(key):
    # la versione 2 restituisce la descrizione come testo semplice,
    # la 3 la restituisce a blocchi
    data = get(JIRA_URL + "/rest/api/2/issue/" + key, basic(JIRA_USER, JIRA_TOKEN))
    return (data["fields"]["summary"],
            data["fields"]["description"] or "",
            key.split("-")[0])


READERS = {"openproject": from_openproject,
           "taiga": from_taiga,
           "jira": from_jira}


# ------------------------------------------------------------
# Pulizia: i tre sistemi non restituiscono il testo come e' stato scritto
# ------------------------------------------------------------

def clean(text):
    text = html.unescape(text)

    lines = []
    for line in text.split("\n"):
        # i recinti del blocco di codice: ``` ```gherkin ```` ```text
        if re.match(r"^\s*`{3,}\w*\s*$", line):
            continue

        # OpenProject mette un a capo in HTML dove c'era la riga vuota
        if re.match(r"^\s*<br\s*/?>\s*$", line):
            continue

        # {noformat} e' la marcatura che usa Jira nella versione 2
        line = line.replace("{noformat}", "")

        # OpenProject mette due spazi a fine riga e la barra sui backtick
        line = line.rstrip().replace("\\`", "`")
        lines.append(line)

    # i tre editor lasciano un numero diverso di righe vuote attorno al blocco
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")


def main():
    if len(sys.argv) < 3:
        print("Usage: fetch_criteria.py <openproject|taiga|jira> <id>",
              file=sys.stderr)
        return 1

    system, key = sys.argv[1], sys.argv[2]

    if system not in READERS:
        print("Unknown system: " + system, file=sys.stderr)
        return 1

    title, description, project = READERS[system](key)
    body = clean(description)

    if not re.search(r"^\s*Scenario", body, re.M):
        print("No acceptance criteria found in " + system + " " + key,
              file=sys.stderr)
        return 1

    # Il titolo della task diventa la riga Feature, il resto della descrizione
    # resta com'e': Gherkin accetta testo libero fin dove comincia il primo
    # Scenario. Il nome del file porta il sistema di provenienza.
    name = re.sub(r"[^A-Za-z0-9-]+", "-", title).strip("-")
    path = os.path.join("features", system + "-" + name + ".feature")

    os.makedirs("features", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("Feature: " + title + "\n\n" + body + "\n")

    count = len(re.findall(r"^\s*Scenario", body, re.M))
    print("Written " + path + " (" + str(count) + " scenarios)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
