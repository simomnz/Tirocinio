# asks for the story of a user story taken on the chain.
#
#   python3 brief.py <contract> <story id>
#
# The private key is used here to sign a sentence and never leaves this
# machine: what travels is the signature. The service works out who is asking
# from it, and answers only to the developer the chain says is working on it.
#
# There is nothing secret in this program, and it is not worth changing: the
# acceptance criteria are cut on the other side, so no version of this can
# ever ask for them.

import getpass
import json
import os
import re
import sys
import urllib.error
import urllib.request

from eth_account import Account
from eth_account.messages import encode_defunct

SERVICE = os.environ.get("BRIEF_SERVICE", "http://127.0.0.1:8070")


def ask(path, payload=None):
    url = SERVICE.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None

    request = urllib.request.Request(url, data=data)
    if data is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:   # the service explains itself in the body
        return json.loads(error.read())


def main():
    arguments = sys.argv[1:]
    if len(arguments) < 2:
        print("Usage: brief.py <contract> <story id>", file=sys.stderr)
        return 2

    contract, story = arguments[0], arguments[1]

    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", contract):
        print("That is not a contract address: it is 0x and forty hexadecimal digits",
              file=sys.stderr)
        return 2

    challenge = ask("/challenge")
    if "nonce" not in challenge:
        print(challenge.get("error", "The service did not answer"), file=sys.stderr)
        return 2

    sentence = ("Brief request\n"
                "contract: " + contract + "\n"
                "story: " + str(story) + "\n"
                "nonce: " + challenge["nonce"])

    print("Signing:")
    print(sentence)
    print()

    key = getpass.getpass("Your private key (not shown, not sent): ").strip()
    try:
        signed = Account.sign_message(encode_defunct(text=sentence), private_key=key)
    except Exception:                         # usually the address pasted in place of the key
        print("That is not a private key: it is sixty-four hexadecimal digits, "
              "and it is not your address. Read " + str(len(key)) + " characters",
              file=sys.stderr)                # the count tells what happened without showing anything
        return 2

    answer = ask("/brief", {"contract": contract,
                            "story": story,
                            "nonce": challenge["nonce"],
                            "signature": "0x" + signed.signature.hex()})   # hex() drops the prefix, and it is expected on the other side

    if "story" not in answer:
        print(answer.get("error", "The service refused"), file=sys.stderr)
        return 1

    print(answer["title"])
    print()
    print(answer["story"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
