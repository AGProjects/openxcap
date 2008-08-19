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

list_element_xml = """<list xmlns="urn:ietf:params:xml:ns:resource-lists" name="friends">
      <entry uri="sip:joe@example.com">
        <display-name>Joe Smith</display-name>
      </entry>
      <entry uri="sip:nancy@example.com">
        <display-name>Nancy Gross</display-name>
      </entry>
      <entry uri="sip:petri@example.com">
        <display-name>Petri Aukia</display-name>
      </entry>
     </list>"""

second_element_xml = """<entry xmlns="urn:ietf:params:xml:ns:resource-lists" uri="sip:nancy@example.com">
        <display-name>Nancy Gross</display-name>
      </entry>"""

broken_element_xml = """<entry xmlns="urn:ietf:params:xml:ns:resource-lists" uri="sip:nancy@example.com">
        <display-name>Nancy Gross</display-name>
      """

class ElementTest(XCAPTest):
    
    def test_get(self):
        self.delete('resource-lists', status=[200,404])
        self.put('resource-lists', resource_list_xml)
        self.get('resource-lists', '/resource-lists/list[@name="other"]', status=404)
        self.get('resource-lists', '/resource-lists/list/entry[4]', status=404)
        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]')
        self.assertBody(r, list_element_xml)
        self.assertHeader(r, 'ETag')
        self.assertHeader(r, 'Content-type', 'application/xcap-el+xml')
        
        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/entry[2]')
        self.assertBody(r, second_element_xml)
        self.assertHeader(r, 'ETag')
        self.assertHeader(r, 'Content-type', 'application/xcap-el+xml')
        
        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/*[2]')
        self.assertStatus(r, 200)
        self.assertBody(r, second_element_xml)
        self.assertHeader(r, 'ETag')
        self.assertHeader(r, 'Content-type', 'application/xcap-el+xml')

    def test_delete(self):
        self.put('resource-lists', resource_list_xml)
        
        r = self.delete('resource-lists', '/resource-lists/list[@name="friends"]/*[3]')
        self.assertHeader(r, 'ETag')

        r = self.delete('resource-lists', '/resource-lists/list[@name="friends"]/*[2]')
        self.assertHeader(r, 'ETag')

        r = self.delete('resource-lists', '/resource-lists/list[@name="friends"]/*[1]')
        self.assertHeader(r, 'ETag')

        self.delete('resource-lists',
                    '/resource-lists/list[@name="friends"]/entry[@uri="sip:joe@example.com"]', status=404)

    def test_put_error(self):
        self.put('resource-lists', resource_list_xml)

        # 415 content type not set
        self.put('resource-lists', second_element_xml, '/resource-lists/list[@name="friends"]', status=415)

        headers = {'Content-type': "application/xcap-el+xml"}
        # 409 <not-xml-frag>
        r = self.put('resource-lists', broken_element_xml, '/resource-lists/list[@name="friends"]',
                     headers, status=409)

        # 409 <not-parent>
        r = self.put('resource-lists', second_element_xml, '/resource-lists/list[@name="others"]/entry[2]',
                     headers, status=409)

        # 409 <uniqueness-failure>
        r = self.put('resource-lists', second_element_xml, '/resource-lists/list[@name="friends"]/entry[1]',
                     headers, status=409)

if __name__ == '__main__':
    runSuiteFromModule()
