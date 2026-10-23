Feature: US-5 Generating a code

  As a system administrator
  I want to generate a random six digit code
  so that I can hand it out as a reference

  Blockchain: 11
  Command: python3 esercizi.py

  Scenario: AT-5.1 the code has the right shape
    When I run "make-code"
    Then it succeeds
    And the output matches "[0-9]{6}"

  Scenario: AT-5.2 unknown command
    When I run "do-something"
    Then it fails
    And the output contains "Unknown command"
