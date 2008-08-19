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
        self.put('resource-lists', resource_list_xml)
        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/namespace::*')
        self.assertHeader(r, 'ETag')
        self.assertHeader(r, 'Content-type', 'application/xcap-ns+xml')

if __name__ == '__main__':
    runSuiteFromModule()
