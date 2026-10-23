# Il vocabolario: ogni frase del documento ha qui sotto la funzione che la esegue.

import importlib.util
import json
import os
import re
import subprocess
import time
import urllib.request

from behave import given, when, then

# Normalmente il codice sta due livelli sopra questo file. Quando invece e' il
# verificatore a eseguire, il codice arriva da GitHub e la sua cartella viene
# passata da fuori con CODE_ROOT.
ROOT = os.environ.get("CODE_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))


# ------------------------------------------------------------
# Appoggio
# ------------------------------------------------------------

def field(context, name):
    """Legge un campo dall'intestazione della user story."""
    for line in context.feature.description:
        text = line.strip()
        if text.startswith(name + ":"):
            return text.split(":", 1)[1].strip()
    raise AssertionError("missing field " + name + " in the header")


def load_module(path):
    spec = importlib.util.spec_from_file_location("under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def absolute_paths(command):
    """I file .py vanno cercati nella radice, non nella cartella temporanea."""
    return [os.path.join(ROOT, p) if p.endswith(".py") else p
            for p in command.split()]


# ------------------------------------------------------------
# Given - preparare
# ------------------------------------------------------------

@given('the file "{path}" contains "{text}"')
def step(context, path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.replace("\\n", "\n"))


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


@given('the service is running')
def step(context):
    address = field(context, "Service")
    for _ in range(20):
        try:
            urllib.request.urlopen(address, timeout=1)
            return
        except Exception:
            time.sleep(0.2)
    raise AssertionError("the service is not responding: " + address)


# ------------------------------------------------------------
# When - agire
# ------------------------------------------------------------

@when('I call "{function}" with {arguments}')
def step(context, function, arguments):
    module = load_module(os.path.join(ROOT, field(context, "Module")))
    values = json.loads(arguments)

    start = time.time()
    try:
        context.result = getattr(module, function)(*values)
    except Exception as error:
        context.error = str(error)
    context.duration = (time.time() - start) * 1000


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
    assert text in str(context.result), \
        "does not contain " + repr(text) + ": " + repr(context.result)


@then('the output contains "{text}"')
def step(context, text):
    assert text in context.output, \
        "does not contain " + repr(text) + ", output: " + repr(context.output)


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
    assert text in context.body, \
        "does not contain " + repr(text) + ", body: " + repr(context.body)


@then('the file "{path}" exists')
def step(context, path):
    assert os.path.exists(path), "the file does not exist: " + path


@then('the file "{path}" does not exist')
def step(context, path):
    assert not os.path.exists(path), \
        "the file exists, " + str(os.path.getsize(path)) + " bytes: " + path


@then('the file "{path}" contains "{text}"')
def step(context, path, text):
    assert os.path.exists(path), "the file does not exist: " + path
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert text in content, \
        "does not contain " + repr(text) + ", content: " + repr(content)


@then('it finishes within {limit:d} milliseconds')
def step(context, limit):
    assert context.duration <= limit, \
        "expected within " + str(limit) + " ms, took: " + str(round(context.duration))
