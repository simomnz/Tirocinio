// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.8.18 <0.9.0;

import "remix_tests.sol";
import "./BaseTest.sol";

//Registrazione delle competenze


//Test su chi puo' inserire le competenze e su come si rileggono
contract NFTSkillTest is BaseTest {

    
    function beforeEach() public {
        _prepara();
    }

    //Prova aggiunta competenza
    function _provaAggiuntaCompetenza(Attore chiamante, address sviluppatore, uint competenza)
        internal
        returns (bool, string memory)
    {
        try chiamante.aggiungiSkill(nft, sviluppatore, competenza, MESI, PUNTEGGIO) {
            return (true, "");
        } catch Error(string memory motivo) {
            return (false, motivo);
        } catch {
            return (false, "");
        }
    }

    //Prova abilitazione di un nuovo ente
    function _provaAbilitazioneEnte(Attore chiamante, address ente) internal returns (bool, string memory) {
        try chiamante.abilitaEnte(nft, ente) {
            return (true, "");
        } catch Error(string memory motivo) {
            return (false, motivo);
        } catch {
            return (false, "");
        }
    }

    // -------------------------------LETTURA--------------------------------

    //COMPETENZE REGISTRATE: si rileggono
    function competenze_registrate_siRileggono() public {
        uint[] memory competenze = nft.getSkill(address(devCompleto));

        Assert.equal(competenze.length, 2, "Numero di competenze sbagliato");
        Assert.equal(competenze[0], SKILL_SOLIDITY, "Prima competenza sbagliata");
        Assert.equal(competenze[1], SKILL_JAVA, "Seconda competenza sbagliata");
    }

    //NESSUNA COMPETENZA: lista vuota
    function competenze_sviluppatoreSenzaNessuna_listaVuota() public {
        uint[] memory competenze = nft.getSkill(address(devSenzaSkill));
        Assert.equal(competenze.length, 0, "La lista doveva essere vuota");
    }

    //PIU' SVILUPPATORI: competenze separate
    function competenze_restanoSeparate() public {
        uint[] memory competenze = nft.getSkill(address(devParziale));
        Assert.equal(competenze.length, 1, "Numero di competenze sbagliato");
        Assert.equal(competenze[0], SKILL_SOLIDITY, "Competenza sbagliata");
    }

    // -------------------------------INSERIMENTO--------------------------------

    //CHI PUO' INSERIRE LE COMPETENZE:

    //SVILUPPATORE SU SE STESSO: bloccato
    function competenze_aggiunteDaSeStesso_bloccate() public {
        (bool riuscita, string memory motivo) =
            _provaAggiuntaCompetenza(devSenzaSkill, address(devSenzaSkill), SKILL_JAVA);
        _deveBloccare(riuscita, motivo, ERR_SOLO_CERTIFICATI);
    }

    //ENTE ABILITATO: competenza registrata
    function competenze_aggiunteDaEnteAbilitato_registrate() public {
        Attore universita = new Attore();
        nft.addCertifier(address(universita));

        universita.aggiungiSkill(nft, address(devSenzaSkill), SKILL_PYTHON, MESI, PUNTEGGIO);

        uint[] memory competenze = nft.getSkill(address(devSenzaSkill));
        Assert.equal(competenze.length, 1, "Competenza non registrata");
        Assert.equal(competenze[0], SKILL_PYTHON, "Competenza sbagliata");
    }

    //ESTRANEO CHE ABILITA UN ENTE: bloccato
    function enti_abilitatiDaEstraneo_bloccati() public {
        (bool riuscita, string memory motivo) = _provaAbilitazioneEnte(estraneo, address(estraneo));
        _deveBloccare(riuscita, motivo, ERR_SOLO_PROPRIETARIO);
    }
}