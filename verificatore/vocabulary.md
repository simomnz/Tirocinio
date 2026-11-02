# Vocabulary

## Standard Gherkin

| Word | What it does |
|---|---|
| `Feature:` | opens the file, says what it is about |
| `Rule:` | groups scenarios inside a Feature |
| `Background:` | shared steps, run before every scenario |
| `Scenario:` | one acceptance criterion |
| `Scenario Outline:` | one criterion with several cases |
| `Examples:` | the table of cases of a Scenario Outline |
| `Given` | the starting situation |
| `When` | the action |
| `Then` | the check |
| `And` | carries on the line above, of the same kind |
| `But` | like `And`, in the negative |
| `@label` | marks a scenario |
| `#` | a comment |
| `"""` | a block of text over several lines |
| `\| a \| b \|` | a table of values |


## Given — getting ready

| Phrase | What it does |
|---|---|
| `Given the file {string} contains {string}` | writes the file with that content |
| `Given the file {string} contains the text` | the same, with the content in the `"""` block below |
| `Given the file {string} is empty` | writes the file empty |
| `Given the file {string} does not exist` | removes it if it is there |
| `Given the service is running` | starts the service and waits for it to answer |

## When — acting

| Phrase | What it does |
|---|---|
| `When I call {string} with {json}` | calls the function, the second value is the list of its arguments |
| `When I run {string}` | runs the command |
| `When I send {word} {string}` | sends a request: the method and the path |
| `When I send {word} {string} with {json}` | sends a request with a body |

## Then — checking

| Phrase | What it checks |
|---|---|
| `Then I get {json}` | the value that came back, matched exactly |
| `Then the result is between {float} and {float}` | values that are approximate |
| `Then the result has {int} items` | the shape, not the content |
| `Then the result contains {string}` | a partial match |
| `Then the result does not contain {string}` | the text is not there |
| `Then the output contains {string}` | some text in the output |
| `Then the output does not contain {string}` | the text is not in the output |
| `Then the output matches {string}` | a regular expression |
| `Then it succeeds` | exit code 0 |
| `Then it fails` | an exit code other than 0 |
| `Then the error {string} is raised` | the exception that was expected |
| `Then I receive status {int}` | the HTTP status code |
| `Then the body contains {string}` | the content of the answer |
| `Then the body does not contain {string}` | the text is not in the answer |
| `Then the file {string} exists` | the file was written |
| `Then the file {string} does not exist` | it is not there, or it was removed |
| `Then the file {string} contains {string}` | the content of the file |
| `Then the file {string} does not contain {string}` | the text is not in the file |
| `Then it finishes within {int} milliseconds` | the longest it may take |

### Criteria in the negative

The four `does not contain` phrases are there to write the criteria that say
what must **not** happen. The usual case is a password: it is not enough that
signing in works, the password must also not be left in clear anywhere.

```gherkin
  Scenario: AT-6.9 the password is not kept in clear
    When I call "signup" with ["mario@test.it", "segretissima"]
    Then the file "utenti.json" does not contain "segretissima"
```

`the file ... does not contain` **demands that the file exist.** When the file
is not there the criterion fails, and does not pass: a criterion asking for
something to be absent from a file nobody ever wrote would pass without having
checked anything, and the one about the password is exactly the one that must
not pass by inertia. When a delivery may legitimately not write the file, that
is said with `the file ... does not exist`.

### The backslash

On **OpenProject** five characters — the underscore, the asterisk, the
backtick and the two square brackets — come back with a backslash in front of
them, because there they mean something in markdown: the verification takes it
off, so they are written as they are.

On **Taiga** and **Jira** the text comes back as it was written, so a
backslash stays where it is. That matters to whoever writes a regular
expression: on those two systems `Then the output matches "\[ok\]"` really does
look for the square brackets.

### `\n` inside the quotes

A criterion cannot hold a real newline inside a quoted string, so `\n` stands
for one. It works the same way in every phrase that writes or compares text:
`Given the file "a.txt" contains "line1\nline2"` writes two lines, and
`Then the file "a.txt" contains "line1\nline2"` finds them again. The one
exception is `the output matches`, where the text is a regular expression and
`\n` is interpreted by the expression engine itself.

## Labels

| Label | What it does |
|---|---|
| `@manual` | **For an acceptance test that CANNOT BE AUTOMATED:** the system skips it and reports it to the Product Owner |

A `@manual` criterion is not run, but it still has to be valid. A `@manual`
written over two lines makes the whole file unreadable, so it must always be
written without `\n`.

### What the Product Owner does with a `@manual`

When the automated criteria pass, the verification signs on the chain and
stops. The Product Owner reads the `@manual` ones in the report and has two
roads, both of them on the chain:

- **signing** with `approveDelivery`, which fills his own box and lets the
  payment through;
- **refusing** with `rejectDelivery`, writing the reason into the transaction,
  where it stays in the log of the events and the developer reads it.

A refusal has no deadline: a `@manual` that could not be measured, and work
written to answer the criteria and nothing else, are seen by a person alone,
and seen when that person looks. A refusal takes the user story back to before
the delivery — the three boxes go empty again, the commit is cleared — and the
developer **gets back the time he had left at the moment he delivered**: the
wait for an answer is not paid for by him. Then he delivers again with
`submitWork`, and the verification starts over from the beginning on the new
commit.

When the Product Owner does nothing instead, after fourteen days his box
expires and the payment goes through by silence: a refusal is something that
is done, not something that happens.

## The header of the user story

| Field | What it names |
|---|---|
| `Module:` | the file that holds the functions, needed by `I call` |
| `Command:` | the program to run, needed by `I run` |
| `Service:` | the address of the service, needed by `I send` |
| `Start:` | the program that starts the service, needed by `Given the service is running` |
| `Repository:` | the repository of the code, when it is not the one of the project |

### User stories with a service

Two fields are needed, and they do two different things: `Start:` says **how
it is switched on**, `Service:` says **where it answers**.

```gherkin
  Service: http://127.0.0.1:8000
  Start: python3 service.py

  Scenario: AT-7.1 signing up answers
    Given the service is running
    When I send POST "/signup" with {"email": "mario@test.it", "password": "segretissima"}
    Then I receive status 201
    And the body does not contain "segretissima"
```

`Given the service is running` starts the program in `Start:`, waits up to
fifteen seconds for `Service:` to answer, and carries on. When the service
dies straight away, the criterion reports its exit code and whatever it wrote,
so that it is clear why it did not come up.

The program in `Start:` may also do nothing more than start the real service
and exit: as long as somebody answers within the fifteen seconds, the
criterion carries on.

**The service is switched off at the end of every criterion**, together with
everything it started in its turn. Every criterion that uses the service must
therefore write its own `Given the service is running`: it is not inherited
from the one before. That is on purpose, because a service left standing would
answer the next criterion, which would then pass against a process nobody
started for it.

For the same reason **the address has to be free when the criterion begins**.
When somebody answers already, before the criterion has started anything, the
criterion fails and says so: that port belongs to a process that is not part
of this verification, and measuring ourselves against it would say nothing
about the delivery. The usual case is a service that broke away from its own
process group and survived the switching off.

The service answers on the local address alone: inside the container there is
no network towards the outside, and `127.0.0.1` keeps working.

The link between the task and the user story on the smart contract is not
written here: the Product Owner sets it on the chain with `setExternalRef`,
and the verification reads it from there. No identifier of the user story goes
into the header, then: the contract says who is working on what, the task says
what there is to do.

`Repository:` accepts addresses in the form `https://host/path` or
`git@host:path` alone. The other forms are refused, because for some of them
git runs commands on the machine that does the verification.

## Placeholders

| Placeholder | What it means |
|---|---|
| `{string}` | a string, text between quotes |
| `{int}` | a whole number |
| `{float}` | a number with a decimal point |
| `{word}` | a single word, without quotes |
| `{json}` | a value in JSON notation |

## Values


| Kind | Example |
|---|---|
| number | `5` `3.5` `-2` |
| text | `"hello"` |
| boolean | `true` `false` |
| list | `[3, 1, 2]` |
| object | `{"email": "mario@test.it"}` |
| nothing | `null` |


---

## An example of use

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

### Output

When the automated criteria pass:

```
US-4 Exporting records to CSV
Repository: https://github.com/simomnz/consegna-esercizi @ 20df34d

Automated criteria: 2 of 2 passed
  AT-4.1 two records                          OK
  AT-4.2 empty list                           OK

To be checked by hand: 1
  AT-4.3 the file opens correctly in a spreadsheet

Status: the automated criteria passed, waiting for the Product Owner.
```

When an automated criterion fails instead:

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

The criteria to be checked by hand are not listed when something failed, so
that the Product Owner does not spend time on work that has not passed the
automated checks yet.
