#!/usr/bin/env python3

# Copyright (C) 2007-2025 AG-Projects.
#

from common import XCAPTest, runSuiteFromModule


watchers = """<?xml version='1.0' encoding='utf-8'?>
<watchers xmlns="http://openxcap.org/ns/watchers"/>"""

class Test(XCAPTest):

    def test_get(self):
        self.get('org.openxcap.watchers')
        self.get('org.openxcap.watchers', '/watchers')
        self.get('org.openxcap.watchers', globaltree=True, status=404)
        self.get('org.openxcap.watchers', '/watchers', globaltree=True, status=404)

#     def test_put_not_allowed(self):
#         self.put('watchers', watchers, status=405)
#         self.put('watchers', watchers, '/watchers', status=405)
#         self.put('watchers', watchers, globaltree=True, status=405)
#         self.put('watchers', watchers, '/watchers', globaltree=True, status=405)

#     def test_delete_not_allowed(self):
#         self.delete('watchers', status=405)
#         self.delete('watchers', '/watchers', status=405)
#         self.delete('watchers', globaltree=True, status=405)
#         self.delete('watchers', '/watchers', globaltree=True, status=405)

if __name__ == '__main__':
    runSuiteFromModule()
