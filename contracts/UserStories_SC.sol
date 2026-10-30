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

    // the employment contracts this one recognises. Before, the employment
    // contract was whatever address the caller handed in, so anyone could
    // write one for the occasion and answer the skill question however they
    // liked. Which contracts count is a decision of the owner, on chain
    mapping(address => bool) public employmentContracts;

    // where a developer's certified skills are read from. One registry,
    // chosen by the owner, and never an address supplied by whoever claims
    address public skillRegistry;

    // money a developer has earned but could not be sent, waiting to be taken
    // with withdraw(). A payment that cannot be delivered must not be able to
    // undo itself: the right stays written down here
    mapping(address => uint) public owed;

    uint public userStoryCount;

    // how long the product owner has to review, counted from the moment the
    // automated criteria were recorded. After that the silence counts as a
    // yes and the developer can collect: a stalemate must not freeze the money
    uint public constant REVIEW_WINDOW = 14 days;

    // how long a developer has to deliver: effort is a class, one week each,
    // so 1 is a week and 3 are three. After that he can no longer deliver,
    // and the product owner can put the user story back on the market
    uint public constant WEEKS_PER_EFFORT = 1 weeks;

    // how long a delivery made in time is protected after the deadline, so
    // that a slow verifier cannot cost a developer the work he handed in on
    // the last day. Past it the product owner can reopen, and the money is
    // free again: nothing in this contract may be locked forever
    uint public constant VERIFICATION_WINDOW = 3 days;

    // the largest effort a user story may carry, in weeks: a year. It is a
    // ceiling against a mistyped figure, not an opinion on how long work
    // takes. Without it an effort of a few billion is accepted, the deadline
    // lands past the end of the world, claimExpired is false for ever and
    // reopenUserStory can never be called: the same lock as effort zero
    uint public constant MAX_EFFORT = 52;

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
        uint submittedAt;          // when the delivery was declared, zero when none
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
    event PaymentOwed(uint indexed id, address developer, uint amount);   // the transfer did not get through, the credit is waiting
    event Withdrawn(address developer, uint amount);
    event ExternalRefSet(uint indexed id, string externalRef);
    event EmploymentContractAdded(address employment);
    event SkillRegistrySet(address skillRegistry);

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
            // effort zero would mean no deadline at all, and a user story
            // without a deadline can never be reopened: the money would have
            // no way out if the developer simply disappeared. A huge effort
            // does the same thing by the other door, and a mistyped figure is
            // enough: at a week each, a deadline nobody lives to see is a
            // deadline that never arrives
            require(_effort[i] > 0 && _effort[i] <= MAX_EFFORT,
                    "Effort must be between one and MAX_EFFORT");

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

    // declares an employment contract as one of ours. A developer can only
    // claim work through a contract that appears here
    function addEmploymentContract(address _employment) public onlyOwner {
        employmentContracts[_employment] = true;
        emit EmploymentContractAdded(_employment);
    }

    function removeEmploymentContract(address _employment) public onlyOwner {
        employmentContracts[_employment] = false;
    }

    // says where certified skills are read from
    function setSkillRegistry(address _skillRegistry) public onlyOwner {
        skillRegistry = _skillRegistry;
        emit SkillRegistrySet(_skillRegistry);
    }

    // ------------------------------------------------------------
    // Link to the project management system
    // ------------------------------------------------------------

    // records which task this user story corresponds to, so that the mapping
    // lives in one place instead of being written by hand on both sides
    function setExternalRef(uint _id, string calldata _externalRef) public onlyOwner {
        require(_id < userStoryCount, "No such user story");

        // only while nobody is working on it. This is what tells the verifier
        // which task to read, and therefore which repository to clone, and the
        // frozen hash covers the text of the criteria and not that link: with
        // criteria written to be reused, two tasks can share one hash, so
        // moving the link afterwards pointed the verification at other code
        // and no check noticed
        require(userStories[_id].taken == false, "Work already started");

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

    // asks an employment contract which skills the job it describes requires.
    // Informative only: these are the requirements of a hiring round, not the
    // skills of any developer, and nothing is ever authorised with them
    function getRequiredSkills(address employmentAddress)
        public view returns (uint[] memory)
    {
        SkillSelection employmentContract = SkillSelection(employmentAddress);   // reads that address as a SkillSelection contract
        return employmentContract.getSkillList();
    }

    // the skills certified for a developer, read from the registry the owner
    // configured. This is what a claim is checked against
    function certifiedSkills(address developer)
        public view returns (uint[] memory)
    {
        require(skillRegistry != address(0), "No skill registry configured");
        return Skill(skillRegistry).getSkill(developer);
    }

    // lists the user stories this developer could claim, by his own skills
    function listAvailableUserStories(address developer)
        public view returns (uint[] memory)
    {
        uint[] memory skills = certifiedSkills(developer);

        uint found = 0;
        for (uint id = 0; id < userStoryCount; id++) {          // first pass counts, so the array comes out the right length
            if (isAvailable(id) && hasAllSkills(id, skills)) found++;
        }

        uint[] memory available = new uint[](found);            // exactly as long as what was found: a trailing zero used to be indistinguishable from user story 0
        uint k = 0;
        for (uint id = 0; id < userStoryCount; id++) {
            if (isAvailable(id) && hasAllSkills(id, skills)) {
                available[k] = id;
                k++;
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

    // assigns the chosen user stories to the caller.
    //
    // Three things are checked, and none of them is in the caller's hands:
    // the employment contract must be one the owner recognises, that contract
    // must say this caller was hired, and the skills compared against the
    // user story are the caller's own certified ones. Before, the only check
    // read a list of skills out of an address the caller passed in, and
    // msg.sender appeared nowhere in it: any address could claim any funded
    // user story, declare a delivery, and be paid for it
    function claimUserStories(address employmentAddress, uint[] memory _ids) public {
        require(employmentContracts[employmentAddress], "Unknown employment contract");
        require(SkillSelection(employmentAddress).isHired(msg.sender),
                "You are not hired on this employment contract");

        uint[] memory skills;
        bool skillsRead = false;                           // read once, and only if some user story asks for skills

        for (uint i = 0; i < _ids.length; i++) {
            uint id = _ids[i];

            // a developer can only claim work whose money is already locked in
            // the contract: that is the guarantee, and it does not depend on trust
            require(userStories[id].funded, "User story is not funded");
            require(isAvailable(id), "User story already claimed");   // being funded already implies frozen criteria

            if (userStories[id].requiredSkills.length > 0) {
                if (!skillsRead) {
                    skills = certifiedSkills(msg.sender);
                    skillsRead = true;
                }
                require(hasAllSkills(id, skills), "Missing required skills");   // fails loudly instead of doing nothing
            }

            userStories[id].taken = true;
            userStories[id].developer = msg.sender;
            userStories[id].claimedAt = block.timestamp;   // starts the clock for the delivery
            emit UserStoryClaimed(id, msg.sender);
        }
    }

    // true when the developer who took it has run out of time. From that
    // moment he can no longer deliver, and the product owner can reopen.
    //
    // The clock is read off claimedAt and nothing else. It used to return
    // false as soon as workSubmitted was set, which did two unintended
    // things: the deadline cancelled itself after the first delivery, so a
    // developer could keep delivering months later; and claimExpired stayed
    // false forever, so reopenUserStory could never be called, refund was
    // already impossible on a claimed story, and payment needed tests that
    // never passed. Anyone could therefore wall the money in with two
    // transactions: claim it, declare a delivery, and never deliver
    function claimExpired(uint _id) public view returns (bool) {
        if (!userStories[_id].taken) return false;
        if (userStories[_id].effort == 0) return false;     // no class, no clock

        return block.timestamp > userStories[_id].claimedAt +
                                 userStories[_id].effort * WEEKS_PER_EFFORT;
    }

    // true while a delivery handed in before the deadline still has its
    // verification window. It protects work submitted on the last day from a
    // verifier that has not got to it yet, and it runs out, so it can never
    // become the permanent lock that workSubmitted used to be
    function verificationPending(uint _id) public view returns (bool) {
        if (!userStories[_id].workSubmitted) return false;
        if (userStories[_id].approvals[0]) return false;    // already recorded, the window is over
        return block.timestamp <= userStories[_id].submittedAt + VERIFICATION_WINDOW;
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

        // past this point the developer has a right that was earned, and the
        // work is not taken away from him: the money can only go forward
        require(userStories[_id].approvals[0] == false, "The tests have already passed");
        require(userStories[_id].paid == false, "Already paid");

        // and a delivery made in time is not thrown away while its
        // verification window is still open
        require(verificationPending(_id) == false,
                "A delivery made in time is still being verified");

        address previous = userStories[_id].developer;
        userStories[_id].taken = false;
        userStories[_id].developer = address(0);
        userStories[_id].claimedAt = 0;
        userStories[_id].criteriaHash = _criteriaHash;

        // the abandoned delivery goes with the claim, or the next developer
        // would inherit somebody else's commit as if it were his own
        userStories[_id].workSubmitted = false;
        userStories[_id].submittedAt = 0;
        userStories[_id].commit = bytes20(0);
        userStories[_id].testsPassedAt = 0;             // the require above proves it is already zero: written anyway, so the review clock cannot be inherited

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
        userStories[_id].submittedAt = block.timestamp;   // opens the verification window, which the deadline no longer cancels

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

    // returns every user story in one call.
    // Not restricted to the owner: every one of these fields is already
    // readable by anyone straight off the chain, so a modifier here would
    // only have suggested a privacy this contract does not have
    function listAllUserStories() public view returns (UserStory[] memory) {
        UserStory[] memory all = new UserStory[](userStoryCount);
        for (uint i = 0; i < userStoryCount; i++) {
            all[i] = userStories[i];
        }
        return all;
    }

    // returns the user stories assigned to one developer
    function listUserStoriesOf(address developer)
        public view returns (UserStory[] memory)
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
        // no effort means no deadline, and no deadline means no way to reopen.
        // The ceiling is there for the same reason: a deadline set far enough
        // away never arrives, and the money would stay in here for good
        require(_effort > 0 && _effort <= MAX_EFFORT,
                "Effort must be between one and MAX_EFFORT");

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

        // and when even call does not get through, the payment is not undone:
        // the right was earned and is written down as a credit the developer
        // withdraws when he can. A require here would have reverted the whole
        // transaction every time, for ever, and an address that cannot receive
        // would have been one more way to lock the money in this contract
        if (!ok) {
            owed[developer] += amount;
            emit PaymentOwed(_id, developer, amount);
        }

        emit PaymentReleased(_id, developer, amount);
    }

    // takes a credit left by a payment that could not get through. It is the
    // one place in this contract where the money moves on the asking of the
    // person it belongs to, so nothing else has to succeed for him to be paid
    function withdraw() public {
        uint amount = owed[msg.sender];
        require(amount > 0, "Nothing owed to you");

        owed[msg.sender] = 0;                                  // zeroed before the transfer, so a reentrant call finds nothing

        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        require(ok, "Transfer failed");                        // here reverting is right: the credit stays and can be taken later

        emit Withdrawn(msg.sender, amount);
    }
}
