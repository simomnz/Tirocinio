# watches the whole chain for deliveries and starts the Jenkins job for the
# contract they came from.
#
#   python3 listener.py
#
# It listens by event and not by address: one filter covers every contract
# that exists, so a company that publishes its own contract is seen without
# anybody configuring anything here. What it checks, on a contract it has
# never met, is whether that contract lists this verifier: the permission is
# written on the chain by whoever wants to be verified, with addVerifier.

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

from web3 import Web3

import blockchain

HERE = os.path.dirname(os.path.abspath(__file__))

JENKINS_URL   = os.environ.get("JENKINS_URL", "http://127.0.0.1:8080")
JENKINS_USER  = os.environ.get("JENKINS_USER", "")
JENKINS_TOKEN = os.environ.get("JENKINS_TOKEN", "")      # an API token, not the password
JENKINS_JOB   = os.environ.get("JENKINS_JOB", "PACT")

INTERVAL = int(os.environ.get("LISTEN_INTERVAL", "5"))   # seconds between one question and the next
WINDOW = int(os.environ.get("LISTEN_WINDOW", "10"))      # blocks per question: nodes cap the range, and a bounded question is served everywhere
CURSOR = os.environ.get("LISTEN_CURSOR", os.path.join(HERE, "last-block.txt"))
KNOWN = os.environ.get("LISTEN_KNOWN", os.path.join(HERE, "contracts-seen.json"))

TOPIC = blockchain.event_topic("WorkSubmitted")


# the block the last question stopped at, so a restart does not lose the
# events that arrived while this process was down
def load_cursor(w3):
    try:
        with open(CURSOR, encoding="utf-8") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return w3.eth.block_number            # the first run starts from now, not from the beginning of the chain


def save_cursor(block):
    with open(CURSOR, "w", encoding="utf-8") as f:
        f.write(str(block) + "\n")


# the contracts that have named this verifier. Only the yes are kept, so the
# file is an answer that cannot go stale: a contract stops inviting us by
# calling removeVerifier, and the next round reads that from the chain anyway.
# A no written down by an older version is dropped while reading, which is all
# the migration this needs
def load_known():
    try:
        with open(KNOWN, encoding="utf-8") as f:
            stored = json.load(f)
    except (FileNotFoundError, ValueError):
        return {}

    known = {}
    for address, answer in stored.items():
        if answer:
            known[address] = True

    return known


def save_known(known):
    with open(KNOWN, "w", encoding="utf-8") as f:
        json.dump(known, f, indent=2, sort_keys=True)


# asks the contract whether it named this verifier, which is what tells our
# contracts apart from anything else emitting a log with the same shape
def invited(address):
    try:
        _, contract = blockchain.connect(address)
        return bool(blockchain.is_invited(contract))
    except Exception:
        return False                          # not one of ours at all


# whether this contract has named us, asking the chain the first time it is
# met. Only a yes is written down. A no lives in memory and lasts the current
# round alone: it used to be saved, so a company that published the contract
# and called addVerifier afterwards was remembered as a no and never asked
# again, and stayed ignored for good without anybody being told
def names_us(address, known, refused):
    if address in known:
        return True
    if address in refused:
        return False

    if invited(address):
        known[address] = True
        save_known(known)
        print("Invited by " + address)
        return True

    refused.add(address)
    print("Ignoring " + address)
    return False


def ask_jenkins(path, address):
    url = (JENKINS_URL.rstrip("/") + "/job/" + JENKINS_JOB + path +
           "?CONTRACT=" + address)            # the job is told which contract, by the machine and not by a person
    request = urllib.request.Request(url, data=b"", method="POST")

    credentials = JENKINS_USER + ":" + JENKINS_TOKEN
    request.add_header("Authorization", "Basic " +
                       base64.b64encode(credentials.encode()).decode())

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status                # 201 means it went into the queue


# the right address depends on whether the job has parameters, and Jenkins
# answers 400 on the wrong one, so both are tried
def start_build(address):
    try:
        return ask_jenkins("/buildWithParameters", address)
    except urllib.error.HTTPError as error:
        if error.code != 400:
            raise
    return ask_jenkins("/build", address)


def main():
    if not JENKINS_USER or not JENKINS_TOKEN:
        print("JENKINS_USER or JENKINS_TOKEN not set", file=sys.stderr)
        return 2

    w3 = Web3(Web3.HTTPProvider(blockchain.RPC))
    if not w3.is_connected():
        print("Cannot reach the node: " + blockchain.RPC, file=sys.stderr)
        return 2

    cursor = load_cursor(w3)
    known = load_known()
    save_known(known)                         # written back at once, so a no left by an older version leaves the file too and not only the memory

    print("Verifier " + blockchain.verifier_address())
    print("Listening for deliveries from block " + str(cursor))
    print("Job " + JENKINS_JOB + " on " + JENKINS_URL)

    while True:
        try:
            latest = w3.eth.block_number

            asked = set()                     # contracts already sent to Jenkins in this round
            refused = set()                   # and the ones that answered no, forgotten when the round ends

            while cursor <= latest:
                last = min(cursor + WINDOW - 1, latest)   # one window at a time, so a long catch up does not ask too much at once

                logs = w3.eth.get_logs({                  # one question, whatever the number of contracts
                    "fromBlock": cursor,
                    "toBlock": last,
                    "topics": [TOPIC],
                })

                for log in logs:
                    address = Web3.to_checksum_address(log["address"])

                    if not names_us(address, known, refused):
                        continue                          # not ours, and the question will be asked again next round

                    if address in asked:
                        continue                          # one build covers every delivery that contract is holding

                    asked.add(address)
                    print("Delivery on " + address + ", block " + str(last))
                    print("Jenkins answered " + str(start_build(address)))

                cursor = last + 1
                save_cursor(cursor)                       # saved window by window, so an interruption loses nothing

        except Exception as error:            # a node hiccup or a restart of Jenkins must not kill the process
            print("Nothing done this round: " + str(error), file=sys.stderr)

        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
