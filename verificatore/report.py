# Turns the output of behave into text to write back into the project
# management systems, and works out the verdict while it is at it.

import json
import os
import urllib.error
import urllib.request
import fetch_criteria as fc
import re


VERIFIER = os.path.dirname(os.path.abspath(__file__))         # the folder of this file, where statuses.json lives


# calls an address with the method asked for and gives the answer back as JSON
def call(address, headers, data=None, method="GET"):
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
    else:
        payload = None

    sent = dict(headers)                                      # a copy, so it does not change the caller's dictionary
    if payload is not None:
        sent["Content-Type"] = "application/json"             # declared only when there really is a body

    request = urllib.request.Request(address, data=payload,
                                     headers=sent, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            text = response.read().decode("utf-8")
            if text:
                return json.loads(text)
            else:
                return None                                   # some answers are empty, like the PATCH of Taiga
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8")                 # the reason for the refusal is in the body, not in the status code
        raise RuntimeError(method + " " + address + " -> " +
                           str(error.code) + "\n" + detail) from None   # from None drops the second error chained onto this one


# signs in to Taiga and gives back the header ready to use
def taiga_login():
    body = {"type": "normal", "username": fc.TAIGA_USER, "password": fc.TAIGA_PASS}
    data = call(fc.TAIGA_URL + "/api/v1/auth", {}, body, "POST")
    return {"Authorization": "Bearer " + data["auth_token"]}



# The outcome, read from the sealed line the run sent back


# the lines that say why a scenario failed: for each step in it, the step
# itself and the message of the error. Only the step that stopped the run is
# in the outcome
def failure_lines(scenario):
    lines = []
    for item in scenario.get("steps", []):
        lines.append("      step:  " + item["keyword"] + " " + item["name"])

        said = str(item.get("error", ""))

        detail = []
        for line in said.split("\n"):
            line = line.strip()
            # behave calls it "Assertion Failed" when it reports the
            # error and "ASSERT FAILED" on screen, so the match
            # ignores case
            if re.match(r"^assert(ion)? failed:", line, re.I):
                detail.append(line.split(":", 1)[1].strip())   # throws the label away and keeps the message

        # a step that broke instead of failing an assertion has no
        # such line, and was reported as FAILED with nothing written
        # under it. The last line of what was raised is the one that
        # names the reason, so that is the one kept
        if not detail:
            last = ""
            for line in said.split("\n"):
                line = line.strip()
                if line:
                    last = line
            if last:
                detail.append(last)

        for line in detail:
            lines.append("      " + line)

    return lines


# works out both the text of the report and the verdict, from the outcome that
# came back sealed from the run. The boolean it returns is the most important
# value of this side of the system: it decides the exit code and whether
# anything is signed on chain
def summary(outcome, header):
    scenarios = outcome.get("scenarios", [])

    # whether a criterion is manual was decided while it ran, by the same
    # function that skipped it. It used to be worked out again here, from the
    # tags in the json of behave, and two answers for the same question is how
    # a @Manual came to be executed and counted among the manual ones at once
    manual = []
    automated = []
    for s in scenarios:
        if s.get("manual"):
            manual.append(s)
        else:
            automated.append(s)

    passed = []
    for s in automated:
        if s.get("status") == "passed":
            passed.append(s)

    # no automated criteria at all is not a pass. The comparison used to be
    # len(passed) == len(automated), which is true with both at zero as well:
    # a user story with every scenario @manual, or an Outline with no Examples,
    # came out all green and was signed on chain without one test having run
    all_green = len(automated) > 0 and len(passed) == len(automated)

    lines = list(header)
    lines.append("")
    lines.append("Automated criteria: " + str(len(passed)) + " of " +
                 str(len(automated)) + " passed")

    for scenario in automated:
        if scenario.get("status") == "passed":
            label = "OK"
        else:
            label = "FAILED"

        lines.append("  " + scenario["name"].ljust(44) + label)   # lines the outcomes up in a column

        if label == "FAILED":
            lines.extend(failure_lines(scenario))

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

    return "\n".join(lines), all_green                        # the bool decides the exit code and the signature on chain


# Writing back into the three systems

# looks in statuses.json for the status to move the task to
def target_status(system, project, passed):
    with open(os.path.join(VERIFIER, "statuses.json"), encoding="utf-8") as f:
        statuses = json.load(f)

    name = system + ":" + project                             # a composed key, like openproject:Prova
    if name not in statuses:
        return None                                           # a project nobody configured, handled by write
    if passed:
        return statuses[name]["passed"]
    else:
        return statuses[name]["failed"]


# writes the comment and changes the status on OpenProject
def to_openproject(key, text, status):
    headers = fc.basic("apikey", fc.OP_TOKEN)
    base = fc.OP_URL + "/api/v3/work_packages/" + key
    call(base + "/activities", headers, {"comment": {"raw": "```\n" + text + "\n```"}}, "POST")   # keeps the columns lined up

    current = call(base, headers)                             # reads the version
    call(base, headers, {
        "lockVersion": current["lockVersion"],                # if somebody touched the task in the meantime it refuses instead of overwriting
        "_links": {"status": {"href": "/api/v3/statuses/" + str(status)}}
    }, "PATCH")


# writes the comment and changes the status on Taiga
def to_taiga(key, text, status):
    headers = taiga_login()
    story = call(fc.TAIGA_URL + "/api/v1/userstories/by_ref?ref=" + key +   # the internal identifier is needed, and by_ref works it out from the visible number
                 "&project__slug=" + fc.TAIGA_SLUG, headers)

    call(fc.TAIGA_URL + "/api/v1/userstories/" + str(story["id"]), headers, {
        "version": story["version"],                          # same check as OpenProject
        "status": status,
        "comment": "```\n" + text + "\n```"                   # comment and status in the same request
    }, "PATCH")


# writes the comment and runs the transition on Jira
def to_jira(key, text, status):
    headers = fc.basic(fc.JIRA_USER, fc.JIRA_TOKEN)
    base = fc.JIRA_URL + "/rest/api/2/issue/" + key

    call(base + "/comment", headers,
         {"body": "{noformat}\n" + text + "\n{noformat}"}, "POST")   # Jira uses {noformat} where the others use backticks

    call(base + "/transitions", headers, {"transition": {"id": str(status)}}, "POST")   # here a status is not set, a transition is run


# ties each system to the function that writes into it
WRITERS = {"openproject": to_openproject, "taiga": to_taiga, "jira": to_jira}


# picks the status to move to and writes into the right system
def write(system, key, project, text, passed):
    status = target_status(system, project, passed)
    if status is None:
        print("No status configured for \"" + system + ":" + project + "\"")
        return                                                # leaves without writing, instead of failing
    WRITERS[system](key, text, status)