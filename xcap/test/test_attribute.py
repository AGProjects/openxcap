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

list_element_xml = """<list name="friends">
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

second_element_xml = """<entry uri="sip:nancy@example.com">
        <display-name>Nancy Gross</display-name>
      </entry>"""

broken_element_xml = """<entry uri="sip:nancy@example.com">
        <display-name>Nancy Gross</display-name>
      """

class AttributeTest(XCAPTest):
    
    def test_get(self):
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus([200, 201])
        
        self.get_resource('resource-lists', '/resource-lists/list[@name="other"]/@some-attribute')
        self.assertStatus(404)
                
        self.get_resource('resource-lists', '/resource-lists/list[@name="friends"]/@name')
        self.assertStatus(200)
        self.assertBody("friends")
        self.assertHeader('ETag')
        self.assertHeader('Content-type', 'application/xcap-att+xml')

    def test_delete(self):
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus([200, 201])
        
        self.delete_resource('resource-lists', '/resource-lists/list[@name="other"]/@some-attribute')
        self.assertStatus(404)

        self.delete_resource('resource-lists', '/resource-lists/list[@name="friends"]/@name')
        self.assertStatus(200)

        self.delete_resource('resource-lists', '/resource-lists/list[@name="friends"]/@name')
        self.assertStatus(404)

    def test_put(self):
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus([200, 201])

        headers = {'Content-type': "application/xcap-att+xml"}
        self.put_resource('resource-lists', 'coworkers', '/resource-lists/list[@name="other"]/@some-attribute', headers)
        self.assertStatus(409)

        headers = {'Content-type': "application/xcap-att+xml"}
        self.put_resource('resource-lists', 'coworkers', '/resource-lists/list[@name="friends"]/@name', headers)
        self.assertStatus(200)

if __name__ == '__main__':
    runSuiteFromModule()
