# The vocabulary. Every phrase documented in vocabulary.md is one function in
# this file. It lives in the verifier's own repository and is copied into the
# working folder, so the code being judged cannot define the language it is
# judged in.

import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.request

from behave import given, when, then

# Run locally the code sits two folders above. When it comes from GitHub its
# folder is passed in from outside with CODE_ROOT, which is the path inside the
# container and not the one outside it.
ROOT = os.environ.get("CODE_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))

# {name}      a string
# {name:d}    an int
# {name:f}    a float




# Helpers


# reads one configuration line out of the header of the user story, the lines
# like Module: or Command: or Service: that say what the criteria run against
def field(context, name):
    for line in context.feature.description:
        text = line.strip()
        if text.startswith(name + ":"):
            return text.split(":", 1)[1].strip()    # the 1 keeps a colon inside a URL from splitting it
    raise AssertionError("missing field " + name + " in the header")


# The delivered code runs in a process of its own, and no longer inside behave.
#
# It used to be imported here with exec_module, that is executed in the very
# interpreter that judges it, and from there a delivered module reaches the
# objects of behave, the formatter that writes the outcome, and the outcome
# file itself. Now the only thing that comes back is one line of JSON.
#
# What is left is a limit of the method and not of this code: a hostile process
# can always lie about its own behaviour. What it cannot fake is what is
# observed from outside, and that is why the steps checking an exit code, the
# output or an HTTP answer are worth more than the ones checking the value a
# function returned.
CALL_RUNNER = r'''
import importlib.util, json, os, sys, time

# the marker comes in on stdin, not in argv and not in the environment: the
# delivered code can read sys.argv and /proc/self/environ, but not a stdin that
# has already been read and closed
nonce = sys.stdin.read().strip()
sys.stdin.close()

path, function, arguments = sys.argv[1], sys.argv[2], sys.argv[3]
outcome = {}

spec = importlib.util.spec_from_file_location("under_test", path)
module = importlib.util.module_from_spec(spec)

start = time.time()
try:
    spec.loader.exec_module(module)
    outcome["result"] = getattr(module, function)(*json.loads(arguments))
except Exception as error:
    outcome["error"] = str(error)
outcome["duration"] = (time.time() - start) * 1000

try:
    text = json.dumps(outcome)
except TypeError:                   # a result that cannot be written as JSON cannot be compared with the criteria either
    text = json.dumps({"error": "the result cannot be represented as JSON",
                       "duration": outcome["duration"]})
sys.stdout.write("\n__VERIFY_RESULT__" + nonce + text + "\n")
sys.stdout.flush()
os._exit(0)      # skips the atexit handlers: one registered by the delivered
                 # code would write after us, and the last marked line would win
'''

MARKER = "__VERIFY_RESULT__"


# reads the answer of the process out of its output. Only the line marked with
# the nonce of this run is accepted: the delivered code writes on the same
# stdout, but it does not know what to sign with
def runner_answer(output, nonce):
    found = None
    for line in output.split("\n"):
        if line.startswith(MARKER + nonce):
            found = line[len(MARKER) + len(nonce):]

    if found is None:
        return {"error": "the delivered code did not answer: " +
                         output.strip()[-400:]}      # the last lines are enough to see what went wrong
    try:
        return json.loads(found)
    except ValueError:
        return {"error": "the answer of the delivered code is not readable"}


# the text a criterion is looking for, as it was written between the quotes.
# A criterion cannot hold a real newline inside a quoted string, so \n stands
# for one, the same way it already did when a file was being written. Without
# this the two halves of the vocabulary disagreed: Given the file contains
# "a\nb" wrote two lines, and Then the file contains "a\nb" went looking for a
# backslash followed by an n, and never found it
def wanted(text):
    return text.replace("\\n", "\n")


def absolute_paths(command):
    pezzi = command.split()        # "python3 esercizi.py" becomes ["python3", "esercizi.py"]
    risultato = []
    for p in pezzi:
        if p.endswith(".py"):
            risultato.append(os.path.join(ROOT, p))   # becomes /tmp/verify-xxxx/code/esercizi.py
        else:
            risultato.append(p)                       # python3 stays as it is
    return risultato



# ------------------------------------------------------------
# Given - preparing
# ------------------------------------------------------------

@given('the file "{path}" contains "{text}"')
def step(context, path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(wanted(text))


@given('the file "{path}" contains the text')
def step(context, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(context.text)


@given('the file "{path}" is empty')
def step(context, path):
    open(path, "w", encoding="utf-8").close()


@given('the file "{path}" does not exist')
def step(context, path):
    if os.path.exists(path):
        os.remove(path)


# true as soon as something at that address is talking HTTP. An answer of 404
# or 500 counts: it means the service is up and has an opinion about the path,
# which is all that is being asked here. Only a connection that is refused
# means it is not there yet.
#
# Before, any HTTP error code counted as silence, so a service that answers
# nothing on / was waited for until the timeout and then declared dead while
# it was running the whole time
def service_answers(address):
    try:
        urllib.request.urlopen(address, timeout=1)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


# starts the service and waits for it to answer.
#
# This step used to do only the second half: it interrogated the address for
# four seconds and gave up, and nothing anywhere started anything. A delivery
# with a service in it was refused however well it was written, because the
# service was never switched on. The whole Service half of the vocabulary was
# documented and unusable
@given('the service is running')
def step(context):
    address = field(context, "Service")
    command = absolute_paths(field(context, "Start"))

    # a criterion that writes this step twice, for instance once in a
    # Background and again in the scenario, used to leave the first service
    # behind: the second one was written over it and nothing ever signalled
    # the group of the first, which then held the port for every criterion
    # after it
    if getattr(context, "service", None) is not None:
        context.stop_service(context)

    # nothing may be answering there yet. Whatever does is not ours: a service
    # an earlier criterion left behind because it escaped its process group,
    # or one that belongs to the machine. Starting on top of it binds to
    # nothing while the old one keeps answering, and the criterion would pass
    # against a process nobody started for it.
    #
    # It is asked here and not after starting, because afterwards the two
    # cases cannot be told apart: a launcher that started the real server and
    # left, and a launcher whose server could not take the port, both exit
    # with zero
    if service_answers(address):
        raise AssertionError(
            "something was already answering at " + address + " before this "
            "criterion started anything: that port is held by a process which "
            "does not belong to this run")

    # the output goes to a file and not to a pipe: a service that writes more
    # than a pipe holds would stop on its own output and never answer
    log = os.path.join(os.getcwd(), "service.log")
    handle = open(log, "w", encoding="utf-8")

    # a session of its own, so that stopping it afterwards reaches whatever it
    # started in turn and not only the process named here
    context.service = subprocess.Popen(command, stdout=handle,
                                       stderr=subprocess.STDOUT,
                                       start_new_session=True)
    context.service_log = log
    handle.close()          # the service keeps its own copy of the descriptor

    # a deadline and not a count of tries. Counting bounded the number of
    # questions, not the time: a service that accepts the connection and then
    # says nothing costs a whole second on every one of them, and the fifteen
    # seconds promised here and in vocabulary.md became ninety
    deadline = time.monotonic() + 15
    ended = None

    while time.monotonic() < deadline:
        if service_answers(address):
            ended = context.service.poll()

            # something answers. It is ours while the process is still
            # running, and also when a launcher started the real server and
            # left quietly. A launcher that failed means the answer comes from
            # somebody else: a service left over from an earlier criterion, or
            # one that was already on that port
            if ended is None or ended == 0:
                return

            raise AssertionError(
                "something is already answering at " + address + ", and the "
                "service started here exited with code " + str(ended) +
                ": the port was taken before this criterion began")

        ended = context.service.poll()
        if ended is not None and ended != 0:
            break                                   # it failed, waiting out the rest is pointless

        time.sleep(0.2)

    with open(log, encoding="utf-8") as f:
        said = f.read().strip()[-600:]              # the end is where the reason is

    if ended is None or ended == 0:
        trouble = "the service did not answer at " + address + " within 15 seconds"
    else:
        trouble = "the service stopped straight away with exit code " + str(ended)

    if said:
        raise AssertionError(trouble + ", it said: " + repr(said))
    else:
        raise AssertionError(trouble + ", and it said nothing")


# ------------------------------------------------------------
# When - agire
# ------------------------------------------------------------

@when('I call "{function}" with {arguments}')
def step(context, function, arguments):
    json.loads(arguments)                   # checked here, so a badly written criterion fails before anything starts

    nonce = secrets.token_hex(16)            # unpredictable, and different for every criterion

    outcome = subprocess.run(
        [sys.executable, "-c", CALL_RUNNER,
         os.path.join(ROOT, field(context, "Module")), function, arguments],
        input=nonce, capture_output=True, text=True, timeout=120)

    answer = runner_answer(outcome.stdout + outcome.stderr, nonce)

    context.result = answer.get("result")
    context.error = answer.get("error")
    context.duration = answer.get("duration", 0)   # measured inside, without the interpreter start-up


@when('I run "{command}"')
def step(context, command):
    start = time.time()
    outcome = subprocess.run(
        absolute_paths(field(context, "Command")) + command.split(),
        capture_output=True, text=True)

    context.duration = (time.time() - start) * 1000
    context.exit_code = outcome.returncode
    context.output = outcome.stdout + outcome.stderr


@when('I send {method} "{path}"')
def step(context, method, path):
    request = urllib.request.Request(field(context, "Service") + path,
                                     method=method)
    start = time.time()
    try:
        with urllib.request.urlopen(request) as response:
            context.status = response.status
            context.body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        context.status = error.code
        context.body = error.read().decode("utf-8")
    context.duration = (time.time() - start) * 1000


@when('I send {method} "{path}" with {payload}')
def step(context, method, path, payload):
    request = urllib.request.Request(
        field(context, "Service") + path,
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=method)
    start = time.time()
    try:
        with urllib.request.urlopen(request) as response:
            context.status = response.status
            context.body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        context.status = error.code
        context.body = error.read().decode("utf-8")
    context.duration = (time.time() - start) * 1000


# ------------------------------------------------------------
# Then - verificare
# ------------------------------------------------------------

@then('I get {expected}')
def step(context, expected):
    assert context.error is None, "the call raised: " + str(context.error)

    value = json.loads(expected)
    assert context.result == value, \
        "expected: " + repr(value) + ", found: " + repr(context.result)


@then('the result is between {low:f} and {high:f}')
def step(context, low, high):
    assert context.error is None, "the call raised: " + str(context.error)
    assert low <= context.result <= high, \
        "expected between " + str(low) + " and " + str(high) + \
        ", found: " + repr(context.result)


@then('the result has {count:d} items')
def step(context, count):
    assert len(context.result) == count, \
        "expected " + str(count) + " items, found: " + str(len(context.result))


@then('the result contains "{text}"')
def step(context, text):
    text = wanted(text)
    assert text in str(context.result), \
        "does not contain " + repr(text) + ": " + repr(context.result)


@then('the result does not contain "{text}"')
def step(context, text):
    text = wanted(text)
    assert text not in str(context.result), \
        "contains " + repr(text) + ": " + repr(context.result)


@then('the output contains "{text}"')
def step(context, text):
    text = wanted(text)
    assert text in context.output, \
        "does not contain " + repr(text) + ", output: " + repr(context.output)


@then('the output does not contain "{text}"')
def step(context, text):
    text = wanted(text)
    assert text not in context.output, \
        "contains " + repr(text) + ", output: " + repr(context.output)


@then('the output matches "{pattern}"')
def step(context, pattern):
    assert re.search(pattern, context.output), \
        "does not match " + repr(pattern) + ", output: " + repr(context.output)


@then('it succeeds')
def step(context):
    assert context.exit_code == 0, \
        "expected exit code 0, found: " + str(context.exit_code) + \
        ", output: " + repr(context.output)


@then('it fails')
def step(context):
    assert context.exit_code != 0, \
        "expected a non-zero exit code, output: " + repr(context.output)


@then('the error "{message}" is raised')
def step(context, message):
    assert context.error is not None, "no error was raised"
    assert message in context.error, \
        "expected " + repr(message) + ", found: " + repr(context.error)


@then('I receive status {expected:d}')
def step(context, expected):
    assert context.status == expected, \
        "expected status " + str(expected) + ", found: " + str(context.status)


@then('the body contains "{text}"')
def step(context, text):
    text = wanted(text)
    assert text in context.body, \
        "does not contain " + repr(text) + ", body: " + repr(context.body)


@then('the body does not contain "{text}"')
def step(context, text):
    text = wanted(text)
    assert text not in context.body, \
        "contains " + repr(text) + ", body: " + repr(context.body)


@then('the file "{path}" exists')
def step(context, path):
    assert os.path.exists(path), "the file does not exist: " + path


@then('the file "{path}" does not exist')
def step(context, path):
    assert not os.path.exists(path), \
        "the file exists, " + str(os.path.getsize(path)) + " bytes: " + path


@then('the file "{path}" contains "{text}"')
def step(context, path, text):
    text = wanted(text)
    assert os.path.exists(path), "the file does not exist: " + path
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert text in content, \
        "does not contain " + repr(text) + ", content: " + repr(content)


# the file has to be there. A criterion asking that something is absent from a
# file that was never written would pass without anything having been looked
# at, and the criterion that says a password is not kept in clear is exactly
# the one that must not pass for free. A delivery that is allowed not to write
# the file at all says so with the file does not exist
@then('the file "{path}" does not contain "{text}"')
def step(context, path, text):
    text = wanted(text)
    assert os.path.exists(path), "the file does not exist: " + path
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert text not in content, \
        "contains " + repr(text) + ", content: " + repr(content)


@then('it finishes within {limit:d} milliseconds')
def step(context, limit):
    assert context.duration <= limit, \
        "expected within " + str(limit) + " ms, took: " + str(round(context.duration))
