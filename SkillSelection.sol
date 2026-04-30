// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.8.18 <0.9.0;

// AGGIUNTO: Un'interfaccia per interagire con l'altro contratto. 
// È più professionale e "pulito" rispetto a chiamare il contratto intero.
interface INFTSkill {
    function getSkill(address _developer) external view returns (uint[] memory);
}

contract SkillSelection {
    address public owner; // CAMBIATO: Messa public per poterla consultare facilmente
    uint[] public idSkill;
    address[] public devAddress;
    uint public contractDuration;
    uint public startDate; 

    constructor(uint _contractDuration, uint[] memory _idSkill) {
        owner = msg.sender;
        startDate = block.timestamp;
        contractDuration = _contractDuration;
        
        // CAMBIATO: Invece di fare un ciclo for e fare idSkill.push uno alla volta, 
        // puoi assegnare l'intero array in un colpo solo. Risparmi gas e righe di codice.
        idSkill = _idSkill;
    }
    
    modifier controlTime() {
        require(block.timestamp < (startDate + contractDuration * 1 minutes), "Candidature Chiuse");
        _;
    }

    modifier earlyTime() {
        require(block.timestamp >= (startDate + contractDuration * 1 minutes), "Candidature Non Ancora Chiuse");
        _;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Non sei il proprietario");
        _;
    }

    // CAMBIATO: Corretto il typo da "elegible" a "Eligible" (standard Solidity)
    event Eligible(address developer, string status);
    event Hired(address owner, address developer, string admission);

    function getSkillList() view public returns (uint[] memory) {
        return idSkill;
    }

    function application(address SCSkillAddress) public controlTime {  
        // AGGIUNTO: Carichiamo le skill richieste in memoria una sola volta
        uint[] memory requiredSkills = idSkill; 
        
        // CAMBIATO: Carichiamo le skill del candidato in memoria PRIMA del ciclo.
        // Nel codice originale chiamavi SkillContract.getSkill() dentro ogni iterazione:
        // era un salasso di Gas pazzesco! Ora la chiamata esterna è una sola.
        INFTSkill skillContract = INFTSkill(SCSkillAddress);
        uint[] memory devSkills = skillContract.getSkill(msg.sender);
        
        bool allSkillsFound = true;

        // CAMBIATO: Logica dei cicli semplificata.
        for(uint i = 0; i < requiredSkills.length; i++) {
            bool found = false;
            
            // AGGIUNTO: Inizializzazione esplicita di j (nell'originale era uint j e basta)
            for(uint j = 0; j < devSkills.length; j++) {
                if(requiredSkills[i] == devSkills[j]) {
                    found = true;
                    break; // Ottimizzazione: se la troviamo, passiamo alla prossima skill richiesta
                }
            }
            
            // Se anche una sola skill richiesta non viene trovata, il candidato fallisce
            if(!found) {
                allSkillsFound = false;
                break;
            }
        }

        // CAMBIATO: Logica di idoneità corretta. 
        // Prima avevi: if(result == false) { suitable = "Idonea" }. Era invertito!
        string memory suitable;
        if(allSkillsFound) {
            suitable = "Candidatura Idonea";
            devAddress.push(msg.sender);
        } else {
            suitable = "Candidatura Non Idonea";
            // AGGIUNTO: Se non è idoneo, facciamo fallire la transazione? 
            // Per ora lasciamo che emetta l'evento come l'originale, ma correggiamo il testo.
        }

        emit Eligible(msg.sender, suitable);
    }

    // CAMBIATO: Corretto il nome da "exportDevLkst" a "exportDevList"
    function exportDevList() public view earlyTime onlyOwner returns(address[] memory) {
        return devAddress;
    }

    function hiring(address developer) public onlyOwner {
        string memory admission = "E' stato assunto";
        emit Hired(owner, developer, admission);
    }
}