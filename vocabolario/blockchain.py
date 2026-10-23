# Firma sulla blockchain l'esito dei test automatici.
#
# E' l'anello che il verificatore percorre da solo: quando tutti i criteri
# automatici passano, scrive sullo smart contract che la user story ha
# superato i test, insieme al commit che li ha superati.
#
# Prima di spendere gas controlla due cose, leggendo dal contratto: che la
# user story sia stata presa in carico da uno sviluppatore, e che i test non
# siano gia' firmati. Le letture sono gratuite, le scritture no.
#
#   python3 blockchain.py 1 20df34d

import os
import sys

from web3 import Web3

RPC = os.environ.get("SEPOLIA_RPC", "https://ethereum-sepolia-rpc.publicnode.com")
VERIFIER_KEY = os.environ.get("VERIFIER_KEY", "")
CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS", "")

ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "_idUserStory", "type": "uint256"},
            {"internalType": "bytes20", "name": "_commit", "type": "bytes20"},
        ],
        "name": "authorizeTests",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "_idUserStory", "type": "uint256"},
        ],
        "name": "getAuthorizations",
        "outputs": [{"internalType": "bool[3]", "name": "", "type": "bool[3]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "name": "US",
        "outputs": [
            {"internalType": "uint256", "name": "effort", "type": "uint256"},
            {"internalType": "uint256", "name": "payment", "type": "uint256"},
            {"internalType": "bool", "name": "status", "type": "bool"},
            {"internalType": "bool", "name": "payed", "type": "bool"},
            {"internalType": "bool", "name": "funded", "type": "bool"},
            {"internalType": "address", "name": "developer", "type": "address"},
            {"internalType": "address", "name": "funder", "type": "address"},
            {"internalType": "bytes20", "name": "commit", "type": "bytes20"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def to_bytes20(commit):
    """Il commit sullo smart contract occupa venti byte esatti."""
    text = commit.lower().replace("0x", "")
    text = (text + "0" * 40)[:40]
    return bytes.fromhex(text)


def connect():
    w3 = Web3(Web3.HTTPProvider(RPC))
    if not w3.is_connected():
        raise RuntimeError("Cannot reach the node: " + RPC)

    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS),
                               abi=ABI)
    return w3, contract


def sign_tests(story_id, commit):
    if not VERIFIER_KEY or not CONTRACT_ADDRESS:
        raise RuntimeError("VERIFIER_KEY or CONTRACT_ADDRESS not set")

    story_id = int(story_id)
    w3, contract = connect()

    # --- controlli gratuiti, prima di spendere ---
    story = contract.functions.US(story_id).call()
    status, payed, developer = story[2], story[3], story[5]

    if payed:
        print("User story " + str(story_id) + " is already paid, nothing to sign")
        return None

    if not status:
        print("User story " + str(story_id) + " has not been taken by any "
              "developer, nothing to sign")
        return None

    if contract.functions.getAuthorizations(story_id).call()[0]:
        print("User story " + str(story_id) + " is already signed, "
              "no transaction sent")
        return None

    # --- la firma, che costa ---
    account = w3.eth.account.from_key(VERIFIER_KEY)
    call = contract.functions.authorizeTests(story_id, to_bytes20(commit))
    transaction = call.build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": w3.eth.chain_id,
    })

    signed = account.sign_transaction(transaction)
    # web3 ha cambiato il nome del campo fra la versione 6 e la 7
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction

    digest = w3.eth.send_raw_transaction(raw)
    print("Signing from  " + account.address)
    print("Developer     " + developer)
    print("Transaction   https://sepolia.etherscan.io/tx/" + digest.hex())
    print("Waiting for the block...")

    receipt = w3.eth.wait_for_transaction_receipt(digest, timeout=180)
    if receipt.status != 1:
        raise RuntimeError("The transaction was reverted")

    print("Signed in block " + str(receipt.blockNumber) +
          ", gas used " + str(receipt.gasUsed))
    return receipt


def main():
    if len(sys.argv) < 3:
        print("Usage: blockchain.py <story-id> <commit>", file=sys.stderr)
        return 2
    sign_tests(sys.argv[1], sys.argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
