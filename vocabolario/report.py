 # Trasforma l'output di behave in un resoconto da scrivere nei sistemi di project management
import json
import os
import urllib.error
import urllib.request
import fetch_criteria as fc
import re


VERIFIER = os.path.dirname(os.path.abspath(__file__))


def call(address, headers, data=None, method="GET"):
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    sent = dict(headers)
    if payload is not None:
        sent["Content-Type"] = "application/json"

    request = urllib.request.Request(address, data=payload,
                                     headers=sent, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        # il motivo del rifiuto sta nel corpo della risposta, non nel codice
        detail = error.read().decode("utf-8")
        raise RuntimeError(method + " " + address + " -> " +
                           str(error.code) + "\n" + detail) from None


def taiga_login():
    body = {"type": "normal", "username": fc.TAIGA_USER, "password": fc.TAIGA_PASS}
    data = call(fc.TAIGA_URL + "/api/v1/auth", {}, body, "POST")
    return {"Authorization": "Bearer " + data["auth_token"]}


# ------------------------------------------------------------
# Il resoconto, dal formato json di behave
# ------------------------------------------------------------

def summary(path, header):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    scenarios = []
    for feature in data:
        for element in feature.get("elements", []):
            if element.get("type") == "scenario":
                scenarios.append(element)

    manual = [s for s in scenarios if "manual" in s.get("tags", [])]
    automated = [s for s in scenarios if "manual" not in s.get("tags", [])]
    passed = [s for s in automated if s.get("status") == "passed"]
    all_green = len(passed) == len(automated)

    lines = list(header)
    lines.append("")
    lines.append("Automated criteria: " + str(len(passed)) + " of " +
                 str(len(automated)) + " passed")

    for scenario in automated:
        outcome = "OK" if scenario.get("status") == "passed" else "FAILED"
        lines.append("  " + scenario["name"].ljust(44) + outcome)

        if outcome == "FAILED":
            for item in scenario.get("steps", []):
                result = item.get("result") or {}
                if result.get("status") != "failed":
                    continue
                lines.append("      step:  " + item["keyword"] + " " + item["name"])

                # behave scrive il messaggio come lista di righe o come
                # stringa unica, e lo chiama "Assertion Failed" nel formato
                # json e "ASSERT FAILED" in quello a schermo
                message = result.get("error_message") or []
                if isinstance(message, str):
                    message = [message]
                for block in message:
                    for line in str(block).split("\n"):
                        line = line.strip()
                        if re.match(r"^assert(ion)? failed:", line, re.I):
                            lines.append("      " + line.split(":", 1)[1].strip())

    if manual:
        lines.append("")
        lines.append("To be checked by hand: " + str(len(manual)))
        for scenario in manual:
            lines.append("  " + scenario["name"])

    lines.append("")
    if all_green and manual:
        lines.append("Status: waiting for the Product Owner.")
    elif all_green:
        lines.append("Status: all automated criteria passed.")
    else:
        lines.append("Status: rejected, the delivery does not meet the criteria.")

    return "\n".join(lines), all_green


# ------------------------------------------------------------
# La scrittura nei tre sistemi
# ------------------------------------------------------------

def target_status(system, project, passed):
    with open(os.path.join(VERIFIER, "statuses.json"), encoding="utf-8") as f:
        statuses = json.load(f)

    name = system + ":" + project
    if name not in statuses:
        return None
    return statuses[name]["passed" if passed else "failed"]


def to_openproject(key, text, status):
    headers = fc.basic("apikey", fc.OP_TOKEN)
    base = fc.OP_URL + "/api/v3/work_packages/" + key
    call(base + "/activities", headers, {"comment": {"raw": "```\n" + text + "\n```"}}, "POST")

    # lockVersion: OpenProject rifiuta la modifica se nel frattempo
    # qualcun altro ha toccato la task
    current = call(base, headers)
    call(base, headers, {
        "lockVersion": current["lockVersion"],
        "_links": {"status": {"href": "/api/v3/statuses/" + str(status)}}
    }, "PATCH")
    


def to_taiga(key, text, status):
    headers = taiga_login()
    story = call(fc.TAIGA_URL + "/api/v1/userstories/by_ref?ref=" + key +
                 "&project__slug=" + fc.TAIGA_SLUG, headers)

    # su Taiga commento e stato si mandano insieme, nella stessa modifica
    call(fc.TAIGA_URL + "/api/v1/userstories/" + str(story["id"]), headers, {
        "version": story["version"],
        "status": status,
        "comment": "```\n" + text + "\n```"
    }, "PATCH")


def to_jira(key, text, status):
    headers = fc.basic(fc.JIRA_USER, fc.JIRA_TOKEN)
    base = fc.JIRA_URL + "/rest/api/2/issue/" + key

    call(base + "/comment", headers,
         {"body": "{noformat}\n" + text + "\n{noformat}"}, "POST")

    # su Jira non si imposta lo stato: si esegue una transizione
    call(base + "/transitions", headers, {"transition": {"id": str(status)}}, "POST")


WRITERS = {"openproject": to_openproject, "taiga": to_taiga, "jira": to_jira}


def write(system, key, project, text, passed):
    status = target_status(system, project, passed)
    if status is None:
        print("No status configured for \"" + system + ":" + project + "\"")
        return
    WRITERS[system](key, text, status)
