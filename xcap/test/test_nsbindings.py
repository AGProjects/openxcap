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

class NSBindingsTest(XCAPTest):

    def test_ns_bindings(self):
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus([200, 201])

        self.get_resource('resource-lists', '/resource-lists/list[@name="friends"]/namespace::*')
        self.assertStatus(200)
        self.assertHeader('ETag')
        self.assertHeader('Content-type', 'application/xcap-ns+xml')

if __name__ == '__main__':
    runSuiteFromModule()
