# Vocabolario

## Standard Gherkin

| Parola | Cosa fa |
|---|---|
| `Feature:` | apre il file, dice di cosa si tratta |
| `Rule:` | raggruppa scenari dentro una Feature |
| `Background:` | passi comuni, eseguiti prima di ogni scenario |
| `Scenario:` | un criterio di accettazione |
| `Scenario Outline:` | un criterio con più casi |
| `Examples:` | la tabella dei casi di uno Scenario Outline |
| `Given` | situazione di partenza |
| `When` | azione |
| `Then` | verifica |
| `And` | continua la riga precedente, dello stesso tipo |
| `But` | come `And`, in negativo |
| `@etichetta` | marca uno scenario |
| `#` | commento |
| `"""` | blocco di testo su più righe |
| `\| a \| b \|` | tabella di valori |


## Given — preparare

| Frase | Cosa fa |
|---|---|
| `Given the file {string} contains {string}` | crea il file con quel contenuto |
| `Given the file {string} contains the text` | come sopra, col contenuto nel blocco `"""` sotto |
| `Given the file {string} is empty` | crea il file vuoto |
| `Given the file {string} does not exist` | lo rimuove se c'è |
| `Given the service is running` | avvia il servizio e aspetta che risponda |

## When — agire

| Frase | Cosa fa |
|---|---|
| `When I call {string} with {json}` | chiama la funzione, il secondo valore è l'elenco degli argomenti |
| `When I run {string}` | esegue il comando |
| `When I send {word} {string}` | manda una richiesta: metodo e percorso |
| `When I send {word} {string} with {json}` | manda una richiesta con un corpo |

## Then — verificare

| Frase | Cosa controlla |
|---|---|
| `Then I get {json}` | il valore restituito, corrispondenza esatta |
| `Then the result is between {float} and {float}` | valori approssimati |
| `Then the result has {int} items` | la forma, non il contenuto |
| `Then the result contains {string}` | corrispondenza parziale |
| `Then the result does not contain {string}` | il testo non c'è |
| `Then the output contains {string}` | un testo nell'output |
| `Then the output does not contain {string}` | il testo non è nell'output |
| `Then the output matches {string}` | un'espressione regolare |
| `Then it succeeds` | codice di uscita 0 |
| `Then it fails` | codice di uscita diverso da 0 |
| `Then the error {string} is raised` | l'eccezione attesa |
| `Then I receive status {int}` | codice di stato HTTP |
| `Then the body contains {string}` | contenuto della risposta |
| `Then the body does not contain {string}` | il testo non è nella risposta |
| `Then the file {string} exists` | il file è stato creato |
| `Then the file {string} does not exist` | non c'è, o è stato rimosso |
| `Then the file {string} contains {string}` | il contenuto del file |
| `Then the file {string} does not contain {string}` | il testo non è nel file |
| `Then it finishes within {int} milliseconds` | tempo massimo di esecuzione |

### I criteri in negativo

Le quattro frasi `does not contain` servono a scrivere i criteri che dicono
cosa **non** deve succedere. Il caso tipico è una password: non basta che
l'accesso funzioni, bisogna anche che la password non resti scritta in chiaro
da nessuna parte.

```gherkin
  Scenario: AT-6.9 la password non viene conservata in chiaro
    When I call "signup" with ["mario@test.it", "segretissima"]
    Then the file "utenti.json" does not contain "segretissima"
```

`the file ... does not contain` **pretende che il file esista.** Se il file non
c'è il criterio fallisce, e non passa: un criterio che chiede l'assenza di
qualcosa da un file che nessuno ha mai scritto passerebbe senza aver
controllato niente, e proprio quello sulla password non deve passare per
inerzia. Se una consegna può legittimamente non scrivere il file, lo si dice
con `the file ... does not exist`.

### La barra rovesciata

Su **OpenProject** cinque caratteri — underscore, asterisco, backtick e le
due parentesi quadre — tornano con una barra rovesciata davanti, perché là
hanno un significato nel markdown: la verifica la toglie, quindi si scrivono
normalmente.

Su **Taiga** e **Jira** il testo torna com'è stato scritto, quindi una barra
rovesciata resta dov'è. Serve a chi scrive un'espressione regolare: su quei
due sistemi `Then the output matches "\[ok\]"` cerca davvero le parentesi
quadre.

### `\n` dentro le virgolette

Un criterio non può contenere un vero ritorno a capo dentro una stringa fra
virgolette, quindi `\n` ne vale uno. Vale allo stesso modo in tutte le frasi
che scrivono o confrontano del testo: `Given the file "a.txt" contains
"riga1\nriga2"` scrive due righe, e `Then the file "a.txt" contains
"riga1\nriga2"` le ritrova. L'unica eccezione è `the output matches`, dove il
testo è un'espressione regolare e `\n` lo interpreta già il motore delle
espressioni.

## Etichette 

| Etichetta | Cosa fa |
|---|---|
| `@manual` | **Per A.T NON AUTOMATIZZABILE:** il sistema lo salta e lo segnala al Product Owner |

Il criterio `@manual` non viene eseguito ma deve comunque essere
valido. Un @manual scritto su due
righe rende illeggibile l'intero file, è obbligatorio quindi scriverlo sempre senza `\n`.

### Cosa fa il Product Owner con un `@manual`

Quando i criteri automatici passano, la verifica firma sulla catena e si
ferma. Il Product Owner legge i `@manual` nel report e ha due strade, entrambe
sulla catena:

- **firmare** con `approveDelivery`, che riempie la sua casella e lascia
  passare il pagamento;
- **rifiutare** con `rejectDelivery`, scrivendo nella transazione il motivo,
  che resta nel registro degli eventi e il developer legge.

Il rifiuto non ha scadenza: un `@manual` che non si poteva misurare, e un
lavoro scritto per rispondere ai criteri e a nient'altro, li vede solo una
persona, e li vede quando li guarda. Il rifiuto riporta la user story a prima
della consegna — le tre caselle tornano vuote, il commit si cancella — e il
developer **ritrova il tempo che gli restava nel momento in cui ha
consegnato**: l'attesa della risposta non la paga lui. Poi riconsegna con
`submitWork`, e la verifica riparte dall'inizio sul nuovo commit.

Se invece il Product Owner non fa niente, dopo quattordici giorni la casella
scade e il pagamento passa per silenzio: il rifiuto è una cosa che si fa, non
una che succede.

## Intestazione della user story

| Campo | Cosa indica |
|---|---|
| `Module:` | file che espone le funzioni, serve per `I call` |
| `Command:` | programma da eseguire, serve per `I run` |
| `Service:` | indirizzo del servizio, serve per `I send` |
| `Start:` | programma che avvia il servizio, serve per `Given the service is running` |
| `Repository:` | repository del codice, se diverso da quello del progetto |

### Le user story con un servizio

Servono due campi, e fanno due cose diverse: `Start:` dice **come si accende**
il servizio, `Service:` dice **dove risponde**.

```gherkin
  Service: http://127.0.0.1:8000
  Start: python3 servizio.py

  Scenario: AT-7.1 la registrazione risponde
    Given the service is running
    When I send POST "/signup" with {"email": "mario@test.it", "password": "segretissima"}
    Then I receive status 201
    And the body does not contain "segretissima"
```

`Given the service is running` avvia il programma di `Start:`, aspetta fino a
quindici secondi che `Service:` risponda, e va avanti. Se il servizio muore
subito, il criterio riporta il suo codice di uscita e quello che ha scritto,
così si capisce perché non è partito.

Il programma di `Start:` può anche limitarsi ad avviare il servizio vero e
uscire: finché qualcuno risponde entro i quindici secondi, il criterio va
avanti.

**Il servizio viene spento alla fine di ogni criterio**, insieme a tutto quello
che ha avviato a sua volta. Ogni criterio che usa il servizio deve quindi
scrivere il proprio `Given the service is running`: non si eredita da quello
prima. È voluto, perché un servizio rimasto in piedi risponderebbe al criterio
successivo, che passerebbe contro un processo che nessuno ha avviato per lui.

Per lo stesso motivo **l'indirizzo deve essere libero quando il criterio
comincia**. Se qualcuno risponde già prima che il criterio avvii qualcosa, il
criterio fallisce dicendolo: quella porta è di un processo che non appartiene
a questa verifica, e misurarci contro non direbbe niente sulla consegna. Il
caso tipico è un servizio che si è staccato dal proprio gruppo di processi ed
è sopravvissuto allo spegnimento.

Il servizio risponde sul solo indirizzo locale: dentro il contenitore la rete
verso l'esterno non esiste, e `127.0.0.1` continua a funzionare.

Il collegamento fra la task e la user story sullo smart contract non si scrive
qui: lo stabilisce il Product Owner sulla catena con `setExternalRef`, e la
verifica lo legge da lì. Nell'intestazione non va quindi nessun identificativo
della user story: il contratto dice chi lavora a cosa, la task dice cosa c'è
da fare.

`Repository:` accetta solo indirizzi nella forma `https://host/percorso` o
`git@host:percorso`. Le altre forme vengono rifiutate, perché per alcune git
esegue comandi sulla macchina che fa la verifica.

## Segnaposto

| Segnaposto | Significato |
|---|---|
| `{string}` | stringa, testo fra virgolette |
| `{int}` | numero intero |
| `{float}` | numero con la virgola |
| `{word}` | parola singola, senza virgolette |
| `{json}` | valore in notazione JSON |

## Valori


| Tipo | Esempio |
|---|---|
| numero | `5` `3.5` `-2` |
| testo | `"hello"` |
| booleano | `true` `false` |
| elenco | `[3, 1, 2]` |
| oggetto | `{"email": "mario@test.it"}` |
| niente | `null` |


---

## Esempio di utilizzo

```gherkin
Rule: US-4 Exporting records to CSV

  As a data owner
  I want to convert a JSON file of records into CSV
  so that I can open it in a spreadsheet

  Command: python3 esercizi.py

  Scenario: AT-4.1 two records
    Given the file "people.json" contains the text
      """
      [{"name": "Mario", "city": "Cagliari"}]
      """
    When I run "export-csv people.json out.csv"
    Then it succeeds
    And the file "out.csv" contains "name,city"

  Scenario: AT-4.2 empty list
    Given the file "none.json" contains "[]"
    When I run "export-csv none.json out.csv"
    Then it fails
    And the file "out.csv" does not exist

  @manual
  Scenario: AT-4.3 the file opens correctly in a spreadsheet
    Then the Product Owner opens the CSV in a spreadsheet and checks that the columns are separated and the accents are readable
```

### Output:

Criteri Automatici passano:

```
US-4 Exporting records to CSV
Repository: https://github.com/simomnz/consegna-esercizi @ 20df34d

Automated criteria: 2 of 2 passed
  AT-4.1 two records                          OK
  AT-4.2 empty list                           OK

To be checked by hand: 1
  AT-4.3 the file opens correctly in a spreadsheet

Status: waiting for the Product Owner.
```

Se invece un criterio automatico fallisce:

```
US-4 Exporting records to CSV
Repository: https://github.com/simomnz/consegna-esercizi @ 13fd97b

Automated criteria: 1 of 2 passed
  AT-4.1 two records                          OK
  AT-4.2 empty list                           FAILED
      step:  Then the file "out.csv" does not exist
      the file exists, 0 bytes: out.csv

Status: rejected, the delivery does not meet the criteria.
```

I criteri da verificare a mano non vengono elencati in caso di errore per non far perdere
tempo al Product Owner su un lavoro che non ha ancora passato i controlli automatici.
