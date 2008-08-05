# Copyright (C) 2007 AG Projects.
#

import sys
import os
import getopt
import unittest

class TestHarness(object):
    """A test harness for OpenXCAP."""

    def __init__(self, tests=[]):
        """Constructor to populate the TestHarness instance.

        tests should be a list of module names (strings).
        """
        self.tests = tests
        module_names = self.tests
        self.test_suites = []
        for testmod in module_names:
            m = __import__(testmod, globals(), locals())
            suite = m.suite()
            suite.modname = testmod
            self.test_suites.append(suite)
    
    def run(self):
        self.run_test_suite(unittest.TestSuite(self.test_suites))

    def run_test_suite(self, suite):
        unittest.TextTestRunner(verbosity=2).run(suite)

def all_tests(patterns = []):
    lst = [x.strip('.py') for x in os.listdir('.') if x.startswith('test_') and x.endswith('.py')]
    if patterns:
        return [x for x in lst if is_test_selected(x, patterns)]
    return lst

def is_test_selected(filename, patterns):
    for x in patterns:
        if x in filename:
            return True

def run():
    opts, args = getopt.getopt(sys.argv[1:], '', ['list'])

    t = TestHarness(all_tests(args))

    if '--list' in dict(opts):
        for x in t.test_suites:
            print x.modname
            for i in x:
                print ' - ', i
            print 
        return

    t.run()

if __name__ == '__main__':
    run()
