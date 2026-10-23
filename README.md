# Test di accettazione in Remix IDE – NFT Competenze e SC Assunzioni

## Struttura

```
contracts/
  NFTSkill.sol                  contratto NFT Competenze (corretto)
  Hiring_Smart_Contract.sol     contratto SC Assunzioni (corretto)
tests/
  Helpers.sol                   supporto ai test (non contiene test)
  NFTSkill_test.sol             US1 - registrazione competenze
  Candidatura_test.sol          US2 - apertura, US3 - candidatura
  Selezione_test.sol            US4 - lista idonei, US5 - assunzione
```

Il file NFT deve chiamarsi `NFTSkill.sol` perché il contratto delle assunzioni lo importa con `import "./NFTSkill.sol";`.

## Come eseguire i test in Remix

1. Nel File Explorer di Remix, crea le cartelle `contracts` e `tests` e carica i file mantenendo la struttura qui sopra.
2. In **Solidity Compiler** scegli una versione 0.8.x (ad esempio 0.8.24). In *Advanced Configurations* attiva **Enable optimization**: i contratti di test contengono al loro interno i contratti da testare e senza ottimizzazione potrebbero superare la dimensione massima consentita.
3. Apri **Plugin Manager** (icona della presa in basso a sinistra), cerca **Solidity Unit Testing** e clicca *Activate*.
4. Apri il plugin (icona con la spunta doppia), imposta come cartella dei test `tests`.
5. Seleziona i tre file `*_test.sol` e clicca **Run**.

Il risultato atteso sono 26 test verdi (6 + 10 + 10).

## Differenze rispetto a Foundry

Remix non permette di cambiare il mittente delle chiamate né di spostare l'orologio della blockchain dentro un test. Per questo:

- **Mittente:** ogni chiamata parte dal contratto di test, che quindi fa da *Product Owner* e da *ente certificatore*. Sviluppatori ed estranei sono simulati con piccoli contratti `Attore`: quando un attore chiama il contratto, `msg.sender` è l'indirizzo dell'attore.
- **Tempo:** il contratto delle assunzioni legge l'orario tramite la funzione `_now()`, che normalmente restituisce `block.timestamp`. Nei test si usa `SkillSelectionTestabile`, che ridefinisce `_now()` e permette di impostare l'istante con `impostaTempo()`. Il contratto reale non cambia comportamento.
- **Eventi:** Remix non permette di leggere gli eventi nei test. L'esito si verifica sullo stato: `hasApplied`, `isEligible`, `isHired`.
- **Rifiuti:** i casi "non ok" usano `try / catch` e controllano che il messaggio di errore sia quello atteso.

## Criteri di accettazione

| US | Criterio | Tipo |
|----|----------|------|
| US1 | AC1.1 Le competenze registrate vengono restituite | ok |
| | AC1.2 Sviluppatore senza competenze → lista vuota | ok |
| | AC1.3 Le competenze restano separate per sviluppatore | ok |
| | AC1.4 Lo sviluppatore si autocertifica una competenza | non ok |
| | AC1.5 Un ente abilitato registra una competenza | ok |
| | AC1.6 Un estraneo abilita un ente certificatore | non ok |
| US2 | AC2.1 Product Owner, skill, data e durata salvati | ok |
| | AC2.2 Apertura senza competenze richieste | non ok |
| | AC2.3 Apertura con durata zero | non ok |
| US3 | AC3.1 Candidato con tutte le skill → idoneo | ok |
| | AC3.2 Candidato con skill parziali → non idoneo | non ok |
| | AC3.3 Candidato senza skill → non idoneo | non ok |
| | AC3.4 Skill in più e in ordine diverso → idoneo | ok |
| | AC3.5 Candidatura alla scadenza | non ok |
| | AC3.6 Candidatura 1 secondo prima della scadenza | ok |
| | AC3.7 Seconda candidatura dello stesso sviluppatore | non ok |
| US4 | AC4.1 Dopo la chiusura il PO vede solo gli idonei | ok |
| | AC4.2 Il PO chiede la lista prima della chiusura | non ok |
| | AC4.3 Un estraneo chiede la lista | non ok |
| | AC4.4 Nessuna candidatura → lista vuota | ok |
| US5 | AC5.1 Il PO assume un candidato idoneo | ok |
| | AC5.2 Un estraneo prova ad assumere | non ok |
| | AC5.3 Il PO assume un candidato non idoneo | non ok |
| | AC5.4 Il PO assume chi non si è mai candidato | non ok |
| | AC5.5 Il PO assume a candidature aperte | non ok |
| | AC5.6 Il PO assume due volte lo stesso candidato | non ok |

Un test "non ok" è verde quando il contratto **rifiuta** l'operazione con il messaggio atteso.

## Correzioni ai contratti di Alice

Ogni correzione è segnata nel codice con `// CORREZIONE n`.

| n. | Problema nel codice originale | Correzione |
|----|------------------------------|------------|
| 1 | `addSkill()` chiamabile da chiunque: autocertificazione delle competenze | Solo enti certificati (`onlyCertifier`, `addCertifier`) |
| 2 | Esito di `application()` invertito | `if (result == false)` → `if (result)` |
| 3 | Tutti i candidati finivano nella lista degli idonei | `push` spostato dentro l'`if`, aggiunto `isEligible` |
| 4 | `getSkill()` richiamata a ogni giro del ciclo | Lettura unica prima del ciclo |
| 5 | Candidature multiple dello stesso sviluppatore | `hasApplied` con `require` |
| 6 | Costruttore senza controlli su lista e durata | Due `require` |
| 7 | `owner` non leggibile, `onlyOwner` senza messaggio | `owner` pubblico, messaggio di errore |
| 8 | Durata in minuti invece che in giorni | `1 minutes` → `1 days` |
| 9 | Refuso `exportDevLkst` | Rinominata `exportDevList` |
| 10 | `hiring()` senza controlli su idoneità e chiusura | `require(isEligible)` e `earlyTime` |
| 11 | Assunzione non registrata e ripetibile | `isHired` con `require` |

La lettura delle competenze soggetta ad autorizzazione dello sviluppatore, descritta nella tesi, non è implementata: è da concordare con la relatrice.

## Prova manuale in Remix (Deploy & Run)

1. Pubblica `Skill`; l'account che pubblica è l'ente certificatore.
2. Con `addSkill` registra le competenze su alcuni account di Remix.
3. Pubblica `SkillSelection` con durata e lista, ad esempio `1, [1,2]`.
4. Cambia account in alto e chiama `application` passando l'indirizzo di `Skill`; nei log compare l'esito.

Con la durata in giorni non si può arrivare a mano alla chiusura. Per una prova manuale completa si può mettere temporaneamente `1 minutes` al posto di `1 days` nei due modificatori, ricordandosi di rimetterlo prima di consegnare.

## Esecuzione fuori da Remix (Jenkins)

Gli stessi test si possono lanciare da riga di comando con `remix-tests`, lo strumento ufficiale del progetto Remix:

```bash
npm install -g @remix-project/remix-tests
remix-tests tests/
```

Verificare le opzioni disponibili con `remix-tests --help` (versione del compilatore, ottimizzazione). Il comando si può inserire in uno stage `sh` della pipeline Jenkins.
