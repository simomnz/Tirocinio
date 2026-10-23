Feature: US-1 Sorting a list

As a library user
I want to sort a list of numbers
so that I can display them in order

Blockchain: 7
Module: esercizi.py

Scenario: AT-1.1 unsorted list
  When I call "sort" with [[3, 1, 2]]
  Then I get [1, 2, 3]

Scenario: AT-1.2 already sorted
  When I call "sort" with [[1, 2, 3]]
  Then I get [1, 2, 3]

Scenario: AT-1.3 empty list
  When I call "sort" with [[]]
  Then I get []
