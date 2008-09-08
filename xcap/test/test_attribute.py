from common import *

resource_list_xml = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists">
     <list name="friends">
      <entry uri="sip:joe@example.com">
        <display-name>Joe Smith</display-name>
      </entry>
      <entry uri="sip:nancy@example.com">
        <display-name>Nancy Gross</display-name>
      </entry>
      <entry uri="sip:petri@example.com">
        <display-name>Petri Aukia</display-name>
      </entry>
     </list>
   </resource-lists>"""

class AttributeTest(XCAPTest):
    
    def test_get(self):
        self.put('resource-lists', resource_list_xml)
        
        self.get('resource-lists', '/resource-lists/list[@name="other"]/@some-attribute', status=404)
                
        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/@name')
        self.assertBody(r, "friends")
        self.assertHeader(r, 'ETag')
        self.assertHeader(r, 'Content-type', 'application/xcap-att+xml')

    def test_delete(self):
        self.put('resource-lists', resource_list_xml)
        self.delete('resource-lists', '/resource-lists/list[@name="other"]/@some-attribute', status=404)

        # XXX is it legal for parent selector (/resource-lists/list[@name="friends"]) to become invalid?
        # I don't think it is, check with RFC
        self.delete('resource-lists', '/resource-lists/list[@name="friends"]/@name', status=200)
        self.delete('resource-lists', '/resource-lists/list[@name="friends"]/@name', status=404)

    def test_put(self):
        self.put('resource-lists', resource_list_xml)

        self.put('resource-lists', 'coworkers',
                 '/resource-lists/list[@name="friends"]/@some-attribute', status=409)

        # fails GET(PUT(x))==x test. must be rejected in the server
        #self.put('resource-lists', 'coworkers', '/resource-lists/list[@name="friends"]/@name', status=409)

        # XXX parent's selector becomes invalid
        r = self.client.put('resource-lists', 'coworkers', '/resource-lists/list[@name="friends"]/@name')
        self.assertStatus(r, 200)

if __name__ == '__main__':
    runSuiteFromModule()
