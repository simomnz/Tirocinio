// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.8.18 <0.9.0;

import "remix_tests.sol";
import "../contracts/Hiring_Smart_Contract.sol";

//File di base per tutti i test


//Gestione del tempo nei test
contract SkillSelectionTestabile is SkillSelection {
    uint public tempoSimulato;

    constructor(uint _durata, uint[] memory _skill) SkillSelection(_durata, _skill) {}

    //Imposta l'ora vista dal contratto
    function impostaTempo(uint _istante) external {
        tempoSimulato = _istante;
    }

    //Ora simulata se impostata, altrimenti quella vera
    function _now() internal view override returns (uint) {
        return tempoSimulato == 0 ? block.timestamp : tempoSimulato;
    }
}


//Attore che utilizza i contratti come sviluppatore o ente 
contract Attore {

    //Invia la candidatura
    function candidati(SkillSelection _hiring, address _nft) external {
        _hiring.application(_nft);
    }

    //Registra una competenza su uno sviluppatore
    function aggiungiSkill(Skill _nft, address _dev, uint _idSkill, uint _mesi, uint _punteggio) external {
        _nft.addSkill(_dev, _idSkill, _mesi, _punteggio);
    }

    //Abilita un nuovo ente certificatore
    function abilitaEnte(Skill _nft, address _ente) external {
        _nft.addCertifier(_ente);
    }

    //Legge la lista degli idonei
    function leggiLista(SkillSelection _hiring) external view returns (address[] memory) {
        return _hiring.exportDevList();
    }

    //Assume un candidato
    function assumi(SkillSelection _hiring, address _dev) external {
        _hiring.hiring(_dev);
    }
}


abstract contract BaseTest {
    

    //Durata in giorni della candidatura
    uint constant DURATA = 7;

    //Codici delle competenze
    uint constant SKILL_SOLIDITY = 1;
    uint constant SKILL_JAVA = 2;
    uint constant SKILL_PYTHON = 3;

    //Mesi e punteggio
    uint constant MESI = 12;
    uint constant PUNTEGGIO = 90;


    //Possibili Errori
    string constant ERR_CHIUSE = "Candidature Chiuse";
    string constant ERR_NON_CHIUSE = "Candidature Non Ancora Chiuse";
    string constant ERR_GIA_CANDIDATO = "Candidatura gia' inviata";
    string constant ERR_SENZA_COMPETENZE = "Nessuna competenza richiesta";
    string constant ERR_DURATA = "Durata non valida";
    string constant ERR_SOLO_PO = "Solo il Product Owner";
    string constant ERR_NON_IDONEO = "Il candidato non e' idoneo";
    string constant ERR_GIA_ASSUNTO = "Candidato gia' assunto";
    string constant ERR_SOLO_CERTIFICATI = "Solo enti certificati possono aggiungere competenze";
    string constant ERR_SOLO_PROPRIETARIO = "Solo il proprietario del contratto";

    //Output di verifica TEST
    string constant MSG_BLOCCATA = "Doveva essere bloccata";
    string constant MSG_MOTIVO = "Motivo sbagliato";
    string constant MSG_IDONEO = "Doveva essere idoneo";
    string constant MSG_NON_IDONEO = "Non doveva essere idoneo";
    string constant MSG_NON_REGISTRATA = "Candidatura non registrata";

    //attori
    Skill nft;
    SkillSelectionTestabile hiring;

    Attore devCompleto;   //ha tutte le competenze richieste
    Attore devParziale;   //ne ha solo una parte
    Attore devSenzaSkill; //non ne ha nessuna
    Attore estraneo;      //non partecipa alla selezione


    //Crea contratti e sviluppatori e apre la selezione
    function _prepara() internal {
        nft = new Skill();

        devCompleto = new Attore();
        devParziale = new Attore();
        devSenzaSkill = new Attore();
        estraneo = new Attore();

        nft.addSkill(address(devCompleto), SKILL_SOLIDITY, MESI, PUNTEGGIO);
        nft.addSkill(address(devCompleto), SKILL_JAVA, MESI, PUNTEGGIO);
        nft.addSkill(address(devParziale), SKILL_SOLIDITY, MESI, PUNTEGGIO);

        hiring = new SkillSelectionTestabile(DURATA, _skillRichieste());
    }

    //Competenze richieste
    function _skillRichieste() internal pure returns (uint[] memory richieste) {
        richieste = new uint[](2);
        richieste[0] = SKILL_SOLIDITY;
        richieste[1] = SKILL_JAVA;
    }

    //Fa finire il tempo della candidatura
    function _chiudiCandidature() internal {
        hiring.impostaTempo(hiring.startDate() + DURATA * 1 days);
    }

    //Controlla che l'operazione si blocchi
    function _deveBloccare(bool riuscita, string memory motivo, string memory atteso) internal {
        Assert.ok(!riuscita, MSG_BLOCCATA);
        if (!riuscita) {
            Assert.equal(motivo, atteso, MSG_MOTIVO);
        }
    }
}