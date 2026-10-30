#Trasforma l'output di behave in un testo da scrivere nei sistemi di project management

import json
import os
import urllib.error
import urllib.request
import fetch_criteria as fc
import re


VERIFIER = os.path.dirname(os.path.abspath(__file__))         # cartella di questo file, dove sta statuses.json


# chiama un indirizzo con il metodo richiesto e restituisce la risposta come JSON
def call(address, headers, data=None, method="GET"):
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    sent = dict(headers)                                      # copia, cosi' non modifica il dizionario di chi chiama
    if payload is not None:
        sent["Content-Type"] = "application/json"             # lo dichiara solo quando c'e' davvero un corpo

    request = urllib.request.Request(address, data=payload,
                                     headers=sent, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else None         # alcune risposte sono vuote, come il PATCH di Taiga
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8")                 # il motivo del rifiuto sta nel corpo, non nel codice di stato
        raise RuntimeError(method + " " + address + " -> " +
                           str(error.code) + "\n" + detail) from None   # from None toglie il doppio errore concatenato


# si accredita su Taiga e restituisce l'intestazione gia' pronta
def taiga_login():
    body = {"type": "normal", "username": fc.TAIGA_USER, "password": fc.TAIGA_PASS}
    data = call(fc.TAIGA_URL + "/api/v1/auth", {}, body, "POST")
    return {"Authorization": "Bearer " + data["auth_token"]}



# Il risultato dal formato json di behave


# legge l'esito di behave e ne ricava il testo del resoconto e il verdetto
def summary(path, header):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    scenarios = []
    for feature in data:                                      # il json di behave e' una lista di feature
        for element in feature.get("elements", []):
            if element.get("type") == "scenario":             # scarta quello che non e' scenario
                scenarios.append(element)

    # le etichette senza la chiocciola, confrontate minuscole: @Manual contava
    # come criterio automatico e veniva eseguito, mentre qui risultava a mano
    def is_manual(scenario):
        return "manual" in [t.lower() for t in scenario.get("tags", [])]

    manual = [s for s in scenarios if is_manual(s)]
    automated = [s for s in scenarios if not is_manual(s)]
    passed = [s for s in automated if s.get("status") == "passed"]

    # zero criteri automatici non e' un esito positivo. Prima il confronto era
    # len(passed) == len(automated), vero anche con entrambi a zero: una user
    # story con tutti gli scenari @manual, o un Outline senza Examples, usciva
    # "tutto verde" e veniva firmata sulla catena senza che un solo test
    # fosse girato
    all_green = len(automated) > 0 and len(passed) == len(automated)

    lines = list(header)
    lines.append("")
    lines.append("Automated criteria: " + str(len(passed)) + " of " +
                 str(len(automated)) + " passed")

    for scenario in automated:
        outcome = "OK" if scenario.get("status") == "passed" else "FAILED"
        lines.append("  " + scenario["name"].ljust(44) + outcome)   # allinea gli esiti in colonna

        if outcome == "FAILED":
            for item in scenario.get("steps", []):
                result = item.get("result") or {}             # un passo saltato ha affatto il campo result
                if result.get("status") != "failed":
                    continue
                lines.append("      step:  " + item["keyword"] + " " + item["name"])

                message = result.get("error_message") or []
                if isinstance(message, str):                  # behave lo scrive come stringa o come lista di righe
                    message = [message]
                for block in message:
                    for line in str(block).split("\n"):
                        line = line.strip()
                        # behave chiama "Assertion Failed" nel json e "ASSERT FAILED" a schermo
                        if re.match(r"^assert(ion)? failed:", line, re.I):
                            lines.append("      " + line.split(":", 1)[1].strip())   # butta l'etichetta e tiene il messaggio

    if manual:
        lines.append("")
        lines.append("To be checked by hand: " + str(len(manual)))
        for scenario in manual:
            lines.append("  " + scenario["name"])

    lines.append("")
    if not automated:
        lines.append("Status: there is no automated criterion to run, "
                     "nothing has been verified.")
    elif all_green and manual:
        lines.append("Status: the automated criteria passed, "
                     "waiting for the Product Owner.")
    elif all_green:
        lines.append("Status: all automated criteria passed.")
    else:
        lines.append("Status: rejected, the delivery does not meet the criteria.")

    return "\n".join(lines), all_green                        # il bool decide il codice di uscita e la firma sulla catena


# Scrittura nei tre sistemi

# cerca in statuses.json lo stato in cui spostare la task
def target_status(system, project, passed):
    with open(os.path.join(VERIFIER, "statuses.json"), encoding="utf-8") as f:
        statuses = json.load(f)

    name = system + ":" + project                             # chiave composta come openproject:Prova
    if name not in statuses:
        return None                                           # progetto non configurato va a WRITE
    return statuses[name]["passed" if passed else "failed"]


# scrive il commento e cambia lo stato su OpenProject,
def to_openproject(key, text, status):
    headers = fc.basic("apikey", fc.OP_TOKEN)
    base = fc.OP_URL + "/api/v3/work_packages/" + key
    call(base + "/activities", headers, {"comment": {"raw": "```\n" + text + "\n```"}}, "POST")   # mantiene l'incolonnamento

    current = call(base, headers)                             # legge la versione 
    call(base, headers, {
        "lockVersion": current["lockVersion"],                # se qualcuno ha toccato la task nel frattempo rifiuta invece di sovrascrivere
        "_links": {"status": {"href": "/api/v3/statuses/" + str(status)}}
    }, "PATCH")


# scrive il commento e cambia lo stato su Taiga 
def to_taiga(key, text, status):
    headers = taiga_login()
    story = call(fc.TAIGA_URL + "/api/v1/userstories/by_ref?ref=" + key +   # serve l'identificativo interno, che by_ref ricava dal numero visibile
                 "&project__slug=" + fc.TAIGA_SLUG, headers)

    call(fc.TAIGA_URL + "/api/v1/userstories/" + str(story["id"]), headers, {
        "version": story["version"],                          # stesso controllo di OP
        "status": status,
        "comment": "```\n" + text + "\n```"                   # commento e stato 
    }, "PATCH")


# scrive il commento ed esegue la transizione su Jira
def to_jira(key, text, status):
    headers = fc.basic(fc.JIRA_USER, fc.JIRA_TOKEN)
    base = fc.JIRA_URL + "/rest/api/2/issue/" + key

    call(base + "/comment", headers,
         {"body": "{noformat}\n" + text + "\n{noformat}"}, "POST")   # Jira usa {noformat} al posto dei backtick

    call(base + "/transitions", headers, {"transition": {"id": str(status)}}, "POST")   # non si mette uno stato si esegue una transizione


# associa ogni sistema alla funzione che ci scrive
WRITERS = {"openproject": to_openproject, "taiga": to_taiga, "jira": to_jira}


# sceglie lo stato di destinazione e lo scrive nel sistema giusto
def write(system, key, project, text, passed):
    status = target_status(system, project, passed)
    if status is None:
        print("No status configured for \"" + system + ":" + project + "\"")
        return                                                # esce senza scrivere, invece di fallire
    WRITERS[system](key, text, status)