# serves a developer the story of a user story, without its acceptance
# criteria. This process holds the project management token, so the cut
# happens here: whatever the developer runs on his own machine, the criteria
# never leave this program.
#
#   python3 brief_service.py
#
# Two steps, so that a signature cannot be used twice: the client asks for a
# challenge, then sends it back signed. The address is worked out from the
# signature, never taken from what the client says about itself.

import json
import os
import re
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from eth_account import Account
from eth_account.messages import encode_defunct

import blockchain
import fetch_criteria

HOST = os.environ.get("BRIEF_HOST", "127.0.0.1")
PORT = int(os.environ.get("BRIEF_PORT", "8070"))
CHALLENGE_LIFE = 120                          # seconds a challenge stays good for

challenges = {}                               # nonce -> when it was handed out


def forget_old_challenges():
    now = time.time()
    for nonce in [n for n, born in challenges.items()
                  if now - born > CHALLENGE_LIFE]:
        del challenges[nonce]


# the sentence the developer signs. It names what he is asking for, so a
# signature given for one user story cannot be spent on another
def challenge_text(contract, story, nonce):
    return ("Brief request\n"
            "contract: " + contract + "\n"
            "story: " + str(story) + "\n"
            "nonce: " + nonce)


# everything before the first scenario is the story, the rest are the criteria.
#
# It returns nothing when it cannot find where the criteria begin. Before it
# returned the whole body in that case, which is the wrong way round: a task
# that is not a Gherkin user story has no Scenario line, so any other task of
# the project management system came out entire. A cut that cannot prove it
# cut something must hand back nothing
def story_only(body):
    criteria = re.search(r"^\s*(Scenario|Background|Examples)", body, re.M)
    if not criteria:
        return None

    return body[:criteria.start()].rstrip()


class Brief(BaseHTTPRequestHandler):

    def reply(self, status, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/challenge":
            self.reply(404, {"error": "No such address"})
            return

        forget_old_challenges()
        nonce = secrets.token_hex(16)         # from the system, not from random()
        challenges[nonce] = time.time()
        self.reply(200, {"nonce": nonce})

    def do_POST(self):
        if self.path != "/brief":
            self.reply(404, {"error": "No such address"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            status, payload = self.brief(request)
        except Exception as error:            # a malformed request is not worth a stack trace
            status, payload = 400, {"error": str(error)}

        self.reply(status, payload)

    # the only way in, and it answers with the story and nothing else
    def brief(self, request):
        contract = request["contract"]
        story = int(request["story"])
        nonce = request["nonce"]

        forget_old_challenges()
        if nonce not in challenges:
            return 403, {"error": "Challenge unknown or expired"}
        del challenges[nonce]                 # one challenge, one answer

        message = encode_defunct(text=challenge_text(contract, story, nonce))
        asker = Account.recover_message(message, signature=request["signature"])

        _, live = blockchain.connect(contract)

        # the address of the contract arrives from whoever is asking, so until
        # this question is answered nothing it says means anything: a contract
        # written for the occasion can claim any address is its developer, and
        # the task it then names would be read with our token. Every other
        # place that reaches a contract asks this first
        if not blockchain.is_invited(live):
            return 403, {"error": "This contract does not list us as a verifier"}

        story_on_chain = blockchain.read_story(live, story)

        # the chain is the only place where it is written who is working on what
        if not story_on_chain["taken"] or story_on_chain["developer"] != asker:
            return 403, {"error": "You have not claimed this user story"}
        if live.functions.claimExpired(story).call():
            return 403, {"error": "Your time on this user story has run out"}

        reference = story_on_chain["externalRef"]
        if ":" not in reference:              # nobody has linked it to a task yet
            return 404, {"error": "This user story has no task linked to it"}

        system, key = reference.split(":", 1)
        if system not in fetch_criteria.READERS:   # named by the contract, so not to be trusted as a key
            return 404, {"error": "Unknown project management system"}

        title, description, _ = fetch_criteria.READERS[system](key)

        narrative = story_only(fetch_criteria.clean(description))
        if narrative is None:                 # no criteria found, so nothing was cut
            return 404, {"error": "This task does not hold acceptance criteria, "
                                  "so the story cannot be served without them"}

        print("Brief for user story " + str(story) + " to " + asker)
        return 200, {"title": title, "story": narrative}

    def log_message(self, formatting, *arguments):
        pass                                  # one line per request on stderr is noise, what matters is printed above


def main():
    server = HTTPServer((HOST, PORT), Brief)
    print("Serving the stories on http://" + HOST + ":" + str(PORT))
    print("The acceptance criteria stay in here")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
