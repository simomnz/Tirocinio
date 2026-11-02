// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.8.18 <0.9.0;

import "./NFTSkill.sol";

contract SkillSelection {

    // the owner, readable by anyone
    address public owner;

    uint[] idSkill;

    address[] devAddress;
    uint public contractDuration;

    // who applied, and who came out eligible

    mapping(address => bool) public hasApplied;
    mapping(address => bool) public isEligible;

    // fix: a hiring stays recorded and cannot be repeated, which it could before
    mapping(address => bool) public isHired;

    // when the contract was published
    uint public startDate;

    constructor(uint _contractDuration, uint[] memory _idSkill) {
        // with no required skills anyone would come out eligible, and with a
        // duration of zero the applications would be closed straight away
        require(_contractDuration > 0, "Durata non valida");
        require(_idSkill.length > 0, "Nessuna competenza richiesta");

        owner = msg.sender;
        startDate = _now();
        // how long the contract runs before it expires
        contractDuration = _contractDuration;

        for(uint i = 0; i < _idSkill.length; i++) {
            idSkill.push(_idSkill[i]);
        }
    }

    // reads the time, pulled out into a function so a test can replace it
    function _now() internal view virtual returns (uint) {
        return block.timestamp;
    }

    // the duration counts in days
    modifier controlTime {
        require(_now() < (startDate + contractDuration * 1 days), "Candidature Chiuse");
        _;
    }

    modifier earlyTime {
        require(_now() >= (startDate + contractDuration * 1 days), "Candidature Non Ancora Chiuse");
        _;
    }

    // stops anyone who is not the owner
    modifier onlyOwner {
        require(msg.sender == owner, "Solo il Product Owner");
        _;
    }

    event elegible(address developer, string suitable);

    function getSkillList() view public returns (uint [] memory){
        return idSkill;
    }

    function application(address SCSkillAddress) public controlTime {

        // fix: a check that stops one candidate from applying several times and
        // appearing in the list more than once
        require(!hasApplied[msg.sender], "Candidatura gia' inviata");
        hasApplied[msg.sender] = true;

        uint[] memory requiredSkills = getSkillList();

        Skill SkillContract = Skill(SCSkillAddress);

        // tidied up: the candidate's skills are read once. getSkill used to be
        // called again on every turn of the loop
        uint[] memory devSkills = SkillContract.getSkill(msg.sender);

        bool result = true;

        // checks the required skills against the ones the candidate holds
        for(uint i = 0; i < requiredSkills.length; i++) {
            bool find = false;
            uint j = 0;
            while (j < devSkills.length && !find) {
                if(requiredSkills[i] == devSkills[j]) {
                    find = true;
                }
                j++;
            }
            result = find && result;
        }

        // the important fix. The condition was the wrong way round, result == false,
        // so an eligible application was announced as not eligible and the other
        // way round. What was here before:
        //
        //   string memory suitable = "Candidatura Non Idonea";
        //   if(result == false) {
        //       suitable = "Candidatura Idonea";
        //   }
        string memory suitable = "Candidatura Non Idonea";

        // and only the eligible candidates go into the list now, where before
        // every one of them did

        if(result) {
            suitable = "Candidatura Idonea";
            isEligible[msg.sender] = true;
            devAddress.push(msg.sender);
        }

        emit elegible(msg.sender, suitable);
    }

    function exportDevList() public view earlyTime onlyOwner returns(address[] memory) {
        return devAddress;
    }

    event hired(address owner, address developer, string admission);

    // fix: the product owner could hire anybody before, including someone who
    // was not eligible or had never applied
    function hiring(address developer) public earlyTime onlyOwner {
        require(isEligible[developer], "Il candidato non e' idoneo");
        require(!isHired[developer], "Candidato gia' assunto");
        isHired[developer] = true;
        string memory admission = "E' stato assunto";
        emit hired(owner, developer, admission);
    }
}
