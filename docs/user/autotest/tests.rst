Tests
========

Within a Category you can create the actual tests. There are several different
tests, which offers enough flexibility to easily set up completely new tests or
execute any already existing testing tools.

Our philosophy is that even automatic assessment using AutoTest should be
feedback oriented: AutoTests should always give as much feedback to the student
as possible. This is already enforced by linking the AutoTest and Rubric
Categories. Another way to maximize feedback to students is by naming
your tests and inputs in a meaningful way, as this is the first feedback
students will receive from the tests.

.. note::

    Use weights per test (or per input of IO test) to differentiate between
    the importance of tests.

IO Test
---------

The IO Test is the most common test to create. This is a test in which you
specify an input to a program and an expected output. If the students' program
returns the same output as expected, the test passes and they achieve points.

A (student) program can be specified to be run in the IO tests, then, you can
specify all input and output combinations you want to check for this program.

Multiple options allow you to more flexibly compare the output of the program:

  - **Case insensitive**: ignore case in comparing the expected output and actual output.
  - **Ignore trailing whitespace**: trim all trailing whitespacing from the start and end.
  - **Ignore all whitespace**: all whitespace is ignored when comparing the student output with the expected output (including newlines).
  - **Substring**: the expected output should be a substring of the actual output.
  - **Regex**: the expected output is a *Python3 Regex* which should match with the actual output.

.. note::
    The options *Ignore all whitespace* and *regex* cannot be activated
    together.

.. note::
    The option *substring* is required when using the *regex* option.


Use the :fa:`plus` button in the bottom left corner to create a new input/output
combination.

Use-cases
~~~~~~~~~~
As the name suggests, IO Tests are used to check the output of a program given
an input. IO Tests are very useful to check the functionality of simple and
advanced programs. From checking for ``Hello, World!`` to checking if a sudoku
solver is correctly implemented or even complex mathematical programs.
Additionally, IO Tests can be used to check the correct handling of incorrect
input.

.. note::

    If you require files as input to your tests, upload these files as fixtures
    to find them in ``$FIXTURES/[FILE]``, where you can then use them as input
    arguments to your test.


Run Program Test
-----------------
The Run Program Test simply executes a specified program and checks the return
code or exit status of this program. Meaning, an exit status of 0 (or
**success**) results in passing the test and any nonzero exit status (or
**failure**) results in failing the test.

Use-cases
~~~~~~~~~~~~
Run Program Tests are easy to set up and effective to check program execution
when specific output is not important. Use Run Program Tests, for instance, to
check the successful compilation of student code or to run single unit tests
that you provide as fixtures.


Capture Points Test
---------------------
The Capture Points Test is an extension of the Run Program Test. It also
executes a specified program but instead of taking the exit status, captures
the output of this program. The output of the program can be captured using a
*Python3 Regex*. This output should be a valid *Python Float* number between **0.0
and 1.0**. This number is then multiplied with the weight of the Capture Point
Test to get to the final score of the test.

Use-cases
~~~~~~~~~~~
Capture Points Tests are especially useful to run programs of which the output
is of importance. Use Capture Points Tests to execute and evaluate your own
unit test scripts or any other specific programs you want to use to evaluate
student code.

It is easy to use existing unit test frameworks with the Capture Points Test,
simply write a small wrapper script around it to parse the output to a value
between 0 and 1.

.. note::

    If you have trouble writing these wrapper scripts or using the Capture
    Points Test with your own frameworks, contact us and we're happy to help
    you!

Checkpoint
---------------
A Checkpoint can be used to add conditions to your Test Categories. A Checkpoint
can be put in between tests, to only execute the following tests
if enough points have been scored in the tests preceding to the Checkpoint.

Use-cases
~~~~~~~~~~
It can be necessary to add conditionality between tests in your Test Category.
This can be done with a Checkpoint, which is for instance useful if you check
compilation in a first test and you only want to run following tests if this
test succeeded.
