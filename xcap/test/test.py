#!/usr/bin/env python
import sys
import os
import traceback

import common as c

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
                self.import_errors += 1
                m = __import__(testmod, globals(), locals())
                suite = c.loadSuiteFromModule(m, option_parser)
                suite.modname = testmod
                self.test_suites.append(suite)
                self.import_errors -= 1
            except AssertionError, ex:
                if str(ex)!='disabled':
                    traceback.print_exc()
            except Exception:
                traceback.print_exc()

    def run(self, options, args):
        c.run_suite(c.TestSuite(self.test_suites), options, args)


def all_tests():
    my_dir = os.path.dirname(os.path.abspath(__file__))
    lst = [x.strip('.py') for x in os.listdir(my_dir) if x.startswith('test_') and x.endswith('.py')]
    return lst

def run():
    parser = c.prepare_optparser()
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

    c.process_options(options)
    c.run_command(lambda : t.run(options, args), options)
    if t.import_errors:
        sys.exit('there were import errors!\n')

if __name__ == '__main__':
    run()
