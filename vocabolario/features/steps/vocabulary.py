# Il vocabolario, ogni frase di Vocabolary.md corrisponde a una funzione di questo file.

import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.request

from behave import given, when, then

# In locale il codice sta due directory sopra, uqando il codice arriva da GitHub la sua cartella viene passata da fuori con CODE_ROOT.
ROOT = os.environ.get("CODE_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))

#{nome}	 	    stringa
#{nome:d}		int
#{nome:f}		float




# Appoggio


def field(context, name):
    """Legge un campo nell'intestazione della user story."""
    for line in context.feature.description:
        text = line.strip()
        if text.startswith(name + ":"):       # cerca il Module
            return text.split(":", 1)[1].strip()    # ,1 per evitare divisioni in LINK 
    raise AssertionError("missing field " + name + " in the header")    # errore se non trova nulla


# Il codice consegnato gira in un processo suo, e non piu' dentro behave.
#
# Prima veniva importato qui con exec_module, cioe' eseguito nello stesso
# interprete che lo giudica: da la' un modulo consegnato arriva agli oggetti di
# behave, al formattatore che scrive l'esito, e al file dell'esito stesso.
# Adesso l'unica cosa che torna indietro e' una riga di JSON.
#
# Il limite che resta e' del metodo, non di questo codice: un processo ostile
# puo' mentire sul proprio comportamento. Quello che non puo' falsificare e'
# cio' che si osserva da fuori, ed e' per questo che i passi che controllano un
# codice di uscita, l'output o una risposta HTTP valgono di piu' di quelli che
# controllano il valore restituito da una funzione.
CALL_RUNNER = r'''
import importlib.util, json, os, sys, time

# il marcatore arriva da stdin e non da argv ne' dall'ambiente: il codice
# consegnato puo' leggere sys.argv e /proc/self/environ, non uno stdin
# già consumato e chiuso
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
except TypeError:                   # un risultato che non si puo' scrivere in JSON non si puo' nemmeno confrontare con i criteri
    text = json.dumps({"error": "the result cannot be represented as JSON",
                       "duration": outcome["duration"]})
sys.stdout.write("\n__VERIFY_RESULT__" + nonce + text + "\n")
sys.stdout.flush()
os._exit(0)      # salta gli atexit: un handler registrato dal codice consegnato
                 # scriverebbe dopo di noi, e l'ultima riga marcata vincerebbe
'''

MARKER = "__VERIFY_RESULT__"


# legge la risposta del processo dall'output. Si accetta solo la riga marcata
# col nonce di questa esecuzione: il codice consegnato scrive sullo stesso
# stdout, ma non sa con cosa firmare
def runner_answer(output, nonce):
    found = None
    for line in output.split("\n"):
        if line.startswith(MARKER + nonce):
            found = line[len(MARKER) + len(nonce):]

    if found is None:
        return {"error": "the delivered code did not answer: " +
                         output.strip()[-400:]}      # le ultime righe bastano a capire cosa e' andato storto
    try:
        return json.loads(found)
    except ValueError:
        return {"error": "the answer of the delivered code is not readable"}


def absolute_paths(command):
    pezzi = command.split()        # split del commando bash, "python3 esercizi.py" diventa ["python3", "esercizi.py"]
    risultato = []
    for p in pezzi:
        if p.endswith(".py"):
            risultato.append(os.path.join(ROOT, p))   # diventa /tmp/verify-xxxx/code/esercizi.py
        else:
            risultato.append(p)                       # python3 rimane identico
    return risultato



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
    json.loads(arguments)                   # controllato qui, cosi' un criterio scritto male fallisce prima di avviare niente

    nonce = secrets.token_hex(16)            # imprevedibile, diverso a ogni criterio

    outcome = subprocess.run(
        [sys.executable, "-c", CALL_RUNNER,
         os.path.join(ROOT, field(context, "Module")), function, arguments],
        input=nonce, capture_output=True, text=True, timeout=120)

    answer = runner_answer(outcome.stdout + outcome.stderr, nonce)

    context.result = answer.get("result")
    context.error = answer.get("error")
    context.duration = answer.get("duration", 0)   # misurata dentro, senza l'avvio dell'interprete


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
