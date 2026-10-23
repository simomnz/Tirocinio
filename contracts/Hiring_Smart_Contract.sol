// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.8.18 <0.9.0;

import "./NFTSkill.sol";

contract SkillSelection {

    // owner Pubblico
    address public owner;

    uint[] idSkill;

    address[] devAddress;
    uint public contractDuration;

    // registro di chi si e' candidato e di chi e' risultato idoneo

    mapping(address => bool) public hasApplied;
    mapping(address => bool) public isEligible;

    // correzione:l'assunzione resta registrata e non puo' essere ripetuta (prima poteva essere ripetuta)
    mapping(address => bool) public isHired;

    // data di invio del contratto 
    uint public startDate;

    constructor(uint _contractDuration, uint[] memory _idSkill) {
        // senza competenze richieste chiunque risulterebbe idoneo,e con durata 0 le candidature sarebbero chiuse subito
        require(_contractDuration > 0, "Durata non valida");
        require(_idSkill.length > 0, "Nessuna competenza richiesta");

        owner = msg.sender;
        startDate = _now();
        // durata del contratto prima di scadere
        contractDuration = _contractDuration;

        for(uint i = 0; i < _idSkill.length; i++) {
            idSkill.push(_idSkill[i]);
        }
    }

    // get del tempo
    function _now() internal view virtual returns (uint) {
        return block.timestamp;
    }

    // durata del contratto settata a 1 giorno come placeholder
    modifier controlTime {
        require(_now() < (startDate + contractDuration * 1 days), "Candidature Chiuse");
        _;
    }

    modifier earlyTime {
        require(_now() >= (startDate + contractDuration * 1 days), "Candidature Non Ancora Chiuse");
        _;
    }

    // messaggio di errore
    modifier onlyOwner {
        require(msg.sender == owner, "Solo il Product Owner");
        _;
    }

    event elegible(address developer, string suitable);

    function getSkillList() view public returns (uint [] memory){
        return idSkill;
    }

    function application(address SCSkillAddress) public controlTime {

        // correzione: controllo  che non permette a un candidato di candidarsi piu' volte e comparire piu' volte nella lista
        require(!hasApplied[msg.sender], "Candidatura gia' inviata");
        hasApplied[msg.sender] = true;

        uint[] memory requiredSkills = getSkillList();

        Skill SkillContract = Skill(SCSkillAddress);

        // ottimizzazione: le competenze del candidato si leggono una sola volta,  prima getSkill veniva richiamata a ogni ciclo 
        uint[] memory devSkills = SkillContract.getSkill(msg.sender);

        bool result = true;

        // controllo gli abbinamenti tra le skill
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

        // CORREZIONE IMPORTANTE 
        //la condizione era invertita: result = false

        //string memory suitable = "Candidatura Non Idonea";       rimasto uguale
        //if(result == false) {
        //    suitable = "Candidatura Idonea";
        //}

        // veniva emesso "Candidatura Idonea" e viceversa.
        string memory suitable = "Candidatura Non Idonea";

        //  adesso solo i candidati idonei entrano nella lista, prima entravano tutti 

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

    // correzuione: prima il Product Owner poteva assumere chiunque, compreso chi non era idobneo o non si era candidato (non so se fosse voluto)
    function hiring(address developer) public earlyTime onlyOwner {
        require(isEligible[developer], "Il candidato non e' idoneo");
        require(!isHired[developer], "Candidato gia' assunto");
        isHired[developer] = true;
        string memory admission = "E' stato assunto";
        emit hired(owner, developer, admission);
    }
}
