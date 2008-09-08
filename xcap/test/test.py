#!/usr/bin/env python
import sys
import os
import traceback
from optparse import OptionParser

from common import *

class TestHarness(object):
    """A test harness for OpenXCAP."""

    def __init__(self, tests, option_parser):
        """Constructor to populate the TestHarness instance.

        tests should be a list of module names (strings).
        """
        self.tests = tests
        self.option_parser = option_parser
        self.test_suites = []
        self.import_errors = 0
        for testmod in self.tests:
            try:
                m = __import__(testmod, globals(), locals())
                suite = loadSuiteFromModule(m, option_parser)
                suite.modname = testmod
                self.test_suites.append(suite)
            except Exception:
                traceback.print_exc()
                self.import_errors = 1
    
    def run(self, options, args):
        run_suite(TestSuite(self.test_suites), options, args)
        if self.import_errors:
            sys.exit('there were import errors!')

def all_tests():
    lst = [x.strip('.py') for x in os.listdir('.') if x.startswith('test_') and x.endswith('.py')]
    return lst

def run():
    read_xcapclient_cfg()
    parser = OptionParser(conflict_handler='resolve')
    parser.add_option('-d', '--debug', action='store_true', default=False)
    parser.add_option("-l", "--list", action="store_true", help="Print list of all tests")
    
    t = TestHarness(all_tests(), parser)
    options, args = parser.parse_args()

    if options.list:
        for x in t.test_suites:
            print x.modname
            for i in x:
                print ' - ', i
            print 
        return

    check_options(options)
    
    t.run(options, args)

if __name__ == '__main__':
    run()
