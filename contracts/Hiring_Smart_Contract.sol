// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.8.18 <0.9.0;

import "./NFTSkill.sol";

contract SkillSelection {
    address owner;

    uint[] idSkill;

    address[] devAddress;
    uint contractDuration;
    
    // Prende la data di invio del contratto (quindi data di creazione del blocco)
    uint public startDate; 
    // Cercare come si crea una lista dinamica di skill e passarla al costruttore, in modo che l'aggiunta delle skill sia all'interno del costruttore

    // Costruttore
    constructor(uint _contractDuration, uint[] memory _idSkill) {
        owner = msg.sender;
        startDate =  block.timestamp;
        // Valore definito dall'utente creatore del contratto, che definisce i giorni possibili per proporsi
        contractDuration = _contractDuration;
    
        for(uint i = 0; i < _idSkill.length; i++) {
            idSkill.push(_idSkill[i]);
        }
    }
    
    modifier controlTime {
        require(block.timestamp < (startDate + contractDuration * 1 minutes), "Candidature Chiuse");
        _;
    }

    modifier earlyTime {
        require(block.timestamp >= (startDate + contractDuration * 1 minutes), "Candidature Non Ancora Chiuse");
        _;
    }

    modifier onlyOwner {
        require(msg.sender == owner);
        _;
    }

    event elegible(address developer, string suitable);

    function getSkillList() view public returns (uint [] memory){
        return idSkill;
    }

    function application(address SCSkillAddress) public controlTime {  

        uint[] memory requiredSkills = getSkillList(); 
        bool find;
        bool result = true;

        Skill SkillContract = Skill(SCSkillAddress);

        // Si controllano gli abbinamenti tra le skill
        for(uint i = 0; i<requiredSkills.length; i++) {
            uint j;
            find = false;
            while (j < SkillContract.getSkill(msg.sender).length && !find){
                if(requiredSkills[i] == SkillContract.getSkill(msg.sender)[j]) {
                    find = true;
                }
                j++;
            }
            result = find && result;

        }

        string memory suitable = "Candidatura Non Idonea";

        if(result == false) {
            suitable = "Candidatura Idonea";
        }

        emit elegible(msg.sender, suitable);
        // Quindi si inserisce l'address del candidati all'interno dell'array degli idonei
        devAddress.push(msg.sender);
    }

    function exportDevLkst() public view earlyTime onlyOwner returns(address[] memory) {
        return(devAddress);
    }

    event hired(address owner, address developer, string admission);

    function hiring(address developer) public onlyOwner {
        string memory admission = "E' stato assunto";
        emit hired(owner, developer, admission);
    }
}
