#!/usr/bin/env python3
"""
Unified test runner for all sprint test files (`test_sprint*.py`).

This script discovers any Python test modules matching the pattern
`test_sprint*.py` in the current directory (recursively if needed),
executes them using the built‑in `unittest` framework, and exits with:

* 0 – if all discovered tests pass
* 1 – if any test fails or raises an error

Usage:
    python run_all_tests.py
"""

import os
import sys
import unittest

def _discover_tests(start_dir: str):
    """Discover all unittest.TestCase modules matching `test_sprint*.py`."""
    loader = unittest.TestLoader()
    # The pattern restricts discovery to files named test_sprint*.py
    suite = loader.discover(start_dir=start_dir, pattern='test_sprint*.py')
    return suite

def main():
    # Root directory for discovery – the directory containing this script
    root_dir = os.path.abspath(os.path.dirname(__file__))

    # Discover tests
    test_suite = _discover_tests(root_dir)

    # Run tests with verbose output (equivalent to `python -m unittest -v`)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Exit with 0 if everything succeeded, otherwise 1
    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == '__main__':
    main()