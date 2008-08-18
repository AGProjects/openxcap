from common import *

resource_list_xml = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists">
     <list name="friends">
     </list>
   </resource-lists>"""

class ETagTest(XCAPTest):

    def test_conditional_GET(self):
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus([200, 201])
        etag = self.assertHeader('ETag')
        
        # Test If-Match (both valid and invalid)
        self.get_resource('resource-lists', headers={'If-Match': etag})
        self.assertStatus(200)
        self.get_resource('resource-lists', headers={'If-Match': '*'})
        self.assertStatus(200)
        self.get_resource('resource-lists', headers={'if-Match': "another-etag"})
        self.assertStatus(412)
        
        # Test If-None-Match (both valid and invalid)
        self.get_resource('resource-lists', headers={'If-None-Match': etag})
        self.assertStatus(304)
        self.get_resource('resource-lists', headers={'If-None-Match': '*'})
        self.assertStatus(304)
        self.get_resource('resource-lists', headers={'If-None-Match': "another-etag"})
        self.assertStatus(200)
        
    def test_conditional_PUT(self):
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus([200, 201])
        etag = self.assertHeader('ETag')        
        
        # Test conditional PUT logic
        ## Alice and Bob initially share the same etag
        alice_etag = bob_etag = etag
        ## Bob modifies the resource
        self.put_resource('resource-lists', resource_list_xml, headers={'If-Match': bob_etag})
        self.assertStatus([200, 201])
        bob_etag = self.assertHeader('ETag')
        
        ## now Alice tries to modify the resource
        self.put_resource('resource-lists', resource_list_xml, headers={'If-Match': alice_etag})
        self.assertStatus(412)
        
        ## the etag has changed so now she updates her in-memory document
        self.get_resource('resource-lists')
        self.assertStatus(200)
        alice_etag = self.assertHeader('ETag')
        
        self.put_resource('resource-lists', resource_list_xml, headers={'If-Match': alice_etag})
        self.assertStatus([200, 201])

if __name__ == '__main__':
    runSuiteFromModule()
