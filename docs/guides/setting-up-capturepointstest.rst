Setting up Capture Points Tests
================================

With a Capture Points test you can easily run and integrate your own unit
test scripts. A Capture Points Test captures the output of the executed program
with a Python3 Regular Expression. This output should be a **number between
0 and 1**.

1. Input which program you want to execute.

2. Specify the **Python3 Regex** with which you want to capture the output. By
   default this captures a single float. This number is multiplied by the **weight**
   to get the amount of points.

   .. note::

       A **Python3 Regex** may contain ``\f``, which will capture a float.

.. note::
  You can easily use existing unit test scripts and frameworks with the Capture
  Points Test, simply write a simple wrapper script around the unit test script
  that parses the output and outputs a number between 0.0 and 1.0 (e.g. the
  amount of passed tests divided by the total amount of tests).
