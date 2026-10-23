# Verifica una user story: prende i criteri dal sistema di project management,
# prende il codice consegnato da GitHub, li mette insieme in una cartella
# temporanea ed esegue behave. Con --write riporta l'esito nel sistema, con
# --chain firma sulla blockchain che i test automatici sono passati.
#
#   python3 verify.py openproject 1115
#   python3 verify.py openproject 1115 --write
#   python3 verify.py openproject 1115 --write --chain
#   python3 verify.py openproject 1115 https://github.com/tizio/altro-repo
#
# Il repository si decide in quest'ordine: quello scritto sulla riga di comando,
# poi il campo Repository: nell'intestazione della user story, poi projects.json.

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import fetch_criteria
import report

# la cartella di questo script, dove vivono il vocabolario e la configurazione
VERIFIER = os.path.dirname(os.path.abspath(__file__))


def repository_for(system, project, body, requested):
    if requested:
        return requested

    written = re.search(r"^\s*Repository:\s*(\S+)\s*$", body, re.M)
    if written:
        return written.group(1)

    name = system + ":" + project
    try:
        with open(os.path.join(VERIFIER, "projects.json"), encoding="utf-8") as f:
            projects = json.load(f)
    except FileNotFoundError:
        projects = {}

    if name not in projects:
        print("No repository configured for \"" + name + "\"", file=sys.stderr)
        print("Add it to projects.json, or pass it on the command line.",
              file=sys.stderr)
        return None

    return projects[name]


def main():
    arguments = [a for a in sys.argv[1:] if not a.startswith("--")]
    write_back = "--write" in sys.argv
    sign_chain = "--chain" in sys.argv

    if len(arguments) < 2:
        print("Usage: verify.py <openproject|taiga|jira> <id> [repository] "
              "[--write] [--chain]", file=sys.stderr)
        return 2

    system, key = arguments[0], arguments[1]
    requested = arguments[2] if len(arguments) > 2 else None

    if system not in fetch_criteria.READERS:
        print("Unknown system: " + system, file=sys.stderr)
        return 2

    # --- i criteri, dal sistema di project management ---
    title, description, project = fetch_criteria.READERS[system](key)
    body = fetch_criteria.clean(description)

    if not re.search(r"^\s*Scenario", body, re.M):
        print("No acceptance criteria found in " + system + " " + key,
              file=sys.stderr)
        return 2

    repository = repository_for(system, project, body, requested)
    if repository is None:
        return 2

    work = tempfile.mkdtemp(prefix="verify-")
    try:
        # --- il codice, da GitHub ---
        code = os.path.join(work, "code")
        cloned = subprocess.run(["git", "clone", "--depth", "1", repository, code],
                                capture_output=True, text=True)
        if cloned.returncode != 0:
            print(cloned.stderr.strip(), file=sys.stderr)
            return 2

        # la forma corta serve a leggere, quella lunga va sulla blockchain
        revision = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                  cwd=code, capture_output=True, text=True)
        full_revision = subprocess.run(["git", "rev-parse", "HEAD"],
                                       cwd=code, capture_output=True, text=True)

        # --- il vocabolario, del sistema di verifica ---
        folder = os.path.join(work, "features")
        os.makedirs(os.path.join(folder, "steps"))
        shutil.copy(os.path.join(VERIFIER, "features", "environment.py"), folder)
        shutil.copy(os.path.join(VERIFIER, "features", "steps", "vocabulary.py"),
                    os.path.join(folder, "steps"))

        with open(os.path.join(folder, "story.feature"), "w", encoding="utf-8") as f:
            f.write("Feature: " + title + "\n\n" + body + "\n")

        # --- esecuzione ---
        environment = dict(os.environ, CODE_ROOT=code)
        outcome = os.path.join(work, "outcome.json")
        run = subprocess.run(["behave", "-f", "json", "-o", outcome],
                             cwd=work, env=environment,
                             capture_output=True, text=True)

        # se behave non riesce nemmeno a leggere i criteri non scrive il
        # resoconto: in quel caso il motivo sta nel suo output
        if not os.path.exists(outcome):
            print("behave could not run the criteria:", file=sys.stderr)
            print((run.stdout + run.stderr).strip(), file=sys.stderr)
            return 2

        text, passed = report.summary(outcome, [
            system + " " + key + " - " + title,
            "Repository: " + repository + " @ " + revision.stdout.strip(),
        ])
        print(text)

        # --- l'esito torna nel sistema di project management ---
        if write_back:
            report.write(system, key, project, text, passed)
            print()
            print("Written back to " + system + ".")

        # --- la firma sulla blockchain ---
        # Parte solo se tutti i criteri automatici sono passati: e' la prima
        # delle tre autorizzazioni al pagamento, le altre due restano umane.
        if sign_chain and passed:
            import blockchain

            story = re.search(r"^\s*Blockchain:\s*(\d+)\s*$", body, re.M)
            if story:
                print()
                blockchain.sign_tests(story.group(1),
                                      full_revision.stdout.strip())
            else:
                print()
                print("No Blockchain: field in the header, nothing signed")

        return 0 if passed else 1

    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())