# Reads the user story from the project management system and saves the
# acceptance criteria as a .feature file. The fingerprint the contract freezes
# is computed on the text that clean() returns down below, so whatever this
# file does to that text is part of the agreement.

import base64
import html
import json
import os
import re
import sys
import urllib.request

# Credentials, all of them from the environment so nothing is written here
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


# calls an address and gives the answer back read as JSON
def get(address, headers=None, data=None):
    request = urllib.request.Request(address, data=data, headers=headers or {})   # sends a POST when data is filled in, a GET otherwise
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


# the authentication header built from a user and a secret
def basic(user, secret):
    pair = (user + ":" + secret).encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(pair).decode("ascii")}   


# adds the project tag that Jira wants in front of the number, so that the
# task can be named as 12 instead of KAN-12 on the command line
def normalize(system, key):
    if system == "jira" and "-" not in key:
        return JIRA_PROJECT + "-" + key
    return key



# reads the user story from OpenProject
def from_openproject(key):
    data = get(OP_URL + "/api/v3/work_packages/" + key, basic("apikey", OP_TOKEN))   # a fixed user "apikey" with the token as the password
    return (data["subject"],
            data["description"]["raw"],                        # the raw text as the product owner typed it
            data["_links"]["project"]["title"])


# reads the user story from Taiga
def from_taiga(key):
    body = json.dumps({"type": "normal",
                       "username": TAIGA_USER,
                       "password": TAIGA_PASS}).encode("utf-8")
    session = get(TAIGA_URL + "/api/v1/auth",
                  {"Content-Type": "application/json"}, body)  # a token good for this run only

    data = get(TAIGA_URL + "/api/v1/userstories/by_ref?ref=" + key +   # looked up by the number the task shows
               "&project__slug=" + TAIGA_SLUG,
               {"Authorization": "Bearer " + session["auth_token"]})
    return data["subject"], data["description"] or "", TAIGA_SLUG     # a missing description becomes an empty string


# reads the user story from Jira, through version 2 of the API and not
# version 3. Version 3 gives the description back as a tree of nodes, version
# 2 gives it back as text, and a fingerprint can only be taken over text

def from_jira(key):
    data = get(JIRA_URL + "/rest/api/2/issue/" + key, basic(JIRA_USER, JIRA_TOKEN))
    return (data["fields"]["summary"],
            data["fields"]["description"] or "",
            key.split("-")[0])                                 # takes KAN out of KAN-number


# ties each system to the function that reads from it. Reused elsewhere as the
# list of the systems that are known, instead of writing that list twice
READERS = {"openproject": from_openproject,
           "taiga": from_taiga,
           "jira": from_jira}



# Cleaning the text


# takes out the decorations the three systems add around the same text, so
# that one user story written in any of them comes out as the same bytes.
# Without this the same criteria would have a different fingerprint depending
# on where they were written.
#
# The system has to be named, because one of the steps below belongs to
# OpenProject alone. Left unsaid, nothing is unescaped: a caller that does not
# know where the text came from must not guess
def clean(text, system=None):
    text = html.unescape(text)                                # turns the HTML entities back into characters

    lines = []
    for line in text.split("\n"):
        
        # skips the opening and closing line of a code block, both ``` and ```gherkin
        
        if re.match(r"^\s*`{3,}\w*\s*$", line):
            continue

        # skips the HTML line break OpenProject puts where an empty line was
        if re.match(r"^\s*<br\s*/?>\s*$", line):               # accepts both <br> and <br/>
            continue

        line = line.replace("{noformat}", "")                  # takes out the block marking of Jira

        line = line.rstrip()                                   # drops the trailing spaces

        # OpenProject stores its descriptions as markdown, so the characters
        # that mean something there come back with a backslash in front of
        # them. A header line written as Module: web_US.py arrives as
        # Module: web\_US.py, and that path does not exist. Only these five
        # are unescaped: \n has to survive, because the criteria use it to
        # write a newline inside a file.
        #
        # OpenProject only, because it is the only one that puts those
        # backslashes there. Taiga and Jira hand back the text as the product
        # owner typed it, so a backslash in it is one he wrote and means
        # something: the criterion matches "\[ok\]" is a regular expression
        # looking for square brackets, and unescaping it turns it into a
        # character class that matches any o or k. "\*\*" stops being a
        # regular expression at all and raises, so a correct delivery is
        # refused
        if system == "openproject":
            line = re.sub(r"\\([_*`\[\]])", r"\1", line)

        lines.append(line)

    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")         # brings runs of empty lines down to two, so all three come out the same


def main():
    if len(sys.argv) < 3:
        print("Usage: fetch_criteria.py <openproject|taiga|jira> <id>",
              file=sys.stderr)                                 # the errors go on stderr
        return 1

    system, key = sys.argv[1], sys.argv[2]
    key = normalize(system, key)                               # the system and the key of the task
    
    if system not in READERS:
        print("Unknown system: " + system, file=sys.stderr)
        return 1

    title, description, project = READERS[system](key)         # picks the system out of the dictionary and calls it
    body = clean(description, system)

    if not re.search(r"^\s*Scenario", body, re.M):             # stops when there is not even one Scenario to run
        print("No acceptance criteria found in " + system + " " + key,
              file=sys.stderr)
        return 1

    name = re.sub(r"[^A-Za-z0-9-]+", "-", title).strip("-")    # turns the title into a file name
    path = os.path.join("features", system + "-" + name + ".feature")   # the system goes in front of the name
    
    os.makedirs("features", exist_ok=True)                     # creates the folder only when it is not there already
    with open(path, "w", encoding="utf-8") as f:
        f.write("Feature: " + title + "\n\n" + body + "\n")    # the Feature line is built from the title of the task

    count = len(re.findall(r"^\s*Scenario", body, re.M))       # counts the Scenario lines that were found
    print("Written " + path + " (" + str(count) + " scenarios)")
    return 0


if __name__ == "__main__":                                    
    sys.exit(main())                                           