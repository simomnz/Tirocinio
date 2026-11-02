# verifies a user story: takes the acceptance criteria from the project
# management system, takes the delivered code from GitHub, puts them together
# in a temporary folder and runs behave. With --write it reports the outcome
# back into the system, with --chain it records on the blockchain that the
# automated tests passed.
#
#   python3 verify.py openproject 1117
#   python3 verify.py openproject 1117 --write
#   python3 verify.py --story 0 --write --chain
#   python3 verify.py openproject 1117 --hash
#
# --chain needs --story: which user story a delivery belongs to is written on
# the chain and nowhere else.
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
import secrets
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

# what the run answers when it was stopped instead of finishing. 124 is the
# number the timeout command uses, and any number does as long as it cannot be
# one the criteria themselves could answer: it tells a delivery that never ends
# apart from a breakdown of this system, and only the first of the two is the
# developer's business
EXPIRED = 124


# the shapes of address git may be sent to. Anything else is refused, because
# git reads some of them as a command to run: "ext::sh -c ..." executes on this
# machine, and the address arrives from the description of a task, which is not
# ours. The clone happens before any container exists, so nothing else guards
# this: here is the only place it can be stopped
ALLOWED_REPOSITORY = re.compile(r"^(https://[\w.-]+/[\w./~-]+|git@[\w.-]+:[\w./~-]+)$")

# the mark the run puts in front of the outcome, the same string environment.py
# writes. It is followed by the secret of the run, so a line can be read only
# if it was written by our own code
MARKER = "__VERIFY_OUTCOME__"


# picks the outcome out of everything the run printed. Only a line carrying the
# secret of this run is read: the delivered code writes on the same stream, but
# the secret went in on a standard input that was emptied before the first
# criterion started, so it never reached it.
#
# None means there is no outcome to believe, and that is never a refused
# delivery: it is this system that could not answer
def sealed_outcome(output, nonce):
    if not nonce:
        return None                     # without a secret any line would do, and that is no check at all

    found = None
    for line in output.split("\n"):
        if line.startswith(MARKER + nonce):
            found = line[len(MARKER) + len(nonce):]   # the last one, as the answer is written once and at the end

    if found is None:
        return None
    try:
        return json.loads(found)
    except ValueError:
        return None


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

    if repository_allowed(chosen):
        return chosen
    else:
        return None


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
# Two folders, both read only: the criteria and our vocabulary on one side, so
# the code being judged cannot rewrite the questions, and the delivered code on
# a path of its own. There is no writable mount at all. There used to be one,
# for the outcome, and that was the last thing the delivered code could still
# get at: same container, same user, so it could rewrite the verdict on itself.
# The outcome comes back on standard output instead, marked with the secret
# that goes in on standard input
def run_in_sandbox(run_dir, code, nonce):
    name = "verify-" + str(os.getpid())
    command = [
        RUNNER, "run", "--rm", "--name", name,
        "--interactive",                                # stdin stays open, which is how the secret gets in
        "--network", "none",                            # loopback still works, the outside does not
        "--user", str(os.getuid()) + ":" + str(os.getgid()),   # the files it writes belong to us, not to root
        "--memory", "512m", "--cpus", "1", "--pids-limit", "256",

        # nothing the delivered code could ask the kernel for is left granted,
        # and it cannot gain anything it was not given at the start
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",

        # the image itself cannot be changed, and the one writable place it is
        # left is a throwaway that cannot be used to run a program from. It
        # goes away with the container, so nothing written there comes back
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",

        # Z relabels the folder for SELinux, which otherwise denies the container
        "--volume", run_dir + ":/run:ro,Z",             # the criteria and the vocabulary
        "--volume", code + ":/code:ro,Z",               # the delivered code, which has nothing to write here

        "--workdir", "/run",
        "--env", "CODE_ROOT=/code",                     # the path inside the container, not the one outside
        "--env", "HOME=/tmp",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        IMAGE,
        "behave", "-f", "plain",                        # on screen only, for when something has to be looked at
    ]

    try:
        return subprocess.run(command, input=nonce, capture_output=True,
                              text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        subprocess.run([RUNNER, "kill", name], capture_output=True)   # the container outlives the client that started it
        return subprocess.CompletedProcess(
            command, EXPIRED, "",
            "The criteria did not finish within " + str(TIMEOUT) + " seconds")


# runs them straight on this machine. Only for trying things out: here the
# delivered code has whatever the user running it has
def run_without_sandbox(run_dir, code, nonce):
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),     # kept: Python finds the installed packages starting from here
        "LANG": os.environ.get("LANG", "C.UTF-8"),  # without it Python reads the files as ASCII
        "CODE_ROOT": code,
    }
    try:
        return subprocess.run(["behave", "-f", "plain"],
                              cwd=run_dir, env=environment, input=nonce,
                              capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:         # answered the same way as the sandbox, or the two paths would disagree
        return subprocess.CompletedProcess(
            ["behave"], EXPIRED, "",
            "The criteria did not finish within " + str(TIMEOUT) + " seconds")


def main():
    # values and options kept apart, so their order does not matter
    arguments = []
    for a in sys.argv[1:]:
        if not a.startswith("--"):
            arguments.append(a)

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
                  "[--write]", file=sys.stderr)
            print("       verify.py --story <id> [--write] [--chain]", file=sys.stderr)
            return 2
        system, key = arguments[0], arguments[1]
        if len(arguments) > 2:                                     # the repository is optional
            requested = arguments[2]
        else:
            requested = None

    # said now and not at the end. It used to print a line and answer 0, so a
    # pipeline asking for a signature it never got was told everything went
    # well
    if sign_chain and story_id is None:
        print("--chain needs --story: which user story this is comes from the "
              "chain and from nowhere else", file=sys.stderr)
        return 2

    if system not in fetch_criteria.READERS:            # reuses the dictionary instead of repeating the list
        print("Unknown system: " + system, file=sys.stderr)
        return 3                                        # no number of retries turns this into a known system

    key = fetch_criteria.normalize(system, key)         # once only, the same identifier is used to write back as well

    # --- the criteria, from the project management system ---
    title, description, project = fetch_criteria.READERS[system](key)
    body = fetch_criteria.clean(description, system)

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
        # two folders, kept apart so the container can mount each one read
        # only on a path of its own: ours and the delivery's. Nothing is
        # mounted writable, and the outcome comes back on standard output
        code = os.path.join(work, "code")               # the delivered code
        run_dir = os.path.join(work, "run")             # the criteria and our vocabulary

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
        # the secret of this run, made here and never written to disk. It is
        # what tells our own answer apart from anything the delivered code
        # prints on the same stream
        nonce = secrets.token_hex(32)

        if SANDBOX:
            run = run_in_sandbox(run_dir, code, nonce)
        else:
            run = run_without_sandbox(run_dir, code, nonce)

        outcome = sealed_outcome(run.stdout, nonce)
        if outcome is None:                             # no sealed answer: behave did not get to the end of the criteria
            # a delivery that never ends, or that eats the machine until the
            # kernel stops it, is an invalid delivery and not a breakdown of
            # this system. It used to come back as 2, so nothing was written
            # anywhere, the user story stayed in the queue, and the next round
            # ran into the same wall: a red build for ever and a developer who
            # was never told why. The outcome cannot be sealed in these two
            # cases, because the line comes out at the end of the criteria and
            # the criteria never got there
            stopped = None
            if run.returncode == EXPIRED:
                stopped = run.stderr.strip()
            elif run.returncode == 137:                 # 128 + SIGKILL: the container was killed from outside
                stopped = ("The criteria did not finish: the container was "
                           "killed, which is what the memory and process "
                           "limits do")

            if stopped is not None:
                print(stopped, file=sys.stderr)
                if write_back:
                    report.write(system, key, project,
                                 "\n".join(header + ["", "Status: rejected, " + stopped]),
                                 False)
                    print("Written back to " + system + ".")
                return 1

            # anything else is this system that could not answer, and saying so
            # to the developer would blame him for our own breakage
            print("The run did not send back a sealed outcome:", file=sys.stderr)
            print((run.stdout + run.stderr).strip()[-2000:], file=sys.stderr)
            return 2

        text, passed = report.summary(outcome, header)
        print(text)

        # behave answers zero only when every scenario it ran passed, so a
        # green report next to a non-zero exit code means the two do not
        # describe the same run. Nothing is signed on a disagreement
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
        # which user story this is comes from the chain and from nowhere else.
        # It used to be possible to name it in the header of the task, with a
        # Blockchain: line, and that was a way in for the wrong number: the
        # task says what has to be done, the contract says who is working on
        # what. setExternalRef ties the two together, and reading it back is
        # what --story does
        if sign_chain and passed:
            import blockchain

            print()
            blockchain.record_tests_passed(story_id, full_revision.stdout.strip(),
                                           blockchain.criteria_hash(body))   # the very text that was run

        # --- the outcome goes back into the project management system ---
        if write_back:
            report.write(system, key, project, text, passed)
            print()
            print("Written back to " + system + ".")

        # 0 the criteria pass, 1 they do not, 2 the system could not even try
        if passed:
            return 0
        else:
            return 1

    finally:
        shutil.rmtree(work, ignore_errors=True)         # removed even when something failed halfway


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:                 # a crash is not a rejected delivery: it is 2, so it gets looked at
        print(str(error), file=sys.stderr)
        sys.exit(2)
