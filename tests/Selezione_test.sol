// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.8.18 <0.9.0;

import "remix_tests.sol";
import "./BaseTest.sol";

//Lista degli idonei e assunzioni


//Test su chi puo' vedere la lista e su chi puo' essere assunto
contract SelezioneTest is BaseTest {

    
    function beforeEach() public {
        _prepara();
    }

    //Prova lettura della lista da parte di chi ha aperto la selezione
    function _provaLettura() internal returns (bool, string memory) {
        try hiring.exportDevList() returns (address[] memory) {
            return (true, "");
        } catch Error(string memory motivo) {
            return (false, motivo);
        } catch {
            return (false, "");
        }
    }

    //Prova lettura della lista da parte di un altro utente
    function _provaLetturaDa(Attore chiamante) internal returns (bool, string memory) {
        try chiamante.leggiLista(hiring) returns (address[] memory) {
            return (true, "");
        } catch Error(string memory motivo) {
            return (false, motivo);
        } catch {
            return (false, "");
        }
    }

    //Prova assunzione da parte di chi ha aperto la selezione
    function _provaAssunzione(address candidato) internal returns (bool, string memory) {
        try hiring.hiring(candidato) {
            return (true, "");
        } catch Error(string memory motivo) {
            return (false, motivo);
        } catch {
            return (false, "");
        }
    }

    //Prova assunzione da parte di un altro utente
    function _provaAssunzioneDa(Attore chiamante, address candidato) internal returns (bool, string memory) {
        try chiamante.assumi(hiring, candidato) {
            return (true, "");
        } catch Error(string memory motivo) {
            return (false, motivo);
        } catch {
            return (false, "");
        }
    }

    //CHI PUO' VEDERE LA LISTA E QUANDO:

    //CANDIDATURE CHIUSE: solo gli idonei in lista
    function lista_dopoLaChiusura_soloIdonei() public {
        devCompleto.candidati(hiring, address(nft));
        devParziale.candidati(hiring, address(nft));
        devSenzaSkill.candidati(hiring, address(nft));
        _chiudiCandidature();

        address[] memory lista = hiring.exportDevList();
        Assert.equal(lista.length, 1, "Numero di idonei sbagliato");
        Assert.equal(lista[0], address(devCompleto), "Idoneo sbagliato");
    }

    //CANDIDATURE ANCORA APERTE: lettura bloccata
    function lista_primaDellaChiusura_bloccata() public {
        devCompleto.candidati(hiring, address(nft));
        (bool riuscita, string memory motivo) = _provaLettura();
        _deveBloccare(riuscita, motivo, ERR_NON_CHIUSE);
    }

    //LETTURA DA UN ESTRANEO: bloccata
    function lista_lettaDaEstraneo_bloccata() public {
        devCompleto.candidati(hiring, address(nft));
        _chiudiCandidature();

        (bool riuscita, string memory motivo) = _provaLetturaDa(estraneo);
        _deveBloccare(riuscita, motivo, ERR_SOLO_PO);
    }

    //NESSUNA CANDIDATURA: lista vuota
    function lista_senzaCandidature_vuota() public {
        _chiudiCandidature();
        address[] memory lista = hiring.exportDevList();
        Assert.equal(lista.length, 0, "La lista doveva essere vuota");
    }

    // -------------------------------ASSUNZIONI--------------------------------

    //TUTTE LE POSSIBILI ASSUNZIONI:

    //CANDIDATO IDONEO: assunzione registrata
    function assunzione_diUnIdoneo_registrata() public {
        devCompleto.candidati(hiring, address(nft));
        _chiudiCandidature();

        hiring.hiring(address(devCompleto));
        Assert.ok(hiring.isHired(address(devCompleto)), "Assunzione non registrata");
    }

    //ASSUNZIONE FATTA DA UN ESTRANEO: bloccata
    function assunzione_fattaDaEstraneo_bloccata() public {
        devCompleto.candidati(hiring, address(nft));
        _chiudiCandidature();

        (bool riuscita, string memory motivo) = _provaAssunzioneDa(estraneo, address(devCompleto));
        _deveBloccare(riuscita, motivo, ERR_SOLO_PO);
    }

    //CANDIDATO NON IDONEO: bloccata
    function assunzione_diUnNonIdoneo_bloccata() public {
        devParziale.candidati(hiring, address(nft));
        _chiudiCandidature();

        (bool riuscita, string memory motivo) = _provaAssunzione(address(devParziale));
        _deveBloccare(riuscita, motivo, ERR_NON_IDONEO);
    }

    //CANDIDATO MAI CANDIDATOSI: bloccata
    function assunzione_diChiNonSiECandidato_bloccata() public {
        _chiudiCandidature();

        (bool riuscita, string memory motivo) = _provaAssunzione(address(estraneo));
        _deveBloccare(riuscita, motivo, ERR_NON_IDONEO);
    }

    //CANDIDATURE ANCORA APERTE: bloccata
    function assunzione_aCandidatureAperte_bloccata() public {
        devCompleto.candidati(hiring, address(nft));

        (bool riuscita, string memory motivo) = _provaAssunzione(address(devCompleto));
        _deveBloccare(riuscita, motivo, ERR_NON_CHIUSE);
    }

    //ASSUNZIONE RIPETUTA: bloccata
    function assunzione_ripetuta_bloccata() public {
        devCompleto.candidati(hiring, address(nft));
        _chiudiCandidature();
        hiring.hiring(address(devCompleto));

        (bool riuscita, string memory motivo) = _provaAssunzione(address(devCompleto));
        _deveBloccare(riuscita, motivo, ERR_GIA_ASSUNTO);
    }
}