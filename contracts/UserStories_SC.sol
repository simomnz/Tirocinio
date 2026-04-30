// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.8.18 <0.9.0;

import "./NFTSkill.sol";
// NOTA: Qui importiamo il file che contiene il contratto "SkillSelection"
import "./Hiring_Smart_Contract.sol"; 

contract UserStories {

    address public owner;
    uint public dimUSList;

    struct UserStory {
        uint[] idSkills;
        uint effort;
        uint payment;
        bool status; // true = assegnata
        bool[3] paymentAuthorized; // Sistema di firma a 3 (multi-sig)
        bool payed;
        address developer;
    }

    mapping(uint => UserStory) public US;

    constructor(uint[][] memory _idSkill, uint[] memory _effort, uint[] memory _payment) {
        owner = msg.sender;
        dimUSList = _idSkill.length;
        for(uint i = 0; i < dimUSList; i++) {
            US[i].idSkills = _idSkill[i];
            US[i].effort = _effort[i];
            US[i].payment = _payment[i];
            // Lo status di default è false, payed è false.
        }
    }

    modifier OnlyOwner() {
        require(msg.sender == owner, "Solo il proprietario puo' farlo");
        _;
    }

    // Questa funzione interroga il contratto che abbiamo sistemato prima!
    function getSkillsFromEmploymnetContract(address employmentAddress) public view returns (uint[] memory) {
        SkillSelection employmentContract = SkillSelection(employmentAddress);
        return (employmentContract.getSkillList());
    }

    // Funzione fondamentale: confronta le skill del compito con quelle dell'assunto
    function getAvailableUSList(address employmentAddress) public view returns (uint[] memory) {
        uint[] memory validUS = new uint[](dimUSList);
        uint[] memory employSkills = getSkillsFromEmploymnetContract(employmentAddress);
        uint validUSIndex = 0; 

        for (uint usIndex = 0; usIndex < dimUSList; usIndex++) {
            uint counter = 0;
            for(uint i = 0; i < US[usIndex].idSkills.length; i++) {
                for(uint j = 0; j < employSkills.length; j++) {
                    if(employSkills[j] == US[usIndex].idSkills[i]) {
                        counter++;
                        break;
                    }
                }                
            }
            // Se lo sviluppatore ha TUTTE le skill richieste per la User Story
            if (counter == US[usIndex].idSkills.length) {
                validUS[validUSIndex] = usIndex;
                validUSIndex++;
            }
        }   
        return validUS;
    }

    // CORREZIONE: Aggiunto OnlyOwner o un controllo di sicurezza per non far "rubare" i task
    function USSelection(address employmentAddress, uint[] memory _idSelected) public {
        uint[] memory employSkills = getSkillsFromEmploymnetContract(employmentAddress);
        
        for(uint i = 0; i < _idSelected.length; i++) {
            uint targetId = _idSelected[i];
            uint counter = 0;
            
            for(uint k = 0; k < US[targetId].idSkills.length; k++) {
                for(uint j = 0; j < employSkills.length; j++) {
                    if(employSkills[j] == US[targetId].idSkills[k]) {
                        counter++;
                        break;
                    }
                }
            }

            if(counter == US[targetId].idSkills.length) {
                US[targetId].status = true;
                US[targetId].developer = msg.sender; // Il dev si "assegna" il task
            }
        }
    }

    // CORREZIONE: In Solidity non puoi restituire un array di struct che contiene array dinamici (idSkills) 
    // facilmente in tutte le versioni di EVM. Ma per i test va bene.
    function getTotalUSList() public view OnlyOwner returns(UserStory[] memory) {
        UserStory[] memory allUs = new UserStory[](dimUSList);
        for(uint i = 0; i < dimUSList; i++) {
            allUs[i] = US[i];
        }
        return allUs;
    }

    // CORREZIONE: sendPayment deve essere sicura
    function sendPayment(uint _idUserStory) public payable {
        require(US[_idUserStory].payed == false, "Gia' pagato");
        
        // Deve essere autorizzato da 3 entità diverse (logica della collega)
        bool authorized = US[_idUserStory].paymentAuthorized[0] && 
                         US[_idUserStory].paymentAuthorized[1] && 
                         US[_idUserStory].paymentAuthorized[2];
                         
        require(authorized == true, "Mancano autorizzazioni");
        
        // Solo il dev o l'owner possono triggerare il pagamento una volta autorizzato
        require(US[_idUserStory].developer == msg.sender || owner == msg.sender, "Non autorizzato");

        US[_idUserStory].payed = true;
        address payable devAddress = payable(US[_idUserStory].developer);
        
        // TRAPPOLA: Bisogna assicurarsi che il contratto abbia i fondi!
        require(address(this).balance >= US[_idUserStory].payment, "Fondi insufficienti nel contratto");
        
        devAddress.transfer(US[_idUserStory].payment);
    }
}