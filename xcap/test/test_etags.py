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

    def test_conditional_GET(self):
        r = self.put('resource-lists', resource_list_xml)
        etag = self.assertHeader(r, 'ETag')

        # Test If-Match (both valid and invalid)
        self.get('resource-lists', headers={'If-Match': etag})
        self.get('resource-lists', headers={'If-Match': '*'})
        self.get('resource-lists', headers={'if-Match': "another-etag"}, status=412)

        # Test If-None-Match (both valid and invalid)
        self.get('resource-lists', headers={'If-None-Match': etag}, status=304)
        self.get('resource-lists', headers={'If-None-Match': '*'}, status=304)
        self.get('resource-lists', headers={'If-None-Match': "another-etag"}, status=200)

    def test_conditional_PUT(self):
        r = self.put('resource-lists', resource_list_xml)
        etag = self.assertHeader(r, 'ETag')

        # Test conditional PUT logic
        ## Alice and Bob initially share the same etag
        alice_etag = bob_etag = etag

        ## Bob modifies the resource
        r = self.put('resource-lists', resource_list_xml, headers={'If-Match': bob_etag})
        bob_etag = self.assertHeader(r, 'ETag')

        ## now Alice tries to modify the resource
        self.put('resource-lists', resource_list_xml, headers={'If-Match': alice_etag}, status=412)

        ## the etag has changed so now she updates her in-memory document
        r = self.get('resource-lists')
        new_alice_etag = self.assertHeader(r, 'ETag')
        self.assertEqual(bob_etag, new_alice_etag)

        self.put('resource-lists', resource_list_xml, headers={'If-Match': new_alice_etag})

    def test_conditional_PUT_2(self):
        self.delete('resource-lists', status=[200,404])
        self.get('resource-lists', status=404)

        self.put('resource-lists', resource_list_xml, headers={'If-None-Match': '*'}, status=201)
        self.put('resource-lists', resource_list_xml, headers={'If-None-Match': '*'}, status=412)


class ETagTest2(XCAPTest):
    # the same as prev, but using 'etag' param

    def test_conditional_GET(self):
        r = self.put('resource-lists', resource_list_xml)
        etag = self.assertHeader(r, 'ETag')

        # Test If-Match (both valid and invalid)
        self.get('resource-lists', etag=etag)
        self.get('resource-lists')
        self.get('resource-lists', etag="another-etag", status=412)

    def test_conditional_PUT(self):
        r = self.put('resource-lists', resource_list_xml)
        etag = self.assertETag(r)
        assert etag is not None, `etag`

        # Test conditional PUT logic
        ## Alice and Bob initially share the same etag
        alice_etag = bob_etag = etag

        ## Bob modifies the resource
        r = self.put('resource-lists', resource_list_xml, etag=bob_etag)
        bob_etag = self.assertETag(r)

        ## now Alice tries to modify the resource
        self.put('resource-lists', resource_list_xml, etag=alice_etag, status=412)

        ## the etag has changed so now she updates her in-memory document
        r = self.get('resource-lists')
        new_alice_etag = self.assertETag(r)
        self.assertEqual(bob_etag, new_alice_etag)

        self.put('resource-lists', resource_list_xml, etag=new_alice_etag)

    def test_etag_parsing(self):
        r = self.put('resource-lists', resource_list_xml)
        etag = self.assertETag(r)
        # no quotes
        r = self.put('resource-lists', resource_list_xml, headers = {'if-match' : 'xxx' }, status=412)
        r = self.put('resource-lists', resource_list_xml, headers = {'if-match' : etag }, status=200)
        etag = self.assertETag(r)
        r = self.put('resource-lists', resource_list_xml, headers = {'if-match' : '"' + etag + '"' }, status=200)
        etag = self.assertETag(r)
        self.put('resource-lists', resource_list_xml, headers = {'if-match' : '"' + etag + 'xx"' }, status=412)

if __name__ == '__main__':
    runSuiteFromModule()
