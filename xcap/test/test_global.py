
# Copyright (C) 2007-2010 AG-Projects.
#

from common import *

has_global = ['xcap-caps']
no_global = set(apps) - set(has_global)

class TestGlobal(XCAPTest):

    def test_no_global(self):
        for app in no_global:
            self.get(app, status=404, globaltree=True)

            # at the moment, no one authorized to do that
            # NOTE, even though 404 would be also a valid response here, 401 should take priority
            # 404 or 401?
#             self.put(app, xml, status=401, globaltree=True)
#             self.delete(app, status=401, globaltree=True)

    def test_has_global(self):
        for app in has_global:
            self.get(app, status=200, globaltree=True)

#             # at the moment, no one authorized to do that
#             #self.put(app, xml, status=401, globaltree=True)
#             self.delete(app, status=401, globaltree=True)

if __name__ == '__main__':
    runSuiteFromModule()
