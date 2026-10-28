# records on the blockchain that the automated tests passed
# reads before writing, so that no gas is spent on a transaction that would be rejected

import json
import os
import sys

from eth_account import Account
from web3 import Web3

HERE = os.path.dirname(os.path.abspath(__file__))

RPC = os.environ.get("SEPOLIA_RPC", "https://ethereum-sepolia-rpc.publicnode.com")   # public Ethereum node
VERIFIER_KEY = os.environ.get("VERIFIER_KEY", "")        # empty when missing, so the checks below catch it


# which contract to work on. The listener finds the contracts by itself and
# says which one, so this is only a convenience for commands run by hand
def configured_address():
    from_environment = os.environ.get("CONTRACT_ADDRESS", "").strip()
    if from_environment:
        return from_environment

    try:
        with open(os.path.join(HERE, "..", "contracts", "address.txt"),
                  encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


CONTRACT_ADDRESS = configured_address()

# the ABI comes from the compiler, not written by hand: one source of truth,
# so it cannot drift away from the contract it describes
ABI_PATH = os.environ.get(
    "CONTRACT_ABI",
    os.path.join(HERE, "..", "contracts", "UserStories_SC.abi.json"))

with open(ABI_PATH, encoding="utf-8") as f:
    ABI = json.load(f)


# writes raw bytes as hexadecimal with the 0x in front, which hex() drops
def prefixed(value):
    return "0x" + value.hex()


# the account the verifier signs with, worked out from the key without
# touching the network
def verifier_address():
    if not VERIFIER_KEY:
        raise RuntimeError("VERIFIER_KEY not set")
    return Account.from_key(VERIFIER_KEY).address


# the topic every log of that event carries. Listening by topic instead of by
# address means one filter covers every contract on the chain, so no list of
# clients has to be kept anywhere
def event_topic(name):
    entry = next(e for e in ABI
                 if e.get("type") == "event" and e.get("name") == name)
    signature = name + "(" + ",".join(i["type"] for i in entry["inputs"]) + ")"
    return Web3.keccak(text=signature)


# the fingerprint of the acceptance criteria. The contract freezes it before
# the work starts, and checks it again when the outcome is recorded, so the
# criteria somebody is judged on are provably the agreed ones
def criteria_hash(text):
    return Web3.keccak(text=text)


# turns a Git commit into the twenty bytes the contract stores
def to_bytes20(commit):
    text = commit.lower().replace("0x", "")
    if len(text) != 40:                       # forty hexadecimal digits, the length of a Git SHA-1
        raise ValueError("The commit must be 40 hexadecimal digits, found " + str(len(text)))
    return bytes.fromhex(text)


# opens the connection and builds the local contract object
def connect(address=None):
    w3 = Web3(Web3.HTTPProvider(RPC))         # local object, talks to nobody yet
    if not w3.is_connected():                 # this one does call the node
        raise RuntimeError("Cannot reach the node: " + RPC)

    target = address or CONTRACT_ADDRESS
    if not target:
        raise RuntimeError("No contract to work on")
    if not Web3.is_address(target):            # says so plainly instead of failing deep inside the encoder
        raise RuntimeError("Not a contract address: " + repr(target))

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(target),   # the mixed case is a checksum against typos
        abi=ABI)
    return w3, contract


# true when the contract itself lists this verifier. The permission lives in
# the contract, so a company that wants its deliveries verified calls
# addVerifier once and nothing is configured on this side
def is_invited(contract):
    return contract.functions.verifiers(verifier_address()).call()


# reads a user story and returns it by field name instead of by position,
# so that adding a field to the struct cannot silently shift the values
def read_story(contract, story_id):
    outputs = next(entry["outputs"] for entry in ABI
                   if entry.get("name") == "userStories")
    values = contract.functions.userStories(story_id).call()
    return {out["name"]: value for out, value in zip(outputs, values)}


# returns what the developer declared on chain for a user story:
# which task it maps to, and which commit is the delivery
def get_delivery(story_id, address=None):
    _, contract = connect(address)

    if not is_invited(contract):              # refuses to work for a contract that did not ask
        raise RuntimeError("This contract does not list us as a verifier")

    story = read_story(contract, int(story_id))

    if not story["workSubmitted"]:
        raise RuntimeError("User story " + str(story_id) + " has no declared delivery")

    reference = story["externalRef"]
    if ":" not in reference:                  # expected shape is "openproject:1117"
        raise RuntimeError("externalRef is not in the form system:task: " + repr(reference))

    system, task = reference.split(":", 1)    # split once, a task identifier may contain a colon
    return {"system": system,
            "task": task,
            "commit": story["commit"].hex(),
            "developer": story["developer"]}


def record_tests_passed(story_id, commit, criteria, address=None):
    story_id = int(story_id)                  # arrives as a string from the command line
    w3, contract = connect(address)

    if not is_invited(contract):
        print("This contract does not list us as a verifier, nothing recorded")
        return None

    # free checks, before spending anything. These mirror the contract's own
    # requires: in Python they save gas, in Solidity they enforce the rule
    story = read_story(contract, story_id)

    if story["paid"]:
        print("User story " + str(story_id) + " is already paid, nothing to record")
        return None                           # None means nothing was done, not an error

    if not story["taken"]:
        print("User story " + str(story_id) + " has not been claimed by any "
              "developer, nothing to record")
        return None

    if not story["workSubmitted"]:
        print("User story " + str(story_id) + " has no declared delivery, "
              "nothing to record")
        return None

    if contract.functions.getApprovals(story_id).call()[0]:   # [0] is the tests box
        print("User story " + str(story_id) + " is already recorded, "
              "no transaction sent")
        return None                           # the box is written once only

    # the commit the developer declared on chain, which is the one that must be verified
    declared = to_bytes20(commit)
    if story["commit"] != declared:
        print("The verified commit does not match the declared delivery")
        print("  declared " + story["commit"].hex())
        print("  verified " + declared.hex())
        return None

    # the criteria the contract froze before the work started
    frozen = story["criteriaHash"]
    if frozen != bytes(32) and frozen != criteria:
        print("The criteria that were run are not the ones agreed on chain")
        print("  agreed " + prefixed(frozen))
        print("  run    " + prefixed(criteria))
        return None

    # the signature, which costs gas
    account = w3.eth.account.from_key(VERIFIER_KEY)     # the address comes from the key, locally
    call = contract.functions.recordTestsPassed(story_id, declared, criteria)   # prepares the call, does not send it

    transaction = call.build_transaction({
        "from": account.address,              # not part of the signed transaction: the sender comes from the signature
        "nonce": w3.eth.get_transaction_count(account.address),   # orders the account's transactions and stops a replay
        "chainId": w3.eth.chain_id,           # 11155111 is Sepolia; it is part of the signature
    })

    signed = account.sign_transaction(transaction)      # signed here, the private key never leaves this machine
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction   # the field was renamed in web3 7

    digest = w3.eth.send_raw_transaction(raw)
    print("Signing from  " + account.address)
    print("Developer     " + story["developer"])
    print("Commit        " + declared.hex())
    print("Criteria      " + prefixed(criteria))
    print("Transaction   https://sepolia.etherscan.io/tx/" + prefixed(digest))
    print("Waiting for the block...")

    receipt = w3.eth.wait_for_transaction_receipt(digest, timeout=180)
    if receipt.status != 1:                   # 1 executed, 0 rejected by a require, gas spent either way
        raise RuntimeError("The transaction was reverted")

    print("Recorded in block " + str(receipt.blockNumber) +
          ", gas used " + str(receipt.gasUsed))
    return receipt


def main():
    print("Not run on its own: verify.py uses this", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
