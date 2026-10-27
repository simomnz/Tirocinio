# verifies a user story: takes the acceptance criteria from the project
# management system, takes the delivered code from GitHub, puts them together
# in a temporary folder and runs behave. With --write it reports the outcome
# back into the system, with --chain it records on the blockchain that the
# automated tests passed.
#
#   python3 verify.py openproject 1117
#   python3 verify.py openproject 1117 --write --chain
#   python3 verify.py --story 0 --write --chain
#
# With --story everything comes from the contract: which task the story maps
# to, and which commit the developer declared as the delivery.

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import fetch_criteria
import report

VERIFIER = os.path.dirname(os.path.abspath(__file__))   # this file's folder, where the vocabulary and the configuration live


# picks the repository holding the delivered code
def repository_for(system, project, body, requested):
    if requested:
        return requested                                # the one given on the command line wins

    written = re.search(r"^\s*Repository:\s*(\S+)\s*$", body, re.M)   # then the one written in the user story header
    if written:
        return written.group(1)                         # group(1) is the part inside the brackets

    name = system + ":" + project
    try:
        with open(os.path.join(VERIFIER, "projects.json"), encoding="utf-8") as f:
            projects = json.load(f)
    except FileNotFoundError:
        projects = {}                                   # a missing file is a configuration to do, not a failure

    if name not in projects:
        print("No repository configured for \"" + name + "\"", file=sys.stderr)
        print("Add it to projects.json, or pass it on the command line.",
              file=sys.stderr)
        return None

    return projects[name]


# brings the repository into the folder at the exact commit asked for.
# A shallow fetch of that single commit is tried first, because a full clone
# of a large repository is slow and almost all of it would be thrown away
def clone_at(repository, folder, commit):
    if commit:
        os.makedirs(folder)
        steps = [["git", "init", "--quiet", folder],
                 ["git", "-C", folder, "remote", "add", "origin", repository],
                 ["git", "-C", folder, "fetch", "--quiet", "--depth", "1", "origin", commit],
                 ["git", "-C", folder, "checkout", "--quiet", "FETCH_HEAD"]]
        ok = True
        for step in steps:
            if subprocess.run(step, capture_output=True, text=True).returncode != 0:
                ok = False
                break
        if ok:
            return True, ""
        shutil.rmtree(folder, ignore_errors=True)       # the fetch by commit was refused, fall back to a full clone

    done = subprocess.run(["git", "clone", "--quiet", repository, folder],
                          capture_output=True, text=True)
    if done.returncode != 0:
        return False, done.stderr.strip()

    if commit:
        done = subprocess.run(["git", "-C", folder, "checkout", "--quiet", commit],
                              capture_output=True, text=True)
        if done.returncode != 0:
            return False, "The declared commit is not in the repository: " + commit
    return True, ""


def main():
    arguments = [a for a in sys.argv[1:] if not a.startswith("--")]   # values and options kept apart, so their order does not matter
    write_back = "--write" in sys.argv
    sign_chain = "--chain" in sys.argv
    story_id = None

    if "--story" in sys.argv:                           # chain driven: the contract says what to verify
        position = sys.argv.index("--story") + 1
        if position >= len(sys.argv):
            print("--story needs the identifier on the chain", file=sys.stderr)
            return 2
        story_id = sys.argv[position]
        if story_id in arguments:
            arguments.remove(story_id)                  # it is a value, but it belongs to the option

    declared_commit = None
    requested = None

    if story_id is not None:
        import blockchain
        try:
            delivery = blockchain.get_delivery(story_id)
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 2
        system = delivery["system"]
        key = delivery["task"]
        declared_commit = delivery["commit"]
        print("User story " + str(story_id) + " on chain")
        print("  task     " + system + " " + key)
        print("  commit   " + declared_commit)
        print("  developer " + delivery["developer"])
        print()
    else:
        if len(arguments) < 2:
            print("Usage: verify.py <openproject|taiga|jira> <id> [repository] "
                  "[--write] [--chain]", file=sys.stderr)
            print("       verify.py --story <id> [--write] [--chain]", file=sys.stderr)
            return 2
        system, key = arguments[0], arguments[1]
        requested = arguments[2] if len(arguments) > 2 else None   # the repository is optional

    if system not in fetch_criteria.READERS:            # reuses the dictionary instead of repeating the list
        print("Unknown system: " + system, file=sys.stderr)
        return 2

    key = fetch_criteria.normalize(system, key)         # once only, the same identifier is used to write back as well

    # --- the criteria, from the project management system ---
    title, description, project = fetch_criteria.READERS[system](key)
    body = fetch_criteria.clean(description)

    if not re.search(r"^\s*Scenario", body, re.M):
        print("No acceptance criteria found in " + system + " " + key,
              file=sys.stderr)
        return 2

    repository = repository_for(system, project, body, requested)
    if repository is None:
        return 2

    work = tempfile.mkdtemp(prefix="verify-")           # everything lives here and is removed at the end
    try:
        # --- the code, from the repository, at the declared commit ---
        code = os.path.join(work, "code")
        ok, problem = clone_at(repository, code, declared_commit)
        if not ok:
            print(problem, file=sys.stderr)
            return 2

        revision = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                  cwd=code, capture_output=True, text=True)   # short form, for the report
        full_revision = subprocess.run(["git", "rev-parse", "HEAD"],
                                       cwd=code, capture_output=True, text=True)   # forty digits, for the chain

        # --- the vocabulary, from our own repository ---
        folder = os.path.join(work, "features")
        os.makedirs(os.path.join(folder, "steps"))      # behave expects exactly this layout
        shutil.copy(os.path.join(VERIFIER, "features", "environment.py"), folder)
        shutil.copy(os.path.join(VERIFIER, "features", "steps", "vocabulary.py"),
                    os.path.join(folder, "steps"))      # it comes from us, never from the delivered repository

        with open(os.path.join(folder, "story.feature"), "w", encoding="utf-8") as f:
            f.write("Feature: " + title + "\n\n" + body + "\n")

        # --- running ---
        environment = dict(os.environ, CODE_ROOT=code)  # tells the vocabulary where the code under test is
        outcome = os.path.join(work, "outcome.json")
        run = subprocess.run(["behave", "-f", "json", "-o", outcome],
                             cwd=work, env=environment,
                             capture_output=True, text=True)   # the json is read, not the screen output, which changes between versions

        if not os.path.exists(outcome):                 # no report means behave could not even read the criteria
            print("behave could not run the criteria:", file=sys.stderr)
            print((run.stdout + run.stderr).strip(), file=sys.stderr)
            return 2

        header = [system + " " + key + " - " + title,
                  "Repository: " + repository + " @ " + revision.stdout.strip()]
        if story_id is not None:
            header.append("User story " + str(story_id) + " on chain")

        text, passed = report.summary(outcome, header)
        print(text)

        # --- the outcome goes back into the project management system ---
        if write_back:
            report.write(system, key, project, text, passed)
            print()
            print("Written back to " + system + ".")

        # --- the record on the chain ---
        # only when every automated criterion passed: it is the first of the
        # three authorisations to payment, the other two stay human
        if sign_chain and passed:
            import blockchain

            target = story_id
            if target is None:                          # without --story the identifier is read from the header
                found = re.search(r"^\s*Blockchain:\s*(\d+)\s*$", body, re.M)
                target = found.group(1) if found else None

            print()
            if target is None:
                print("No Blockchain: field in the header, nothing recorded")
            else:
                blockchain.record_tests_passed(target, full_revision.stdout.strip())

        return 0 if passed else 1                       # 0 the criteria pass, 1 they do not, 2 the system could not even try

    finally:
        shutil.rmtree(work, ignore_errors=True)         # removed even when something failed halfway


if __name__ == "__main__":
    sys.exit(main())