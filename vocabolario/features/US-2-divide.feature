Feature: US-2 Safe division

  As a library user
  I want to divide two numbers
  so that I get a result or a clear error

  Blockchain: 8
  Module: esercizi.py

  Scenario Outline: AT-2.1 valid divisions
    When I call "divide" with [<a>, <b>]
    Then I get <result>

    Examples:
      | a   | b  | result |
      | 10  | 2  | 5      |
      | 7   | 2  | 3.5    |
      | 0   | 5  | 0      |
      | -10 | 2  | -5     |
      | 10  | -2 | -5     |

  Scenario: AT-2.2 division by zero
    When I call "divide" with [10, 0]
    Then the error "division by zero" is raised

  Scenario: AT-2.3 periodic result
    When I call "divide" with [1, 3]
    Then the result is between 0.333 and 0.334
