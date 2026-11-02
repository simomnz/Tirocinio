# Prints every status of the three systems, to find the ids that go into
# statuses.json. Those ids are not guessable and differ from one installation
# to the next, so they are read from the systems themselves.

import json
import sys

import fetch_criteria as fc                                    # reuses its addresses, credentials and the get and basic functions


# prints the statuses of OpenProject, which are the same for the whole instance
def openproject():
    data = fc.get(fc.OP_URL + "/api/v3/statuses", fc.basic("apikey", fc.OP_TOKEN))
    for status in data["_embedded"]["elements"]:                  # in the HAL format the collections sit inside _embedded
        if status.get("isClosed"):                               # tells the final statuses from the ones in between
            closed = "  (closed)"
        else:
            closed = ""

        print("  " + str(status["id"]) + "  " + status["name"] + closed)


# prints the statuses of Taiga, which belong to the single project
def taiga():
    body = json.dumps({"type": "normal",
                       "username": fc.TAIGA_USER,
                       "password": fc.TAIGA_PASS}).encode("utf-8")
    session = fc.get(fc.TAIGA_URL + "/api/v1/auth",
                     {"Content-Type": "application/json"}, body)   # signs in and gets the token
    headers = {"Authorization": "Bearer " + session["auth_token"]}

    project = fc.get(fc.TAIGA_URL + "/api/v1/projects/by_slug?slug=" + fc.TAIGA_SLUG,
                     headers)
    for status in project["us_statuses"]:                      # the statuses arrive inside the project
        if status.get("is_closed"):
            closed = "  (closed)"
        else:
            closed = ""

        print("  " + str(status["id"]) + "  " + status["name"] + closed)


# prints the transitions of Jira, which depend on the single issue and on the
# status it is sitting in right now
def jira(project):
    found = fc.get(fc.JIRA_URL + "/rest/api/2/search/jql?maxResults=1&fields=key&jql=project%3D" +
                   project, fc.basic(fc.JIRA_USER, fc.JIRA_TOKEN))   # /search/jql
    issues = found.get("issues", [])                           # an empty list instead of an error when the key is missing
    if not issues:
        print("  no issues in project " + project)
        return

    sample = issues[0]["key"]
    print("  (sample issue: " + sample + ")")                  # the list holds from the status this issue is in

    data = fc.get(fc.JIRA_URL + "/rest/api/2/issue/" + sample + "/transitions",
                  fc.basic(fc.JIRA_USER, fc.JIRA_TOKEN))
    for move in data["transitions"]:
        print("  " + move["id"] + "  " + move["name"] + "  ->  " + move["to"]["name"])   # the id to put in statuses.json is the transition's, not the status'


if __name__ == "__main__":
    if len(sys.argv) > 1:                                      # falls back to KAN when no project is given
        project = sys.argv[1]
    else:
        project = "KAN"

    print("OpenProject:")
    openproject()
    print()
    print("Taiga (" + fc.TAIGA_SLUG + "):")
    taiga()
    print()
    print("Jira (transitions available in project " + project + "):")
    jira(project)