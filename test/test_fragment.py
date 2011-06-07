#!/usr/bin/env python

# Copyright (C) 2007-2010 AG-Projects.
#

import common

document = """<?xml version="1.0" encoding="UTF-8"?>
<resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists">
<list xmlns:gm="http://www.yyyyy.org">
<entry uri="sip:xxx@yyyyy.net">
<gm:group>Foo</gm:group>
</entry>
</list>
</resource-lists>"""

# well-formed fragment that would've been rejected by XML parser because of
# unbound namespace prefix
fragment = """<entry uri="sip:xxx@yyyyy.net">
   <gm:group>Test</gm:group>
</entry>"""

node = '/resource-lists/list/entry[@uri="sip:xxx@yyyyy.net"]'

class FragmentTest(common.XCAPTest):

    def test_success(self):
        self.put('resource-lists', document)
        self.put('resource-lists', fragment, node)

    def test_errors(self):
        self.put('resource-lists', document)

        r = self.put('resource-lists', "<tag></bag>", node, status=409)
        self.assertInBody(r, 'mismatched tag')

        r = self.put('resource-lists', "<ta g></ta g>", node, status=409)
        self.assertInBody(r, 'not well-formed (invalid token)')

        r = self.put('resource-lists', "<ta g></ta g>", node, status=409)
        self.assertInBody(r, 'not well-formed (invalid token)')

        r = self.put('resource-lists', "<tag1/><tag2/>", node, status=409)
        self.assertInBody(r, 'junk after document element')

        r = self.put('resource-lists', "<tag\\></tag\\>", node, status=409)
        self.assertInBody(r, 'not well-formed (invalid token)')

if __name__ == '__main__':
    common.runSuiteFromModule()
