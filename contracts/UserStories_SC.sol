// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.8.18 <0.9.0;

import "./NFTSkill.sol";
import "./Hiring_Smart_Contract.sol";

contract UserStories {

    // --- chi puo' fare cosa ---
    address public owner;          // chi ha pubblicato il contratto
    address public verifier;       // il sistema di verifica automatica
    address public productOwner;   // firma dopo aver revisionato il lavoro
    address public client;         // opzionale: a zero significa "non previsto"

    uint public dimUSList;

    struct UserStory {
        uint[] idSkills;
        uint effort;
        uint payment;
        bool status;                 // presa in carico
        bool[3] paymentAuthorized;   // 0 verificatore, 1 Product Owner, 2 cliente
        bool payed;
        bool funded;                 // il denaro e' depositato nel contratto
        address developer;
        address funder;              // chi ha depositato, per l'eventuale rimborso
        bytes20 commit;              // il commit Git che ha superato i test
    }

    mapping(uint => UserStory) public US;

    // --- eventi: cosi' il mondo esterno sa cosa succede ---
    event USFunded(uint indexed idUserStory, address funder, uint amount);
    event USRefunded(uint indexed idUserStory, address funder, uint amount);
    event USTaken(uint indexed idUserStory, address developer);
    event TestsPassed(uint indexed idUserStory, bytes20 commit);
    event PaymentAuthorized(uint indexed idUserStory, address signer, uint8 slot);
    event PaymentSent(uint indexed idUserStory, address developer, uint amount);

    constructor(
        uint[][] memory _idSkill,
        uint[] memory _effort,
        uint[] memory _payment,
        address _verifier,
        address _productOwner
    ) {
        owner = msg.sender;
        verifier = _verifier;
        productOwner = _productOwner;
        client = address(0);

        dimUSList = _idSkill.length;
        for (uint i = 0; i < dimUSList; i++) {
            US[i].idSkills = _idSkill[i];
            US[i].effort = _effort[i];
            US[i].payment = _payment[i];
        }
    }

    modifier OnlyOwner() {
        require(msg.sender == owner, "Solo il proprietario puo' farlo");
        _;
    }

    // Gli indirizzi dei firmatari si possono cambiare: un sistema di verifica
    // si sostituisce, un Product Owner cambia ruolo.
    function setVerifier(address _verifier) public OnlyOwner {
        verifier = _verifier;
    }

    function setProductOwner(address _productOwner) public OnlyOwner {
        productOwner = _productOwner;
    }

    function setClient(address _client) public OnlyOwner {
        client = _client;
    }

    // ------------------------------------------------------------
    // Deposito a garanzia
    // ------------------------------------------------------------

    // Il denaro viene immobilizzato nel contratto PRIMA che qualcuno lavori.
    // L'importo deve corrispondere esattamente a quello concordato: ne' meno
    // (lo sviluppatore verrebbe pagato meno del dovuto) ne' piu' (l'eccedenza
    // resterebbe bloccata).
    function fundUS(uint _idUserStory) public payable {
        require(_idUserStory < dimUSList, "User Story inesistente");
        require(US[_idUserStory].funded == false, "Gia' finanziata");
        require(msg.value == US[_idUserStory].payment, "Importo non corrispondente");

        US[_idUserStory].funded = true;
        US[_idUserStory].funder = msg.sender;

        emit USFunded(_idUserStory, msg.sender, msg.value);
    }

    // Via d'uscita: chi ha depositato puo' riprendersi i fondi solo finche'
    // nessuno ha preso in carico il lavoro. Dopo, il denaro non e' piu' suo.
    function refundUS(uint _idUserStory) public {
        require(US[_idUserStory].funded == true, "Non finanziata");
        require(US[_idUserStory].status == false, "Gia' presa in carico");
        require(US[_idUserStory].payed == false, "Gia' pagata");
        require(msg.sender == US[_idUserStory].funder, "Non sei tu ad aver depositato");

        uint amount = US[_idUserStory].payment;
        US[_idUserStory].funded = false;
        US[_idUserStory].funder = address(0);

        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        require(ok, "Rimborso fallito");

        emit USRefunded(_idUserStory, msg.sender, amount);
    }

    // ------------------------------------------------------------
    // Le firme
    // ------------------------------------------------------------

    // La firma del sistema di verifica, con il commit che ha superato i test.
    // E' l'unica automatica, e l'unica che porta con se' un dato.
       // La firma del sistema di verifica, con il commit che ha superato i test.
    // E' l'unica automatica, e l'unica che porta con se' un dato.
    function authorizeTests(uint _idUserStory, bytes20 _commit) public {
        require(msg.sender == verifier, "Solo il verificatore puo' firmare qui");
        require(US[_idUserStory].payed == false, "Gia' pagata");
        require(US[_idUserStory].status == true,
                "User Story non presa in carico");
        require(US[_idUserStory].paymentAuthorized[0] == false,
                "Test gia' firmati");

        US[_idUserStory].paymentAuthorized[0] = true;
        US[_idUserStory].commit = _commit;

        emit TestsPassed(_idUserStory, _commit);
        emit PaymentAuthorized(_idUserStory, msg.sender, 0);
    }

    // La firma umana: il Product Owner, e il cliente se previsto.
    // Il mittente decide da solo quale casella puo' firmare.
    function authorize(uint _idUserStory) public {
        require(US[_idUserStory].payed == false, "Gia' pagata");

        uint8 slot;
        if (msg.sender == productOwner) {
            slot = 1;
        } else if (client != address(0) && msg.sender == client) {
            slot = 2;
        } else {
            revert("Non sei autorizzato a firmare");
        }

        US[_idUserStory].paymentAuthorized[slot] = true;
        emit PaymentAuthorized(_idUserStory, msg.sender, slot);
    }

    // La firma del cliente serve solo se il cliente esiste.
    function isAuthorized(uint _idUserStory) public view returns (bool) {
        if (!US[_idUserStory].paymentAuthorized[0]) return false;
        if (!US[_idUserStory].paymentAuthorized[1]) return false;
        if (client != address(0) && !US[_idUserStory].paymentAuthorized[2]) return false;
        return true;
    }

    // Serve allo sviluppatore per sapere chi manca all'appello.
    function getAuthorizations(uint _idUserStory) public view returns (bool[3] memory) {
        return US[_idUserStory].paymentAuthorized;
    }

    // ------------------------------------------------------------
    // Selezione e presa in carico
    // ------------------------------------------------------------

    function getSkillsFromEmploymnetContract(address employmentAddress)
        public view returns (uint[] memory validSkills)
    {
        SkillSelection employmentContract = SkillSelection(employmentAddress);
        return (employmentContract.getSkillList());
    }

    function getAvailableUSList(address employmentAddress)
        public view returns (uint[] memory)
    {
        uint[] memory validUS = new uint[](dimUSList);
        uint[] memory employSkills = getSkillsFromEmploymnetContract(employmentAddress);
        uint validUSIndex = 0;

        for (uint usIndex = 0; usIndex < dimUSList; usIndex++) {
            // una user story non finanziata o gia' presa non e' disponibile
            if (!US[usIndex].funded || US[usIndex].status) continue;

            uint counter = 0;
            for (uint i = 0; i < US[usIndex].idSkills.length; i++) {
                uint currentSkill = US[usIndex].idSkills[i];
                for (uint j = 0; j < employSkills.length; j++) {
                    if (employSkills[j] == currentSkill) {
                        counter++;
                        break;
                    }
                }
            }
            if (counter == US[usIndex].idSkills.length) {
                validUS[validUSIndex] = usIndex;
                validUSIndex++;
            }
        }
        return validUS;
    }

    function USSelection(address employmentAddress, uint[] memory _idSelected) public {
        uint[] memory employSkills = getSkillsFromEmploymnetContract(employmentAddress);

        for (uint i = 0; i < _idSelected.length; i++) {
            uint targetId = _idSelected[i];

            // Lo sviluppatore puo' prendere in carico solo lavoro gia' pagato
            // nel contratto: e' la sua garanzia, e non deve fidarsi di nessuno
            // per averla.
            require(US[targetId].funded, "User Story non finanziata");
            require(!US[targetId].status, "User Story gia' presa in carico");

            uint counter = 0;
            for (uint k = 0; k < US[targetId].idSkills.length; k++) {
                for (uint j = 0; j < employSkills.length; j++) {
                    if (employSkills[j] == US[targetId].idSkills[k]) {
                        counter++;
                        break;
                    }
                }
            }

            if (counter == US[targetId].idSkills.length) {
                US[targetId].status = true;
                US[targetId].developer = msg.sender;
                emit USTaken(targetId, msg.sender);
            }
        }
    }

    function getTotalUSList() public view OnlyOwner returns (UserStory[] memory) {
        UserStory[] memory us = new UserStory[](dimUSList);
        for (uint i = 0; i < dimUSList; i++) {
            us[i] = US[i];
        }
        return (us);
    }

    function getAddressUSList(address developer)
        public view OnlyOwner returns (UserStory[] memory)
    {
        uint dimUSListAddress = 0;
        for (uint i = 0; i < dimUSList; i++) {
            if (developer == US[i].developer) {
                dimUSListAddress++;
            }
        }

        UserStory[] memory usAddress = new UserStory[](dimUSListAddress);
        uint counter = 0;
        for (uint i = 0; i < dimUSList; i++) {
            if (developer == US[i].developer) {
                usAddress[counter] = US[i];
                counter++;
            }
        }
        return (usAddress);
    }

    function addUS(uint[] memory _idSkill, uint _effort, uint _payment)
        public OnlyOwner returns (uint)
    {
        US[dimUSList].idSkills = _idSkill;
        US[dimUSList].effort = _effort;
        US[dimUSList].payment = _payment;
        dimUSList++;
        return (dimUSList);
    }

    // ------------------------------------------------------------
    // Pagamento
    // ------------------------------------------------------------

    // Non e' piu' payable: i fondi sono gia' nel contratto dal momento del
    // deposito, chi chiama non deve portare denaro.
    function sendPayment(uint _idUserStory) public {
        require(US[_idUserStory].payed == false, "Gia' pagato");
        require(US[_idUserStory].funded == true, "Non finanziata");
        require(isAuthorized(_idUserStory), "Mancano autorizzazioni");
        require(
            US[_idUserStory].developer == msg.sender || owner == msg.sender,
            "Non sei autorizzato a riscuotere"
        );

        // si scrive prima e si trasferisce dopo: difesa contro il rientro
        US[_idUserStory].payed = true;

        uint amount = US[_idUserStory].payment;
        address devAddress = US[_idUserStory].developer;

        // call e non transfer: transfer concede solo 2300 di gas e fallirebbe
        // se lo sviluppatore riceve su un portafoglio che e' un contratto
        (bool ok, ) = payable(devAddress).call{value: amount}("");
        require(ok, "Trasferimento fallito");

        emit PaymentSent(_idUserStory, devAddress, amount);
    }
}
