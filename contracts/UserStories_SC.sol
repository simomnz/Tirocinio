// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.8.18 <0.9.0;

import "./NFTSkill.sol";
import "./Hiring_Smart_Contract.sol";

contract UserStories {

    // who is allowed to do what
    address public owner;          // published the contract
    address public productOwner;   // signs after reviewing the work
    address public client;         // optional, zero means "not used"

    // several verifiers are allowed, so that signatures can be produced in
    // parallel without competing for the same nonce, and so that a compromised
    // key can be replaced without stopping the system
    mapping(address => bool) public verifiers;

    uint public userStoryCount;

    // how long the product owner has to review, counted from the moment the
    // automated criteria were recorded. After that the silence counts as a
    // yes and the developer can collect: a stalemate must not freeze the money
    uint public constant REVIEW_WINDOW = 14 days;

    // how long a developer has to deliver: effort is a class, one week each,
    // so 1 is a week and 3 are three. After that he can no longer deliver,
    // and the money stays in the contract: it only ever moves forward
    uint public constant WEEKS_PER_EFFORT = 1 weeks;

    struct UserStory {
        uint[] requiredSkills;
        uint effort;
        uint payment;              // in wei
        bool funded;               // the money is held by this contract
        bool taken;                // a developer has claimed it
        bool workSubmitted;        // the developer has declared a delivery
        bool paid;
        bool[3] approvals;         // 0 tests, 1 product owner, 2 client
        address developer;
        address funder;            // who deposited, for a possible refund
        uint claimedAt;            // when a developer took it, zero when free
        uint testsPassedAt;        // when the automated criteria were recorded
        bytes20 commit;            // the Git commit declared by the developer
        bytes32 criteriaHash;      // keccak of the acceptance criteria, frozen before the work starts
        string externalRef;        // the task this story maps to, e.g. "openproject:1117"
    }

    // not public: the automatic getter returns the fields one by one, and with
    // this many it no longer fits. getUserStory returns the whole thing, and
    // brings along requiredSkills and approvals, which that getter skipped
    mapping(uint => UserStory) internal userStories;

    event UserStoryFunded(uint indexed id, address funder, uint amount);
    event UserStoryRefunded(uint indexed id, address funder, uint amount);
    event UserStoryClaimed(uint indexed id, address developer);
    event ClaimExpired(uint indexed id, address developer);
    event WorkSubmitted(uint indexed id, address developer, bytes20 commit);   // this is what starts the verification
    event TestsPassed(uint indexed id, bytes20 commit, bytes32 criteriaHash);
    event CriteriaHashSet(uint indexed id, bytes32 criteriaHash);
    event DeliveryApproved(uint indexed id, address signer, uint8 slot);
    event PaymentReleased(uint indexed id, address developer, uint amount);
    event ExternalRefSet(uint indexed id, string externalRef);

    // creates the initial user stories and sets who will be allowed to sign
    constructor(
        uint[][] memory _requiredSkills,
        uint[] memory _effort,
        uint[] memory _payment,
        address _verifier,
        address _productOwner
    ) {
        owner = msg.sender;
        productOwner = _productOwner;
        client = address(0);        // enabled later with setClient, if needed
        verifiers[_verifier] = true;

        userStoryCount = _requiredSkills.length;
        for (uint i = 0; i < userStoryCount; i++) {
            userStories[i].requiredSkills = _requiredSkills[i];
            userStories[i].effort = _effort[i];
            userStories[i].payment = _payment[i];
        }
    }

    // stops anyone who is not the owner, then _ runs the function body
    modifier onlyOwner() {
        require(msg.sender == owner, "Only the owner can do this");
        _;
    }

    modifier onlyVerifier() {
        require(verifiers[msg.sender], "Only a verifier can do this");
        _;
    }

    // ------------------------------------------------------------
    // Roles
    // ------------------------------------------------------------

    function addVerifier(address _verifier) public onlyOwner {
        verifiers[_verifier] = true;
    }

    function removeVerifier(address _verifier) public onlyOwner {
        verifiers[_verifier] = false;
    }

    function setProductOwner(address _productOwner) public onlyOwner {
        productOwner = _productOwner;
    }

    function setClient(address _client) public onlyOwner {
        client = _client;
    }

    // ------------------------------------------------------------
    // Link to the project management system
    // ------------------------------------------------------------

    // records which task this user story corresponds to, so that the mapping
    // lives in one place instead of being written by hand on both sides
    function setExternalRef(uint _id, string calldata _externalRef) public onlyOwner {
        require(_id < userStoryCount, "No such user story");
        userStories[_id].externalRef = _externalRef;
        emit ExternalRefSet(_id, _externalRef);
    }

    // freezes the acceptance criteria by their keccak. It can only be done
    // before a developer takes the work, so that the criteria somebody is
    // judged on are the ones that existed when they accepted the job
    function setCriteriaHash(uint _id, bytes32 _criteriaHash) public onlyOwner {
        require(_id < userStoryCount, "No such user story");
        require(userStories[_id].taken == false, "Work already started");

        userStories[_id].criteriaHash = _criteriaHash;
        emit CriteriaHashSet(_id, _criteriaHash);
    }

    // ------------------------------------------------------------
    // Escrow
    // ------------------------------------------------------------

    // locks the money in the contract before anyone starts working
    function fundUserStory(uint _id) public payable {
        require(_id < userStoryCount, "No such user story");
        require(userStories[_id].funded == false, "Already funded");
        require(msg.value == userStories[_id].payment, "Amount does not match");   // not less, not more
        require(userStories[_id].criteriaHash != bytes32(0),
                "The acceptance criteria have not been frozen");   // money goes in last, when what has to be done is settled

        userStories[_id].funded = true;
        userStories[_id].funder = msg.sender;                  // so we know who to pay back

        emit UserStoryFunded(_id, msg.sender, msg.value);
    }

    // gives the money back, but only while nobody has claimed the work
    function refundUserStory(uint _id) public {
        require(userStories[_id].funded == true, "Not funded");
        require(userStories[_id].taken == false, "Already claimed");   // after this point the money is no longer the funder's
        require(userStories[_id].paid == false, "Already paid");
        require(msg.sender == userStories[_id].funder, "You did not fund this");

        uint amount = userStories[_id].payment;
        userStories[_id].funded = false;                       // write first, transfer after
        userStories[_id].funder = address(0);

        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        require(ok, "Refund failed");                          // call does not revert by itself

        emit UserStoryRefunded(_id, msg.sender, amount);
    }

    // ------------------------------------------------------------
    // Claiming the work
    // ------------------------------------------------------------

    // asks an employment contract which skills the job requires
    function getRequiredSkills(address employmentAddress)
        public view returns (uint[] memory)
    {
        SkillSelection employmentContract = SkillSelection(employmentAddress);   // reads that address as a SkillSelection contract
        return employmentContract.getSkillList();
    }

    // lists the user stories a developer could claim
    function listAvailableUserStories(address employmentAddress)
        public view returns (uint[] memory)
    {
        uint[] memory available = new uint[](userStoryCount);   // as long as all of them, filled only in part
        uint[] memory skills = getRequiredSkills(employmentAddress);
        uint found = 0;

        for (uint id = 0; id < userStoryCount; id++) {
            if (!isAvailable(id)) continue;
            if (hasAllSkills(id, skills)) {
                available[found] = id;
                found++;
            }
        }
        return available;
    }

    // true when the given skills cover every skill the user story requires
    function hasAllSkills(uint _id, uint[] memory skills) internal view returns (bool) {
        uint matched = 0;
        for (uint i = 0; i < userStories[_id].requiredSkills.length; i++) {
            for (uint j = 0; j < skills.length; j++) {
                if (skills[j] == userStories[_id].requiredSkills[i]) {
                    matched++;
                    break;                                     // skill found, move to the next one
                }
            }
        }
        return matched == userStories[_id].requiredSkills.length;   // all of them, not just some
    }

    // assigns the chosen user stories to the caller
    function claimUserStories(address employmentAddress, uint[] memory _ids) public {
        uint[] memory skills = getRequiredSkills(employmentAddress);

        for (uint i = 0; i < _ids.length; i++) {
            uint id = _ids[i];

            // a developer can only claim work whose money is already locked in
            // the contract: that is the guarantee, and it does not depend on trust
            require(userStories[id].funded, "User story is not funded");
            require(isAvailable(id), "User story already claimed");   // being funded already implies frozen criteria
            require(hasAllSkills(id, skills), "Missing required skills");   // fails loudly instead of doing nothing

            userStories[id].taken = true;
            userStories[id].developer = msg.sender;
            userStories[id].claimedAt = block.timestamp;   // starts the clock for the delivery
            emit UserStoryClaimed(id, msg.sender);
        }
    }

    // true when the developer who took it has run out of time without
    // delivering. From that moment he can no longer deliver, and the product
    // owner can reopen the user story
    function claimExpired(uint _id) public view returns (bool) {
        if (!userStories[_id].taken) return false;
        if (userStories[_id].workSubmitted) return false;   // delivered in time, the verifier has it now
        if (userStories[_id].effort == 0) return false;     // no class, no clock

        return block.timestamp > userStories[_id].claimedAt +
                                 userStories[_id].effort * WEEKS_PER_EFFORT;
    }

    // true when somebody can take this user story right now. An expired claim
    // does not put it back by itself: the criteria have been seen by the
    // developer who dropped it, so the product owner reopens it on purpose
    function isAvailable(uint _id) public view returns (bool) {
        if (!userStories[_id].funded) return false;
        if (userStories[_id].paid) return false;
        return !userStories[_id].taken;
    }

    // puts an abandoned user story back on the market, with the criteria
    // stated again. They can be the same ones, but saying so is a decision
    // and it is written on the chain
    function reopenUserStory(uint _id, bytes32 _criteriaHash) public onlyOwner {
        require(claimExpired(_id), "The developer still has time");
        require(_criteriaHash != bytes32(0), "The criteria must be stated again");

        address previous = userStories[_id].developer;
        userStories[_id].taken = false;
        userStories[_id].developer = address(0);
        userStories[_id].claimedAt = 0;
        userStories[_id].criteriaHash = _criteriaHash;

        emit ClaimExpired(_id, previous);
        emit CriteriaHashSet(_id, _criteriaHash);
    }

    // ------------------------------------------------------------
    // Delivery and signatures
    // ------------------------------------------------------------

    // the developer declares which commit is the delivery, and the event this
    // emits is what starts the verification. The commit is therefore stated by
    // the person who signs, not chosen by whoever launches the verification
    function submitWork(uint _id, bytes20 _commit) public {
        require(msg.sender == userStories[_id].developer, "Not the assigned developer");
        require(claimExpired(_id) == false, "Your time to deliver has run out");
        require(userStories[_id].paid == false, "Already paid");
        require(userStories[_id].approvals[0] == false, "Tests already recorded");   // a new delivery is allowed until then

        userStories[_id].commit = _commit;
        userStories[_id].workSubmitted = true;

        emit WorkSubmitted(_id, msg.sender, _commit);
    }

    // records that the automated criteria passed on the declared commit.
    // It records an outcome, it does not authorise a payment
    function recordTestsPassed(uint _id, bytes20 _commit, bytes32 _criteriaHash)
        public onlyVerifier
    {
        require(userStories[_id].paid == false, "Already paid");
        require(userStories[_id].taken == true, "User story not claimed");
        require(userStories[_id].workSubmitted == true, "No delivery to verify");
        require(userStories[_id].commit == _commit, "Commit does not match the delivery");   // proves the tests ran on the declared code
        require(userStories[_id].approvals[0] == false, "Tests already recorded");   // written once only

        // the criteria that were run must be the ones frozen before the work
        // started. They cannot be missing: without them nobody could claim it
        require(userStories[_id].criteriaHash == _criteriaHash,
                "These are not the agreed criteria");

        userStories[_id].approvals[0] = true;
        userStories[_id].testsPassedAt = block.timestamp;   // starts the clock for the review

        emit TestsPassed(_id, _commit, _criteriaHash);
        emit DeliveryApproved(_id, msg.sender, 0);
    }

    // a person approves the delivery: the product owner, or the client if set
    function approveDelivery(uint _id) public {
        require(userStories[_id].paid == false, "Already paid");
        require(userStories[_id].approvals[0] == true, "Tests have not passed yet");   // the machine goes first, then the person

        uint8 slot;
        if (msg.sender == productOwner) {
            slot = 1;
        } else if (client != address(0) && msg.sender == client) {   // the client counts only when one is set
            slot = 2;
        } else {
            revert("You are not allowed to approve");          // revert undoes the whole transaction
        }

        userStories[_id].approvals[slot] = true;
        emit DeliveryApproved(_id, msg.sender, slot);
    }

    // true when the people who had to review have run out of time
    function reviewExpired(uint _id) public view returns (bool) {
        if (userStories[_id].testsPassedAt == 0) return false;      // the clock has not started
        return block.timestamp > userStories[_id].testsPassedAt + REVIEW_WINDOW;
    }

    // true when every signature that is needed is in place, or the time to
    // give it has run out. The tests are never waived: that one is the machine
    function isReadyForPayment(uint _id) public view returns (bool) {
        if (!userStories[_id].approvals[0]) return false;

        bool expired = reviewExpired(_id);
        if (!userStories[_id].approvals[1] && !expired) return false;
        if (client != address(0) && !userStories[_id].approvals[2] && !expired) return false;   // two signatures are enough without a client
        return true;
    }

    // returns the three boxes, to see who is still missing
    function getApprovals(uint _id) public view returns (bool[3] memory) {
        return userStories[_id].approvals;                     // written by hand because the automatic getter skips arrays
    }

    // ------------------------------------------------------------
    // Reading
    // ------------------------------------------------------------

    // returns one user story, every field of it
    function getUserStory(uint _id) public view returns (UserStory memory) {
        return userStories[_id];
    }

    // returns the skills a user story requires
    function getRequiredSkillsOf(uint _id) public view returns (uint[] memory) {
        return userStories[_id].requiredSkills;
    }

    // returns every user story in one call
    function listAllUserStories() public view onlyOwner returns (UserStory[] memory) {
        UserStory[] memory all = new UserStory[](userStoryCount);
        for (uint i = 0; i < userStoryCount; i++) {
            all[i] = userStories[i];
        }
        return all;
    }

    // returns the user stories assigned to one developer
    function listUserStoriesOf(address developer)
        public view onlyOwner returns (UserStory[] memory)
    {
        uint count = 0;
        for (uint i = 0; i < userStoryCount; i++) {            // first pass counts, because the length must be known up front
            if (developer == userStories[i].developer) count++;
        }

        UserStory[] memory result = new UserStory[](count);
        uint k = 0;
        for (uint i = 0; i < userStoryCount; i++) {            // second pass fills
            if (developer == userStories[i].developer) {
                result[k] = userStories[i];
                k++;
            }
        }
        return result;
    }

    // adds a user story after the contract has been published
    function addUserStory(
        uint[] memory _requiredSkills,
        uint _effort,
        uint _payment,
        string calldata _externalRef
    ) public onlyOwner returns (uint) {
        uint id = userStoryCount;                              // the new identifier is the current count
        userStories[id].requiredSkills = _requiredSkills;
        userStories[id].effort = _effort;
        userStories[id].payment = _payment;
        userStories[id].externalRef = _externalRef;
        userStoryCount++;
        emit ExternalRefSet(id, _externalRef);
        return id;                                             // the identifier, not the new total
    }

    // ------------------------------------------------------------
    // Payment
    // ------------------------------------------------------------

    // pays the developer out of the money already held by the contract
    function releasePayment(uint _id) public {                 // not payable: the caller brings no money
        require(userStories[_id].paid == false, "Already paid");
        require(userStories[_id].funded == true, "Not funded");
        require(isReadyForPayment(_id), "Missing approvals");
        require(
            userStories[_id].developer == msg.sender || owner == msg.sender,   // the developer is paid either way
            "You are not allowed to collect this"
        );

        userStories[_id].paid = true;                          // write first, transfer after, or it could be called again

        uint amount = userStories[_id].payment;
        address developer = userStories[_id].developer;

        // call and not transfer: transfer only forwards 2300 gas and would fail
        // when the developer receives on a contract wallet
        (bool ok, ) = payable(developer).call{value: amount}("");
        require(ok, "Transfer failed");

        emit PaymentReleased(_id, developer, amount);
    }
}
