Feature: US-4 Exporting records to CSV

As a data owner
I want to convert a JSON file of records into CSV
so that I can open it in a spreadsheet

Blockchain: 10
Command: python3 esercizi.py

Scenario: AT-4.1 two records
  Given the file "people.json" contains the text
    """
    [{"name": "Mario", "city": "Cagliari"},
     {"name": "Lucia", "city": "Roma"}]
    """
  When I run "export-csv people.json out.csv"
  Then it succeeds
  And the output contains "Exported 2 records"
  And the file "out.csv" exists
  And the file "out.csv" contains "name,city"
  And the file "out.csv" contains "Mario,Cagliari"

Scenario: AT-4.2 empty list
  Given the file "none.json" contains "[]"
  When I run "export-csv none.json out.csv"
  Then it fails
  And the output contains "Nothing to export"
  And the file "out.csv" does not exist

Scenario: AT-4.3 malformed input
  Given the file "broken.json" contains "{not json"
  When I run "export-csv broken.json out.csv"
  Then it fails
  And the output contains "Invalid JSON"

@manual
Scenario: AT-4.4 the file opens correctly in a spreadsheet
  Then the Product Owner opens the CSV in a spreadsheet and checks that
  the columns are separated and the accents are readable
