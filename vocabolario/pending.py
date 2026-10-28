# lists the user stories whose delivery is waiting to be verified, so that the
# verification is started by Jenkins reading the chain, and never by a person
# choosing which task and which repository to look at.
#
#   python3 pending.py            prints one identifier per line
#   python3 pending.py --mark 0   notes the delivery currently declared for 0
#
# The chain cannot call out, so somebody has to go and look: this is what
# Jenkins runs on a timer. The note keeps a delivery that did not pass from
# being verified again at every round, which would fill the task with
# identical comments.

import json
import os
import sys

import blockchain

# the note lives outside the workspace, which Jenkins wipes between builds
STATE = os.environ.get(
    "VERIFY_STATE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "attempted.json"))


# the key of a delivery in the note. The identifier alone is not enough:
# every contract numbers its user stories from zero, so the same number
# belongs to a different delivery on each of them
def key_for(contract, story_id):
    return contract.address.lower() + ":" + str(story_id)


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}                             # the first run has nothing to remember


def save_state(state):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


# the user stories with a delivery nobody has verified yet
def pending():
    _, contract = blockchain.connect()

    if not blockchain.is_invited(contract):   # whoever started the job cannot point it at a contract that did not ask
        raise RuntimeError("This contract does not list us as a verifier")

    count = contract.functions.userStoryCount().call()
    state = load_state()

    waiting = []
    for story_id in range(count):
        story = blockchain.read_story(contract, story_id)

        if not story["taken"] or not story["workSubmitted"]:
            continue                          # nothing has been delivered
        if story["paid"]:
            continue
        if contract.functions.getApprovals(story_id).call()[0]:
            continue                          # the tests are already recorded on chain

        if ":" not in story["externalRef"]:   # nobody has linked it to a task yet, so there are no criteria to run
            print("User story " + str(story_id) + " has a delivery but no task "
                  "linked to it, skipped", file=sys.stderr)   # said out loud: it is a mistake somebody has to fix
            continue

        if state.get(key_for(contract, story_id)) == story["commit"].hex():
            continue                          # this very delivery was already tried

        waiting.append(story_id)

    return waiting


# remembers which delivery was tried, by commit and not by identifier, so that
# a developer who delivers again is verified again
def mark(story_id):
    _, contract = blockchain.connect()
    story = blockchain.read_story(contract, int(story_id))

    state = load_state()
    state[key_for(contract, story_id)] = story["commit"].hex()
    save_state(state)


def main():
    try:
        if "--mark" in sys.argv:
            position = sys.argv.index("--mark") + 1
            if position >= len(sys.argv):
                print("--mark needs the identifier on the chain", file=sys.stderr)
                return 2
            mark(sys.argv[position])
            return 0

        for story_id in pending():
            print(story_id)                   # one per line, so the shell can loop on it

    except Exception as error:                # one line instead of forty of traceback
        print(str(error), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
