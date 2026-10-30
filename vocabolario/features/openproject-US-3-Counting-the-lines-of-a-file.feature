Feature: US-3 Counting the lines of a file

As a command line user
I want to know how many lines a file has
so that I can check its size

Blockchain: 0
Command: python3 esercizi.py

Scenario: AT-3.1 file with three lines
  Given the file "data.txt" contains "a\nb\nc"
  When I run "count-lines data.txt"
  Then it succeeds
  And the output contains "3"

Scenario: AT-3.2 empty file
  Given the file "empty.txt" is empty
  When I run "count-lines empty.txt"
  Then it succeeds
  And the output contains "0"

Scenario: AT-3.3 one line without newline
  Given the file "one.txt" contains "hello"
  When I run "count-lines one.txt"
  Then the output contains "1"

Scenario: AT-3.4 missing file
  Given the file "gone.txt" does not exist
  When I run "count-lines gone.txt"
  Then it fails
  And the output contains "File not found"

  #SEED:5356f02a6a5aef2cdb78aee4f187fe4e
