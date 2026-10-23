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
| `Given the service is running` | aspetta che il servizio risponda |

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
| `Then the output contains {string}` | un testo nell'output |
| `Then the output matches {string}` | un'espressione regolare |
| `Then it succeeds` | codice di uscita 0 |
| `Then it fails` | codice di uscita diverso da 0 |
| `Then the error {string} is raised` | l'eccezione attesa |
| `Then I receive status {int}` | codice di stato HTTP |
| `Then the body contains {string}` | contenuto della risposta |
| `Then the file {string} exists` | il file è stato creato |
| `Then the file {string} does not exist` | non c'è, o è stato rimosso |
| `Then the file {string} contains {string}` | il contenuto del file |
| `Then it finishes within {int} milliseconds` | tempo massimo di esecuzione |

## Etichette 

| Etichetta | Cosa fa |
|---|---|
| `@manual` | **Per A.T NON AUTOMATIZZABILE:** il sistema lo salta e lo segnala al Product Owner |

Il criterio `@manual` non viene eseguito ma deve comunque essere
valido. Un @manual scritto su due
righe rende illeggibile l'intero file, è obbligatorio quindi scriverlo sempre senza `\n`.

## Intestazione della user story

| Campo | Cosa indica |
|---|---|
| `Blockchain:` | identificativo della user story sullo smart contract |
| `Module:` | file che espone le funzioni, serve per `I call` |
| `Command:` | programma da eseguire, serve per `I run` |
| `Service:` | indirizzo del servizio, serve per `I send` |
| `Repository:` | repository del codice, se diverso da quello del progetto |

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

  Blockchain: 10
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
