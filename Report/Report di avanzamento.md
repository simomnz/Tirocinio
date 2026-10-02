# Report di avanzamento

**Tirocinio — smart contract per la gestione dei team effimeri**

## 1. Da dove sono partito

Il progetto viene dalla tesi di un'altra studentessa, che usa la blockchain per formare team effimeri. Ci sono tre contratti:

- **Skill (NFT Competenze)**: tiene le competenze di ogni sviluppatore;
- **SkillSelection (SC Assunzioni)**: apre la selezione, raccoglie le candidature, dice chi è idoneo e permette di assumere;
- **UserStories (SC User Story)**: gestisce le user story assegnate agli sviluppatori e il pagamento.

Oltre ai contratti, sono presenti anche FitNesse e Jenkins per far girare i test sulle user story.

Io ho lavorato su due cose: la pipeline con Jenkins e OpenProject, e i test di accettazione sui primi due contratti.

---

## 2. La pipeline Jenkins

Ho scritto una pipeline (`Pipeline.groovy`) che a ogni esecuzione fa quattro cose:

1. **Checkout**: scarica il codice dal ramo `main` del repository GitHub.
2. **Preparazione**: cancella `node_modules` e `package-lock.json` e reinstalla le dipendenze con `npm install --legacy-peer-deps`. Così ogni build parte pulita e ripulisce le dipendenze delle run precedenti.
3. **Audit & Test**: `npx hardhat clean`, `npx hardhat compile` e `npx hardhat test`, quindi compila i tre contratti e lancia i test che stanno nel repository.
4. **Feedback OpenProject**: manda un commento sul work package per dire che è andato tutto bene.

Per il quarto stage uso l'API REST di OpenProject: scrivo il commento in un file JSON e lo mando con `curl` in POST su `/api/v3/work_packages/1094/activities`. Mi autentico con utente `apikey` e il mio token.

Il token non è scritto nella pipeline: l'ho messo nelle credenziali di Jenkins (`OP_CREDENTIALS`) e lo richiamo con `credentials()`, così Jenkins lo nasconde anche nei log. Su `curl` ho messo `-f` perché se OpenProject risponde con un errore lo stage deve fallire.

Non è gestita ancora su che macchina e sistema operativo girano Jenkins e OpenProject e con che versioni.
Manca una notifica lato OpenProject in caso di errore,
La pipeline al momento è statica lo stage dei test esegue `npx hardhat test`, la cartella `test/` la ho eliminata (dalla repository github), quindi attualmente non viene più eseguito alcun test e la build risulta sempre positiva. I test di accettazione che ho scritto stanno in `tests/` e sono fatti per Remix. Comunque è un fix facilissimo da risolvere

---

## 3. Le correzioni ai contratti

Scrivendo i test ho confrontato il codice con i requisiti della tesi e ho trovato diversi problemi. Li ho corretti e nel codice ogni modifica ha un commento con `//CORREZIONE`.

### Errori trovati e risolti

**L'esito della candidatura era invertito:** In `application()` la condizione era `if (result == false)`, quindi veniva dichiarato idoneo chi *non* aveva le competenze richieste. Ora la condizione è `if (result)`.

**Nella lista degli idonei finivano tutti:** Il `push` nella lista era fuori dall'`if`, quindi ogni candidato veniva aggiunto. L'ho spostato dentro e ho aggiunto `isEligible` per tenere traccia di chi è idoneo.

**Si poteva assumere chiunque;** `hiring()` controllava solo che a chiamarla fosse il Product Owner: si poteva assumere un non idoneo, uno che non si era mai candidato, e anche a candidature ancora aperte. Ho aggiunto un controllo sull'idoneità e il modificatore `earlyTime`.

**Chiunque poteva aggiungere competenze:** `addSkill()` non aveva controlli, quindi uno sviluppatore poteva aggiungersi le competenze e passare la selezione. Nella tesi le competenze *dovrebbero*  essere rilasciate dagki enti certificati. Ho aggiunto la lista `certifiers`, il modificatore `onlyCertifier` e l a funzione `addCertifier()` per abilitarne di nuovi.

**Ci si poteva candidare più volte:** Lo stesso indirizzo compariva più volte nella lista. Ho aggiunto `hasApplied` per risolvere il problema.

**L'assunzione non veniva registrata:** Ho aggiunto `isHired` per salvare l'assunzione.

`getSkill()` veniva chiamata a ogni giro del ciclo, quindi una chiamata esterna ogni volta: ora le competenze si leggono una volta sola (gas risparmaito).
Il costruttore accettava lista di competenze vuota (tutti idonei) e durata zero (selezione già chiusa): ho aggiunto due `require`.
`owner` non era leggibile dall'esterno e `onlyOwner` non dava nessun messaggio d'errore: sistemati entrambi.
La durata era in minuti (`1 minutes`) mentre la tesi e il commento nel codice parlano di giorni: ora è `1 days` (penso voluto per motivi di testing però dimenticato).Per risolvere questo problema di testing adessoil contratto non legge più `block.timestamp` ma usa la funzione `_now()`. Nei test uso una copia del contratto che ridefinisce `_now()` e mi permette di spostare l'ora: Il contratto vero rimane invariato.

---

## 4. I test di accettazione

Sono partito dai requisiti della tesi e per ognuno ho scritto cosa deve succedere perché si possa dire soddisfatto. Per ogni requisito ho messo sia i casi che devono funzionare sia quelli che devono essere bloccati; nei casi bloccati viene mandato in output anche il messaggio d'errore specifico.

I requisiti che coperto sono cinque:

- R1 — le competenze le inseriscono solo indirizzi certificati;
- R2 — il Product Owner apre la selezione con competenze richieste e durata;
- R3 — lo sviluppatore si candida e il sistema decide se è idoneo;
- R4 — a candidature chiuse il Product Owner vede la lista degli idonei;
- R5 — si assumono candidati presi da quella lista.

### I test

Sono 26 test in 3 files:

| File | Cosa contiene | Test |
| --- | --- | --- |
| `BaseTest.sol` | Nessun test: contiene: le costanti, i messaggi d'errore e i controlli | — |
| `NFTSkill_test.sol` | R1 | 6 |
| `Candidatura_test.sol` | R2 e R3 | 10 |
| `Selezione_test.sol` | R4 e R5 | 10 |

---

## La pipeline

```groovy
pipeline {
    agent any

    environment {
        OP_CREDENTIALS = credentials('OP_CREDENTIALS')
    }

    stages {
        stage('1. Checkout') {
            steps {
                git branch: 'main', url: 'https://github.com/simomnz/Tirocinio.git'
            }
        }

        stage('2. Preparazione') {
            steps {
                sh 'rm -rf node_modules package-lock.json'
                sh 'npm install --legacy-peer-deps'
            }
        }

        stage('3. Audit & Test') {
            steps {
                sh 'npx hardhat clean'
                sh 'npx hardhat compile'
                sh 'npx hardhat test'
            }
        }

        stage('4. Feedback OpenProject') {
            steps {
                script {
                    def comment = '{"comment": {"format": "markdown", "raw": "Jenkins CI: build e test superati."}}'
                    writeFile file: 'comment.json', text: comment
                    sh "curl -f -X POST -u apikey:${OP_CREDENTIALS_PSW} -H 'Content-Type: application/json' -d @comment.json http://127.0.0.1:8090/api/v3/work_packages/1094/activities"
                }
            }
        }
    }

    post {
        failure {
            echo 'Build o test falliti.'
        }
    }
}
