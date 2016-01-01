""" allows tests to be executed by "python test" from main project directory"""
import os
import sys
import unittest

sys.path.append(os.path.abspath("."))

from test_patterns import *
from test_reply import *

if __name__ == "__main__":
    unittest.main()
