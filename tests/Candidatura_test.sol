// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.8.18 <0.9.0;

import "remix_tests.sol";
import "./BaseTest.sol";

//Apertura della selezione e candidature


//Test sull'apertura della selezione e sulle candidature
contract CandidaturaTest is BaseTest {

    
    function beforeEach() public {
        _prepara();
    }

    //Prova candidazione
    function _provaCandidatura(Attore candidato) internal returns (bool, string memory) {
        try candidato.candidati(hiring, address(nft)) {
            return (true, "");
        } catch Error(string memory motivo) {
            return (false, motivo);
        } catch {
            return (false, "");
        }
    }

    //Prova apertura selezione
    function _provaApertura(uint durata, uint[] memory competenze) internal returns (bool, string memory) {
        try new SkillSelectionTestabile(durata, competenze) returns (SkillSelectionTestabile) {
            return (true, "");
        } catch Error(string memory motivo) {
            return (false, motivo);
        } catch {
            return (false, "");
        }
    }


    //Salavataggio dei dati della selezione all'apertura
    function apertura_salvaIDati() public {
        uint[] memory competenze = hiring.getSkillList();

        Assert.equal(hiring.owner(), address(this), "Chi ha aperto la selezione e' sbagliato");
        Assert.equal(competenze.length, 2, "Numero di competenze sbagliato");
        Assert.equal(competenze[0], SKILL_SOLIDITY, "Prima competenza sbagliata");
        Assert.equal(competenze[1], SKILL_JAVA, "Seconda competenza sbagliata");
        Assert.ok(hiring.startDate() > 0, "Manca la data di inizio");
        Assert.equal(hiring.contractDuration(), DURATA, "Durata sbagliata");
    }


    //Non si puo' aprire una selezione senza chiedere nessuna competenza
    function apertura_senzaCompetenze_bloccata() public {
        (bool riuscita, string memory motivo) = _provaApertura(DURATA, new uint[](0));
        _deveBloccare(riuscita, motivo, ERR_SENZA_COMPETENZE);
    }

    //Non si puo' aprire una selezione che dura zero giorni
    function apertura_durataZero_bloccata() public {
        (bool riuscita, string memory motivo) = _provaApertura(0, _skillRichieste());
        _deveBloccare(riuscita, motivo, ERR_DURATA);
    }

    // -------------------------------CANDIDATURE--------------------------------

    //TUTTE LE POSSIBILI CANDIDATURE:

    //COMPETENZE COMPLETE: idoneo
    function candidato_conTutteLeCompetenze_idoneo() public {
        devCompleto.candidati(hiring, address(nft));
        Assert.ok(hiring.hasApplied(address(devCompleto)), MSG_NON_REGISTRATA);
        Assert.ok(hiring.isEligible(address(devCompleto)), MSG_IDONEO);
    }

    //COMPETENZE PARZIALI: non idoneo
    function candidato_conAlcuneCompetenze_nonIdoneo() public {
        devParziale.candidati(hiring, address(nft));
        Assert.ok(hiring.hasApplied(address(devParziale)), MSG_NON_REGISTRATA);
        Assert.ok(!hiring.isEligible(address(devParziale)), MSG_NON_IDONEO);
    }

    //COMPETENZE NULLE: non idoneo
    function candidato_senzaCompetenze_nonIdoneo() public {
        devSenzaSkill.candidati(hiring, address(nft));
        Assert.ok(!hiring.isEligible(address(devSenzaSkill)), MSG_NON_IDONEO);
    }

    //COMPETENZE IN PIU': idoneo
    function candidato_conCompetenzeInPiu_idoneo() public {
        Attore devEsperto = new Attore();
        nft.addSkill(address(devEsperto), SKILL_PYTHON, MESI, PUNTEGGIO);
        nft.addSkill(address(devEsperto), SKILL_JAVA, MESI, PUNTEGGIO);
        nft.addSkill(address(devEsperto), SKILL_SOLIDITY, MESI, PUNTEGGIO);

        devEsperto.candidati(hiring, address(nft));
        Assert.ok(hiring.isEligible(address(devEsperto)), MSG_IDONEO);
    }

    //DATA DI SCADENZA SUPERATA: non candidabile
    function candidatura_dopoLaScadenza_bloccata() public {
        _chiudiCandidature();
        (bool riuscita, string memory motivo) = _provaCandidatura(devCompleto);
        _deveBloccare(riuscita, motivo, ERR_CHIUSE);
    }

    //DATA DI SCADENZA NON RAGGIUNTA: candidabile
    function candidatura_unSecondoPrimaDellaScadenza_accettata() public {
        hiring.impostaTempo(hiring.startDate() + DURATA * 1 days - 1);
        devCompleto.candidati(hiring, address(nft));
        Assert.ok(hiring.isEligible(address(devCompleto)), MSG_IDONEO);
    }

    //CANDIDATURA RIPETUTA: bloccata 
    function candidatura_ripetuta_bloccata() public {
        devCompleto.candidati(hiring, address(nft));
        (bool riuscita, string memory motivo) = _provaCandidatura(devCompleto);
        _deveBloccare(riuscita, motivo, ERR_GIA_CANDIDATO);
    }
}