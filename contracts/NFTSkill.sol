// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.8.18 <0.9.0;


contract Skill {

    // the address that published the contract
    address public owner;

    // fix: in the earlier version anyone could call addSkill. Whether that was
    // meant or not, it let anybody certify their own skills


    mapping(address => bool) public certifiers;

    // the shape of a skill
    struct SkillData {
        uint idSkill;
        uint duration;
        uint generalScore;
    }

    struct ListSkills {
        mapping(uint => SkillData) skills;
        uint numberOfSkills;
    }

    // the skills held by each user
    mapping(address => ListSkills) public skillList;

    event CertifierAdded(address certifier);
    event SkillAdded(address developer, uint idSkill);

    constructor() {
        owner = msg.sender;
        certifiers[msg.sender] = true;
    }

    modifier onlyOwner {
        require(msg.sender == owner, "Solo il proprietario del contratto");
        _;
    }

    modifier onlyCertifier {
        require(certifiers[msg.sender], "Solo enti certificati possono aggiungere competenze");
        _;
    }

    // the owner can add new certifiers
    function addCertifier(address certifier) public onlyOwner {
        certifiers[certifier] = true;
        emit CertifierAdded(certifier);
    }

    function getSkill(address developer) public view returns(uint[] memory) {
        uint[] memory skills = new uint[](skillList[developer].numberOfSkills);
        for(uint i = 0; i < skillList[developer].numberOfSkills; i++) {
            skills[i] = skillList[developer].skills[i].idSkill;
        }
        return skills;
    }

    // fix: onlyCertifier added here
    function addSkill(address developer, uint _idSkill, uint _duration, uint _generalScore) public onlyCertifier {
        uint numberOfSkillsTemp = skillList[developer].numberOfSkills;

        skillList[developer].skills[numberOfSkillsTemp].idSkill = _idSkill;
        skillList[developer].skills[numberOfSkillsTemp].duration = _duration;
        skillList[developer].skills[numberOfSkillsTemp].generalScore = _generalScore;

        skillList[developer].numberOfSkills += 1;

        emit SkillAdded(developer, _idSkill);
    }
}
