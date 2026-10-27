# records on the blockchain that the automated tests passed
# reads before writing, so that no gas is spent on a transaction that would be rejected

import json
import os
import sys

from web3 import Web3

# configuration from the environment
RPC = os.environ.get("SEPOLIA_RPC", "https://ethereum-sepolia-rpc.publicnode.com")   # public Ethereum node
VERIFIER_KEY = os.environ.get("VERIFIER_KEY", "")                      # empty when missing, so the check below catches it
CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS", "")

# the ABI comes from the compiler, not written by hand: one source of truth,
# so it cannot drift away from the contract it describes
HERE = os.path.dirname(os.path.abspath(__file__))
ABI_PATH = os.environ.get(
    "CONTRACT_ABI",
    os.path.join(HERE, "..", "contracts", "UserStories_SC.abi.json"))

with open(ABI_PATH, encoding="utf-8") as f:
    ABI = json.load(f)


# writes raw bytes as hexadecimal with the 0x in front, which hex() drops
# and which both Etherscan and Remix expect
def prefixed(value):
    return "0x" + value.hex()


# turns a Git commit into the twenty bytes the contract stores
def to_bytes20(commit):
    text = commit.lower().replace("0x", "")
    if len(text) != 40:                       # forty hexadecimal digits, the length of a Git SHA-1
        raise ValueError("The commit must be 40 hexadecimal digits, found " + str(len(text)))
    return bytes.fromhex(text)


# opens the connection and builds the local contract object
def connect():
    w3 = Web3(Web3.HTTPProvider(RPC))         # local object, talks to nobody yet
    if not w3.is_connected():                 # this one does call the node
        raise RuntimeError("Cannot reach the node: " + RPC)

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),   # the mixed case is a checksum against typos
        abi=ABI)
    return w3, contract


# reads a user story and returns it by field name instead of by position,
# so that adding a field to the struct cannot silently shift the values
def read_story(contract, story_id):
    outputs = next(entry["outputs"] for entry in ABI
                   if entry.get("name") == "userStories")
    values = contract.functions.userStories(story_id).call()
    return {out["name"]: value for out, value in zip(outputs, values)}


# returns what the developer declared on chain for a user story:
# which task it maps to, and which commit is the delivery
def get_delivery(story_id):
    if not CONTRACT_ADDRESS:
        raise RuntimeError("CONTRACT_ADDRESS not set")

    _, contract = connect()
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


def record_tests_passed(story_id, commit):
    if not VERIFIER_KEY or not CONTRACT_ADDRESS:        # an empty string is false in Python
        raise RuntimeError("VERIFIER_KEY or CONTRACT_ADDRESS not set")

    story_id = int(story_id)                  # arrives as a string from the command line
    w3, contract = connect()

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

    # the signature, which costs gas
    account = w3.eth.account.from_key(VERIFIER_KEY)     # the address comes from the key, locally
    call = contract.functions.recordTestsPassed(story_id, declared)   # prepares the call, does not send it

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
    print("Transaction   https://sepolia.etherscan.io/tx/" + prefixed(digest))
    print("Waiting for the block...")

    receipt = w3.eth.wait_for_transaction_receipt(digest, timeout=180)
    if receipt.status != 1:                   # 1 executed, 0 rejected by a require, gas spent either way
        raise RuntimeError("The transaction was reverted")

    print("Recorded in block " + str(receipt.blockNumber) +
          ", gas used " + str(receipt.gasUsed))
    return receipt


def main():
    if len(sys.argv) < 3:                     # argv[0] is the program name
        print("Usage: blockchain.py <story-id> <commit>", file=sys.stderr)
        return 2
    record_tests_passed(sys.argv[1], sys.argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())