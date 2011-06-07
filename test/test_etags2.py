#!/usr/bin/env python

# Copyright (C) 2007-2010 AG-Projects.
#

from common import *

resource_list_xml = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists">
     <list name="friends">
     </list>
   </resource-lists>"""

class ETagTest(XCAPTest):

    def test_conditional_PUT(self):
        self.delete('resource-lists', status=[200,404])
        self.get('resource-lists', status=404)

        # Test conditional PUT when document doesn't exist
        self.put('resource-lists', resource_list_xml, headers={'If-Match': '12345asdf'}, status=412)

#        r = self.put('resource-lists', resource_list_xml)
#        etag = self.assertHeader(r, 'ETag')
#
#        # Test conditional PUT logic
#        ## Alice and Bob initially share the same etag
#        alice_etag = bob_etag = etag
#
#        ## Bob modifies the resource
#        r = self.put('resource-lists', resource_list_xml, headers={'If-Match': bob_etag})
#        bob_etag = self.assertHeader(r, 'ETag')
#
#        ## now Alice tries to modify the resource
#        self.put('resource-lists', resource_list_xml, headers={'If-Match': alice_etag}, status=412)
#
#        ## the etag has changed so now she updates her in-memory document
#        r = self.get('resource-lists')
#        new_alice_etag = self.assertHeader(r, 'ETag')
#        self.assertEqual(bob_etag, new_alice_etag)
#
#        self.put('resource-lists', resource_list_xml, headers={'If-Match': new_alice_etag})
#
    def test_conditional_PUT_2(self):
        self.delete('resource-lists', status=[200,404])
        self.get('resource-lists', status=404)

        self.put('resource-lists', resource_list_xml, headers={'If-None-Match': '*'}, status=201)
        self.put('resource-lists', resource_list_xml, headers={'If-None-Match': '*'}, status=412)


if __name__ == '__main__':
    runSuiteFromModule()
