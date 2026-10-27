# TUTTI gli stati dei tre sistemi per trovare gli id da mettere in statuses.json

import json
import sys

import fetch_criteria as fc                                    # riusa indirizzi, credenziali e le funzioni get e basic


# stampa gli stati di OpenProject, che valgono per tutta l'istanza
def openproject():
    data = fc.get(fc.OP_URL + "/api/v3/statuses", fc.basic("apikey", fc.OP_TOKEN))
    for status in data["_embedded"]["elements"]:                  # nel formato HAL le collezioni stanno dentro _embedded
        closed = "  (closed)" if status.get("isClosed") else ""   # distingue gli stati finali da quelli intermedi
        print("  " + str(status["id"]) + "  " + status["name"] + closed)


# stampa gli stati di Taiga che appartengono al progetto 
def taiga():
    body = json.dumps({"type": "normal",
                       "username": fc.TAIGA_USER,
                       "password": fc.TAIGA_PASS}).encode("utf-8")
    session = fc.get(fc.TAIGA_URL + "/api/v1/auth",
                     {"Content-Type": "application/json"}, body)   # si accredita e ottiene il token
    headers = {"Authorization": "Bearer " + session["auth_token"]}

    project = fc.get(fc.TAIGA_URL + "/api/v1/projects/by_slug?slug=" + fc.TAIGA_SLUG,
                     headers)
    for status in project["us_statuses"]:                      # gli stati arrivano dentro il progetto
        closed = "  (closed)" if status.get("is_closed") else ""
        print("  " + str(status["id"]) + "  " + status["name"] + closed)


# stampa le transizioni di Jira che dipendono dalla singola issue e da dove si trova
def jira(project):
    found = fc.get(fc.JIRA_URL + "/rest/api/2/search/jql?maxResults=1&fields=key&jql=project%3D" +
                   project, fc.basic(fc.JIRA_USER, fc.JIRA_TOKEN))   # /search/jql
    issues = found.get("issues", [])                           # lista vuota invece di un errore se la chiave manca
    if not issues:
        print("  no issues in project " + project)
        return

    sample = issues[0]["key"]
    print("  (sample issue: " + sample + ")")                  # l'elenco vale dallo stato in cui si trova questa issue

    data = fc.get(fc.JIRA_URL + "/rest/api/2/issue/" + sample + "/transitions",
                  fc.basic(fc.JIRA_USER, fc.JIRA_TOKEN))
    for move in data["transitions"]:
        print("  " + move["id"] + "  " + move["name"] + "  ->  " + move["to"]["name"])   # l'id da mettere in statuses.json e' quello della transizione


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else "KAN"      # usa KAN se non arriva nessun progetto

    print("OpenProject:")
    openproject()
    print()
    print("Taiga (" + fc.TAIGA_SLUG + "):")
    taiga()
    print()
    print("Jira (transitions available in project " + project + "):")
    jira(project)