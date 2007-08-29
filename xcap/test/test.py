# Copyright (C) 2007 AG Projects.
#

import unittest
import common

class TestHarness(object):
    """A test harness for OpenXCAP."""

    def __init__(self, tests=[]):
        """Constructor to populate the TestHarness instance.

        tests should be a list of module names (strings).
        """
        self.tests = tests
    
    def run(self):
        module_names = self.tests
        test_suites = []
        for testmod in module_names:
            m = __import__(testmod, globals(), locals())
            test_suites.append(m.suite())
        self.run_test_suite(unittest.TestSuite(test_suites))

    def run_test_suite(self, suite):
        unittest.TextTestRunner(verbosity=2).run(suite)


def run():

    testList = [
        'test_document',
        'test_element',
        'test_attribute',
        'test_etags',
        'test_auth',
        'test_pidf',
        'test_presrules'
    ]
    
    t = TestHarness(testList)
    t.run()

if __name__ == '__main__':
    run()
