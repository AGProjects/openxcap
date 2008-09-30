from common import *
from lxml import etree

has_global = ['xcap-caps']
no_global = set(apps) - set(has_global)

class TestGlobal(XCAPTest):

    def test_no_global(self):
        for app in no_global:
            self.get_global(app, status=404)

    def test_has_global(self):
        for app in has_global:
            self.get_global(app, status=200)

if __name__ == '__main__':
    runSuiteFromModule()
