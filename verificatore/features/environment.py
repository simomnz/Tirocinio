# Set-up and clean-up around every scenario, and the sealed outcome of the run.
#
# The outcome used to be the json report of behave, written into a folder that
# had to be mounted writable so that it could come back out of the container.
# The delivered code runs in that same container and under the same user, so
# that file was within its reach: a delivery could rewrite the verdict on
# itself. Nothing writable is shared any more. The outcome leaves on standard
# output, on a single line marked with a secret that arrives on standard input
# before the first scenario starts and is never written anywhere. The
# delivered code can write on the same stream, but it cannot produce that mark.

import ctypes
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

MARKER = "__VERIFY_OUTCOME__"

PR_SET_DUMPABLE = 4
PR_GET_DUMPABLE = 3


# shuts this process to anybody looking in from outside.
#
# A secret kept in memory is only a secret while nobody can read that memory.
# The delivered code runs as a child of this process and under the same user,
# and that is enough to attach to it: measured inside the hardened container,
# a child attached to its parent and found the mark in its memory on the first
# try. Capabilities were already all dropped, which does not help, because
# between two processes of the same user the kernel asks for no privilege.
#
# Lowering the dump flag is what changes that. From here on the kernel hands
# /proc/<pid>/mem, maps, environ and fd of this process to root, and asks for
# a privilege that this container does not have. It also closes the way into
# the stream this process writes the outcome on.
#
# It is checked and not merely asked for: if it did not take, the mark is
# readable, and a verification that cannot keep its own secret must stop
# rather than sign something.
#
# required says whether an outcome will have to be sealed. It is true for
# every real verification, where the secret arrives on standard input. It is
# false when behave is run by hand with nobody listening: there is no secret
# to protect, so a machine without this call, one that is not Linux or does
# not carry glibc, can still be used to try the criteria out
def close_to_outsiders(required):
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)
        closed = libc.prctl(PR_GET_DUMPABLE, 0, 0, 0, 0) == 0
    except Exception:
        closed = False              # no libc.so.6, or no prctl: not a Linux with glibc

    if closed:
        return

    if required:
        raise RuntimeError(
            "this process could not be closed to the code it is judging: "
            "the outcome of the run would not be trustworthy")

    print("Warning: this process could not be closed to the code it is "
          "judging. No outcome is being sealed, so nothing is signed on it.",
          file=sys.stderr)

NONCE = ""                  # the secret of this run, read once from stdin
STDOUT = None               # the real descriptor 1, kept aside
SCENARIOS = []              # one entry per scenario, in the order they ran


# the tags are compared in lower case. @Manual did not match "manual", so it
# was executed as if it were an automated criterion while the report counted it
# among the ones to be checked by hand: two answers for the same scenario
def is_manual(scenario):
    for tag in scenario.tags:
        if tag.lower() == "manual":
            return True
    return False


# what the report needs out of one scenario, and nothing more. Keeping our own
# shape here, instead of reading the json of behave later, means the outcome
# does not change shape when behave changes its own, and that the manual mark
# is worked out in one place only
def collected(scenario):
    steps = []

    # all_steps and not steps: the second one holds the scenario's own steps
    # and leaves out the ones of a Background, which run first and can fail
    # just as well. A Background that broke arrived at the report as FAILED
    # with nothing written under it
    for step in scenario.all_steps:
        # behave keeps two different words apart: failed is a criterion whose
        # assertion did not hold, error is a step that broke outright, for
        # instance because nothing answered at the address. Only the first was
        # being carried, so a step that broke was reported with no reason
        # under it at all
        if step.status.name not in ("failed", "error"):
            continue                        # only the step that stopped the run is worth carrying

        if step.error_message is None:
            message = ""
        else:
            message = str(step.error_message)

        steps.append({"keyword": step.keyword,
                      "name": step.name,
                      "error": message})

    return {"name": scenario.name,
            "status": scenario.status.name,
            "manual": is_manual(scenario),
            "steps": steps}


# stops the service a criterion started, and whatever it started in turn.
#
# It has to be gone before the next criterion begins. A service left listening
# would answer the criterion after it, which would then pass against a process
# nobody started for it: green on paper, and nothing verified.
#
# The group is signalled whether or not the process named here is still
# running, and that is the whole point. A launcher that starts the real server
# and exits is an ordinary way to write one, and the earlier version only
# signalled while that launcher was alive: its children kept the port, the
# next criterion found an answer, and passed without starting anything. The
# group id is the launcher's own pid, because the step started it in a session
# of its own
def stop_service(context):
    service = getattr(context, "service", None)
    if service is None:
        return

    group = service.pid

    try:
        os.killpg(group, signal.SIGTERM)        # asked to leave, the whole group
    except OSError:
        pass                        # nobody left in it, which is the wanted end

    if service.poll() is None:
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    else:
        time.sleep(0.2)             # a moment for the children of a launcher that already left

    try:
        os.killpg(group, signal.SIGKILL)        # made to leave
    except OSError:
        pass

    if service.poll() is None:
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    context.service = None


def before_all(context):
    global NONCE, STDOUT

    # descriptor 1 as it is now, before behave starts putting its own object in
    # front of sys.stdout around steps and hooks. Writing to the descriptor
    # keeps the outcome out of whatever behave is capturing at that moment
    STDOUT = os.dup(1)

    # a secret is coming only when somebody is feeding us one. The same
    # question decides whether the outcome has to be sealed, so it is asked
    # once and used for both
    expected = sys.stdin is not None and not sys.stdin.isatty()

    # before the secret exists, so there is no moment in which it is in memory
    # and that memory can still be read from outside
    close_to_outsiders(expected)

    # the secret of this run. Reading is skipped on a terminal so that running
    # behave by hand does not sit waiting for a line nobody will type
    if expected:
        NONCE = sys.stdin.readline().strip()

    # and now stdin is an empty one. A delivered program that reads it still
    # finds a stream it can read to the end, and finds nothing in it
    empty = os.open(os.devnull, os.O_RDONLY)
    os.dup2(empty, 0)
    os.close(empty)


def before_scenario(context, scenario):

    # the criteria marked @manual are not executed, the product owner checks them

    if is_manual(scenario):
        scenario.skip("to be checked by hand")
        return                  # nothing to prepare for a scenario that will not run

    # every scenario gets an empty folder of its own, so that the files one
    # criterion creates are not there for the one after it
    context.folder = tempfile.mkdtemp()     # a folder with a random name
    context.previous = os.getcwd()          # where we were before changing folder
    os.chdir(context.folder)

    # the places the steps leave their results in
    context.result = None
    context.error = None
    context.exit_code = None
    context.output = ""
    context.status = None
    context.body = ""
    context.duration = 0
    context.service = None                  # filled in by the step that starts it

    # handed to the step so that it can stop a service it is about to replace.
    # It cannot import this file, which behave loads by path and not as a
    # module, so the function travels on the context
    context.stop_service = stop_service


def after_scenario(context, scenario):

    SCENARIOS.append(collected(scenario))   # the manual ones are kept too, the report lists them

    stop_service(context)       # before anything else: it has to be gone whatever happened

    if is_manual(scenario):
        return                  # nothing was prepared, so nothing to undo

    os.chdir(context.previous)                             # back to the folder we came from
    shutil.rmtree(context.folder, ignore_errors=True)      # and the temporary one goes away


def after_all(context):

    # the one line that comes back out of the container. It goes out last,
    # after every scenario has run, and a leading newline makes sure the mark
    # starts a line of its own whatever behave printed before it
    line = MARKER + NONCE + json.dumps({"scenarios": SCENARIOS})
    os.write(STDOUT, ("\n" + line + "\n").encode("utf-8"))
