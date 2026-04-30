// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.8.18 <0.9.0;

//import "https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC721/ERC721.sol";

// Si crea un token contenente ogni singola skill di ogni professionista
contract Skill{ //is ERC721 {

    address public owner;

    // Si definisce la struttura con l'id e i dati della skill (compresi i punteggi)
    struct SkillData {
        uint idSkill;
        uint duration;
        uint generalScore;
    }

    struct ListSkills {
        mapping(uint => SkillData) skills;
        uint numberOfSkills;
    }

    // Si definisce la funzione per la gestione del curriculum (ERC20 Curriculum Token)
    constructor() { //ERC721("skill", "SCT") {
        owner = msg.sender;
    }

    // Mappa le skill per ogni utente
    // mapping(uint => certificate) skillGroup;
    // mapping(uint => address) skillOwner;
    mapping(address => ListSkills) public skillList;

    function getSkill(address developer) public view returns(uint[] memory) {
        uint[] memory skills = new uint[](skillList[developer].numberOfSkills);
        for(uint i = 0; i < skillList[developer].numberOfSkills; i++) {
            skills[i] = (skillList[developer].skills[i].idSkill);
        }
        return (skills);
    }

    
    function addSkill(address developer, uint _idSkill, uint _duration, uint _generalScore) public {
        uint numberOfSkillsTemp = skillList[developer].numberOfSkills;

        skillList[developer].skills[numberOfSkillsTemp].idSkill = _idSkill;
        skillList[developer].skills[numberOfSkillsTemp].duration = _duration;
        skillList[developer].skills[numberOfSkillsTemp].generalScore = _generalScore;
        
        skillList[developer].numberOfSkills += 1;
    }
    
}