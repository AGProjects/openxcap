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
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus([200, 201])
        
        self.get_resource('resource-lists', '/resource-lists/list[@name="other"]')
        self.assertStatus(404)
        
        self.get_resource('resource-lists', '/resource-lists/list/entry[4]')
        self.assertStatus(404)
        
        self.get_resource('resource-lists', '/resource-lists/list[@name="friends"]')
        self.assertStatus(200)
        self.assertInBody(list_element_xml)
        #self.assertBody(list_element_xml)
        self.assertHeader('ETag')
        self.assertHeader('Content-type', 'application/xcap-el+xml')
        
        self.get_resource('resource-lists', '/resource-lists/list[@name="friends"]/entry[2]')
        self.assertStatus(200)
        self.assertInBody(second_element_xml)
        #self.assertBody(second_element_xml)
        self.assertHeader('ETag')
        self.assertHeader('Content-type', 'application/xcap-el+xml')
        
        self.get_resource('resource-lists', '/resource-lists/list[@name="friends"]/*[2]')
        self.assertStatus(200)
        self.assertInBody(second_element_xml)
        #self.assertBody(second_element_xml)
        self.assertHeader('ETag')
        self.assertHeader('Content-type', 'application/xcap-el+xml')

    def test_delete(self):
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus([200, 201])
        
        self.delete_resource('resource-lists', '/resource-lists/list[@name="friends"]/*[3]')
        self.assertStatus(200)
        self.assertHeader('ETag')

        self.delete_resource('resource-lists', '/resource-lists/list[@name="friends"]/*[2]')
        self.assertStatus(200)
        self.assertHeader('ETag')

        self.delete_resource('resource-lists', '/resource-lists/list[@name="friends"]/*[1]')
        self.assertStatus(200)
        self.assertHeader('ETag')

        self.delete_resource('resource-lists', '/resource-lists/list[@name="friends"]/entry[@uri="sip:joe@example.com"]')
        self.assertStatus(404)

    def test_put(self):
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus([200, 201])
        
        self.put_resource('resource-lists', second_element_xml, '/resource-lists/list[@name="friends"]')
        self.assertStatus(415)        ## content type not set

        headers = {'Content-type': "application/xcap-el+xml"}
        self.put_resource('resource-lists', broken_element_xml, '/resource-lists/list[@name="friends"]', headers)
        self.assertStatus(409)        ## <not-xml-frag>
        
        self.put_resource('resource-lists', second_element_xml, '/resource-lists/list[@name="others"]/entry[2]', headers)
        self.assertStatus(409)        ## <not-parent>
        
        self.put_resource('resource-lists', second_element_xml, '/resource-lists/list[@name="friends"]/entry[1]', headers)
        self.assertStatus(409)        ## <uniqueness-failure>

if __name__ == '__main__':
    runSuiteFromModule()
