# Inutile, solo per capire quanti stati esistessero sui 3 sistemi
import json
import sys

import fetch_criteria as fc


def openproject():
    data = fc.get(fc.OP_URL + "/api/v3/statuses", fc.basic("apikey", fc.OP_TOKEN))
    for status in data["_embedded"]["elements"]:
        closed = "  (closed)" if status.get("isClosed") else ""
        print("  " + str(status["id"]) + "  " + status["name"] + closed)


def taiga():
    body = json.dumps({"type": "normal",
                       "username": fc.TAIGA_USER,
                       "password": fc.TAIGA_PASS}).encode("utf-8")
    session = fc.get(fc.TAIGA_URL + "/api/v1/auth",
                     {"Content-Type": "application/json"}, body)
    headers = {"Authorization": "Bearer " + session["auth_token"]}

    project = fc.get(fc.TAIGA_URL + "/api/v1/projects/by_slug?slug=" + fc.TAIGA_SLUG,
                     headers)
    for status in project["us_statuses"]:
        closed = "  (closed)" if status.get("is_closed") else ""
        print("  " + str(status["id"]) + "  " + status["name"] + closed)
        
def jira(project):
    # le transizioni su Jira dipendono dalla singola issue e dal punto in cui
    # si trova, quindi non esiste una risposta valida per tutto il progetto:
    # ne prendiamo una qualsiasi e usiamo quella come campione
    found = fc.get(fc.JIRA_URL + "/rest/api/2/search/jql?maxResults=1&fields=key&jql=project%3D" +
                   project, fc.basic(fc.JIRA_USER, fc.JIRA_TOKEN))
    issues = found.get("issues", [])
    if not issues:
        print("  no issues in project " + project)
        return

    sample = issues[0]["key"]
    print("  (sample issue: " + sample + ")")

    data = fc.get(fc.JIRA_URL + "/rest/api/2/issue/" + sample + "/transitions",
                  fc.basic(fc.JIRA_USER, fc.JIRA_TOKEN))
    for move in data["transitions"]:
        print("  " + move["id"] + "  " + move["name"] + "  ->  " + move["to"]["name"])


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else "KAN"

    print("OpenProject:")
    openproject()
    print()
    print("Taiga (" + fc.TAIGA_SLUG + "):")
    taiga()
    print()
    print("Jira (transitions available in project " + project + "):")
    jira(project)