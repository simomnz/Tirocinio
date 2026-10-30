# verifies a user story: takes the acceptance criteria from the project
# management system, takes the delivered code from GitHub, puts them together
# in a temporary folder and runs behave. With --write it reports the outcome
# back into the system, with --chain it records on the blockchain that the
# automated tests passed.
#
#   python3 verify.py openproject 1117
#   python3 verify.py openproject 1117 --write --chain
#   python3 verify.py --story 0 --write --chain
#   python3 verify.py openproject 1117 --hash
#
# With --story everything comes from the contract: which task the story maps
# to, and which commit the developer declared as the delivery.
#
# What it answers with:
#   0  the automated criteria passed
#   1  the delivery was refused, and that is an answer about the delivery
#   2  it could not try, and trying again may work: this one stays in the queue
#   3  it will never work as things stand, and somebody has to go and fix
#      something. Retrying is pointless, so the delivery is not left in the
#      queue: before, these came back as 2 and Jenkins went red at every round
#      for ever without anybody being told why

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

RUNNER = os.environ.get("VERIFY_RUNNER", "docker")      # podman takes the same arguments
IMAGE = os.environ.get("VERIFY_IMAGE", "criteria-sandbox:1")
TIMEOUT = int(os.environ.get("VERIFY_TIMEOUT", "600"))  # seconds, against a delivery that never ends
SANDBOX = os.environ.get("VERIFY_SANDBOX", "on") != "off"   # off runs on this machine, for trying things out only


# the shapes of address git may be sent to. Anything else is refused, because
# git reads some of them as a command to run: "ext::sh -c ..." executes on this
# machine, and the address arrives from the description of a task, which is not
# ours. The clone happens before any container exists, so nothing else guards
# this: here is the only place it can be stopped
ALLOWED_REPOSITORY = re.compile(r"^(https://[\w.-]+/[\w./~-]+|git@[\w.-]+:[\w./~-]+)$")


# true when git may be pointed at this address
def repository_allowed(repository):
    if ALLOWED_REPOSITORY.match(repository):
        return True

    print("Repository address not allowed: " + repr(repository), file=sys.stderr)
    print("Only https://host/path and git@host:path are accepted. Other forms, "
          "such as ext:: or file://, make git run commands on this machine.",
          file=sys.stderr)
    return False


# picks the repository holding the delivered code. Every way in goes through
# repository_allowed, so no source of the address can skip the check
def repository_for(system, project, body, requested):
    if requested:
        chosen = requested                              # the one given on the command line wins
    else:
        written = re.search(r"^\s*Repository:\s*(\S+)\s*$", body, re.M)   # then the one written in the user story header
        if written:
            chosen = written.group(1)                   # group(1) is the part inside the brackets
        else:
            name = system + ":" + project
            try:
                with open(os.path.join(VERIFIER, "projects.json"), encoding="utf-8") as f:
                    projects = json.load(f)
            except FileNotFoundError:
                projects = {}                           # a missing file is a configuration to do, not a failure

            if name not in projects:
                print("No repository configured for \"" + name + "\"", file=sys.stderr)
                print("Add it to projects.json, or pass it on the command line.",
                      file=sys.stderr)
                return None

            chosen = projects[name]

    return chosen if repository_allowed(chosen) else None


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


# runs the criteria inside a throwaway container. The delivered code is
# written by somebody else and is run here, so it gets a machine of its own:
# no network out, no privileges, a time and memory ceiling, and nothing of
# ours to reach.
#
# Three separate folders, and not one: the criteria and our vocabulary go in
# read only, so the code being judged cannot rewrite the questions; the
# delivered code goes in read only on a path of its own; and the only writable
# mount holds the outcome. Before, all three lived in the same writable tree,
# so the delivered code sat next to the file that holds its own verdict
def run_in_sandbox(run_dir, code, out_dir):
    name = "verify-" + str(os.getpid())
    command = [
        RUNNER, "run", "--rm", "--name", name,
        "--network", "none",                            # loopback still works, the outside does not
        "--user", str(os.getuid()) + ":" + str(os.getgid()),   # the files it writes belong to us, not to root
        "--memory", "512m", "--cpus", "1", "--pids-limit", "256",

        # nothing the delivered code could ask the kernel for is left granted,
        # and it cannot gain anything it was not given at the start
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",

        # the image itself cannot be changed, and the one writable place it is
        # left cannot be used to run a program from
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",

        # Z relabels the folder for SELinux, which otherwise denies the container
        "--volume", run_dir + ":/run:ro,Z",             # the criteria and the vocabulary
        "--volume", code + ":/code:ro,Z",               # the delivered code, which has nothing to write here
        "--volume", out_dir + ":/out:rw,Z",             # the outcome, the only thing that comes back

        "--workdir", "/run",
        "--env", "CODE_ROOT=/code",                     # the path inside the container, not the one outside
        "--env", "HOME=/tmp",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        IMAGE,
        "behave", "-f", "json", "-o", "/out/outcome.json",
    ]

    try:
        return subprocess.run(command, capture_output=True, text=True,
                              timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        subprocess.run([RUNNER, "kill", name], capture_output=True)   # the container outlives the client that started it
        return subprocess.CompletedProcess(
            command, 1, "",
            "The criteria did not finish within " + str(TIMEOUT) + " seconds")


# runs them straight on this machine. Only for trying things out: here the
# delivered code has whatever the user running it has
def run_without_sandbox(run_dir, code, out_dir):
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),     # kept: Python finds the installed packages starting from here
        "LANG": os.environ.get("LANG", "C.UTF-8"),  # without it Python reads the files as ASCII
        "CODE_ROOT": code,
    }
    return subprocess.run(["behave", "-f", "json",
                           "-o", os.path.join(out_dir, "outcome.json")],
                          cwd=run_dir, env=environment,
                          capture_output=True, text=True, timeout=TIMEOUT)


def main():
    arguments = [a for a in sys.argv[1:] if not a.startswith("--")]   # values and options kept apart, so their order does not matter
    write_back = "--write" in sys.argv
    sign_chain = "--chain" in sys.argv
    print_hash = "--hash" in sys.argv               # prints the fingerprint of the criteria and stops
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
    frozen_criteria = None
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
        frozen_criteria = delivery["criteriaHash"]
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
        return 3                                        # no number of retries turns this into a known system

    key = fetch_criteria.normalize(system, key)         # once only, the same identifier is used to write back as well

    # --- the criteria, from the project management system ---
    title, description, project = fetch_criteria.READERS[system](key)
    body = fetch_criteria.clean(description)

    if not re.search(r"^\s*Scenario", body, re.M):
        print("No acceptance criteria found in " + system + " " + key,
              file=sys.stderr)
        print("Somebody has to write them in the task: this is not a delivery "
              "that failed.", file=sys.stderr)
        return 3                                        # a task with no criteria will not grow any by itself

    if print_hash:                                  # what the product owner freezes with setCriteriaHash
        import blockchain
        print(blockchain.prefixed(blockchain.criteria_hash(body)))
        return 0

    # the criteria are checked before anything else happens: nothing is cloned,
    # nothing is run and nothing is written back for a delivery that is going
    # to be refused anyway
    if frozen_criteria is not None:
        import blockchain
        running = blockchain.criteria_hash(body)
        if running != frozen_criteria:
            print("These are not the criteria agreed on chain", file=sys.stderr)
            print("  agreed " + blockchain.prefixed(frozen_criteria), file=sys.stderr)
            print("  found  " + blockchain.prefixed(running), file=sys.stderr)
            print("The text in the task was changed after it was frozen: until "
                  "somebody puts it back, or the user story is reopened with "
                  "the new criteria, this delivery cannot be verified.",
                  file=sys.stderr)
            return 3                                    # the text will not go back on its own

    repository = repository_for(system, project, body, requested)
    if repository is None:
        return 3                                        # a missing configuration, not a passing failure

    work = tempfile.mkdtemp(prefix="verify-")           # everything lives here and is removed at the end
    try:
        # three folders, kept apart so the container can mount them with
        # different rights: ours to read, the delivery to read, the outcome to write
        code = os.path.join(work, "code")               # the delivered code
        run_dir = os.path.join(work, "run")             # the criteria and our vocabulary
        out_dir = os.path.join(work, "out")             # what comes back
        os.makedirs(out_dir)

        header = [system + " " + key + " - " + title]
        if story_id is not None:
            header.append("User story " + str(story_id) + " on chain")

        # --- the code, from the repository, at the declared commit ---
        ok, problem = clone_at(repository, code, declared_commit)
        if not ok:
            # a commit that is not in the repository is an invalid delivery,
            # not a breakdown of this system: it is refused once and said out
            # loud. Returning 2 left it in the queue, so Jenkins retried it at
            # every round for ever and the developer was never told
            print(problem, file=sys.stderr)
            if write_back:
                report.write(system, key, project,
                             "\n".join(header + ["", "Status: rejected, " + problem]),
                             False)
                print("Written back to " + system + ".")
            return 1

        revision = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                  cwd=code, capture_output=True, text=True)   # short form, for the report
        full_revision = subprocess.run(["git", "rev-parse", "HEAD"],
                                       cwd=code, capture_output=True, text=True)   # forty digits, for the chain

        header.insert(1, "Repository: " + repository + " @ " + revision.stdout.strip())

        # --- the vocabulary, from our own repository ---
        folder = os.path.join(run_dir, "features")
        os.makedirs(os.path.join(folder, "steps"))      # behave expects exactly this layout
        shutil.copy(os.path.join(VERIFIER, "features", "environment.py"), folder)
        shutil.copy(os.path.join(VERIFIER, "features", "steps", "vocabulary.py"),
                    os.path.join(folder, "steps"))      # it comes from us, never from the delivered repository

        with open(os.path.join(folder, "story.feature"), "w", encoding="utf-8") as f:
            f.write("Feature: " + title + "\n\n" + body + "\n")

        # --- running ---
        outcome = os.path.join(out_dir, "outcome.json")
        if SANDBOX:
            run = run_in_sandbox(run_dir, code, out_dir)
        else:
            run = run_without_sandbox(run_dir, code, out_dir)   # the json is read, not the screen output, which changes between versions

        if not os.path.exists(outcome):                 # no report means behave could not even read the criteria
            print("behave could not run the criteria:", file=sys.stderr)
            print((run.stdout + run.stderr).strip(), file=sys.stderr)
            return 2

        text, passed = report.summary(outcome, header)
        print(text)

        # behave answers zero only when every scenario it ran passed, so a
        # green report next to a non-zero exit code means the two do not
        # describe the same run. Nothing is signed on a disagreement: the
        # outcome file is the one thing the delivered code could get at
        if passed and run.returncode != 0:
            print("The report says the criteria passed but the run ended with "
                  + str(run.returncode) + ": nothing is recorded",
                  file=sys.stderr)
            print((run.stdout + run.stderr).strip()[-2000:], file=sys.stderr)
            return 2

        # --- the record on the chain ---
        # only when every automated criterion passed: it is the first of the
        # three authorisations to payment, the other two stay human.
        #
        # It goes first, and the report after: the other way round a project
        # management system that was down took the signature with it, and the
        # tests had passed. The fact belongs on the chain, the report is the
        # account of it
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
                blockchain.record_tests_passed(target, full_revision.stdout.strip(),
                                               blockchain.criteria_hash(body))   # the very text that was run

        # --- the outcome goes back into the project management system ---
        if write_back:
            report.write(system, key, project, text, passed)
            print()
            print("Written back to " + system + ".")

        return 0 if passed else 1                       # 0 the criteria pass, 1 they do not, 2 the system could not even try

    finally:
        shutil.rmtree(work, ignore_errors=True)         # removed even when something failed halfway


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:                 # a crash is not a rejected delivery: it is 2, so it gets looked at
        print(str(error), file=sys.stderr)
        sys.exit(2)
