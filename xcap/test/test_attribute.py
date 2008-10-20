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
      <external anchor="http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list%5b@name=%22mkting%22%5d"/>
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

        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/external/@anchor')
        uri = 'http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list%5b@name=%22mkting%22%5d'
        self.assertBody(r, uri)

        print 'WARNING: test with URI in att_value is disabled'
#         r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/external[@anchor="%s"]/@anchor' % uri)
#         self.assertBody(r, uri)

        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/external[]/@anchor', status=400)

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
        r = self.client._put('resource-lists', 'coworkers', '/resource-lists/list[@name="friends"]/@name')
        self.assertStatus(r, 200)

if __name__ == '__main__':
    runSuiteFromModule()
