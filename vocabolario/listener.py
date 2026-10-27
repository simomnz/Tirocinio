# watches the chain and starts the Jenkins job as soon as a delivery arrives.
#
#   python3 listener.py
#
# The chain cannot call out, so this process does the listening. The developer
# declares the delivery with submitWork and that is his only move: he does not
# decide when the verification runs, nor what it looks at.
#
# This only decides WHEN to look. What to verify is still pending.py, reading
# the state of the contract, so a missed event is not a lost delivery.

import base64
import os
import sys
import time
import urllib.error
import urllib.request

import blockchain

HERE = os.path.dirname(os.path.abspath(__file__))

JENKINS_URL   = os.environ.get("JENKINS_URL", "http://127.0.0.1:8080")
JENKINS_USER  = os.environ.get("JENKINS_USER", "")
JENKINS_TOKEN = os.environ.get("JENKINS_TOKEN", "")      # an API token, not the password
JENKINS_JOB   = os.environ.get("JENKINS_JOB", "verifica-consegne")

INTERVAL = int(os.environ.get("LISTEN_INTERVAL", "5"))   # seconds between one question and the next
CURSOR = os.environ.get("LISTEN_CURSOR", os.path.join(HERE, "last-block.txt"))


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


# asks Jenkins to run the job. An API token is not subject to the cross site
# check, so no crumb has to be fetched first
def start_build():
    url = JENKINS_URL.rstrip("/") + "/job/" + JENKINS_JOB + "/build"
    request = urllib.request.Request(url, data=b"", method="POST")

    credentials = JENKINS_USER + ":" + JENKINS_TOKEN
    request.add_header("Authorization", "Basic " +
                       base64.b64encode(credentials.encode()).decode())

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status                # 201 means it went into the queue


def main():
    if not blockchain.CONTRACT_ADDRESS:
        print("CONTRACT_ADDRESS not set", file=sys.stderr)
        return 2
    if not JENKINS_USER or not JENKINS_TOKEN:
        print("JENKINS_USER or JENKINS_TOKEN not set", file=sys.stderr)
        return 2

    w3, contract = blockchain.connect()
    cursor = load_cursor(w3)
    print("Listening for deliveries from block " + str(cursor))
    print("Job " + JENKINS_JOB + " on " + JENKINS_URL)

    while True:
        try:
            latest = w3.eth.block_number

            if latest >= cursor:
                logs = contract.events.WorkSubmitted.get_logs(
                    from_block=cursor, to_block=latest)   # one question, whatever the number of user stories

                for entry in logs:
                    print("Delivery for user story " + str(entry["args"]["id"]) +
                          " from " + entry["args"]["developer"] +
                          ", commit " + entry["args"]["commit"].hex() +
                          ", block " + str(entry["blockNumber"]))

                if logs:
                    status = start_build()    # one build for the whole batch: the job verifies everything pending
                    print("Jenkins answered " + str(status))

                cursor = latest + 1
                save_cursor(cursor)

        except Exception as error:            # a node hiccup or a restart of Jenkins must not kill the process
            print("Nothing done this round: " + str(error), file=sys.stderr)

        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
