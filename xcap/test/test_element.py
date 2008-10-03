from common import *

xml = """<?xml version="1.0" encoding="UTF-8"?>
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

def index(s, sub, skip=0, start=0):
    while skip >= 0:
        found = s.index(sub, start)
        skip -= 1
        start = found + 1
    return found

def eindex(s, sub, skip=0):
    return index(s, sub, skip)+len(sub)

lst = xml[xml.index('<list'):eindex(xml, '</list>')]
nancy = xml[xml.index('<entry uri="sip:nancy'):eindex(xml, '</entry>', 1)]
broken = """<entry uri="sip:alice@example.com">
        <display-name>Alice</display-name>
      """
external = xml[xml.index('<external'):eindex(xml, '/>')]

class ElementTest(XCAPTest):
    
    def test_get(self):
        self.delete('resource-lists', status=[200,404])
        self.put('resource-lists', xml)
        self.get('resource-lists', '/resource-lists/list[@name="other"]', status=404)
        self.get('resource-lists', '/resource-lists/list/entry[4]', status=404)
        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]')
        self.assertBody(r, lst)
        self.assertHeader(r, 'ETag')
        self.assertHeader(r, 'Content-type', 'application/xcap-el+xml')
        
        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/entry[2]')
        self.assertBody(r, nancy)
        self.assertHeader(r, 'ETag')
        self.assertHeader(r, 'Content-type', 'application/xcap-el+xml')
        
        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/*[2]')
        self.assertBody(r, nancy)
        self.assertHeader(r, 'ETag')
        self.assertHeader(r, 'Content-type', 'application/xcap-el+xml')

        print 'WARNING: test with URI in att_value is disabled'
#         r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/external[@anchor="http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list%5b@name=&quot;mkting&quot;5d"]')
#         self.assertBody(r, external)
#         self.assertHeader(r, 'ETag')
#         self.assertHeader(r, 'Content-type', 'application/xcap-el+xml')

    def test_delete(self):
        self.put('resource-lists', xml)

        # cannot delete something in the middle
        self.delete('resource-lists', '/resource-lists/list[@name="friends"]/entry[2]', status=409)
        self.delete('resource-lists', '/resource-lists/list[@name="friends"]/*[3]', status=409)

        # it's ok to delete the last one though
        r = self.delete('resource-lists', '/resource-lists/list[@name="friends"]/*[4]')
        self.assertHeader(r, 'ETag')

        r = self.delete('resource-lists', '/resource-lists/list[@name="friends"]/*[3]')
        self.assertHeader(r, 'ETag')

        r = self.delete('resource-lists', '/resource-lists/list[@name="friends"]/*[2]')
        self.assertHeader(r, 'ETag')

        r = self.delete('resource-lists', '/resource-lists/list[@name="friends"]/entry')
        self.assertHeader(r, 'ETag')

        r = self.get('resource-lists', '/resource-lists/list')
        self.assertMatchesBody(r, '^<list name="friends">\\s*</list>$')

        self.delete('resource-lists',
                    '/resource-lists/list[@name="friends"]/entry[@uri="sip:joe@example.com"]', status=404)

    def test_put_error(self):
        self.put('resource-lists', xml)

        # 415 content type not set
        self.put('resource-lists', nancy, '/resource-lists/list[@name="friends"]',
                 headers={'Content-Type' : None},status=415)

        # 409 <not-xml-frag>
        r = self.put('resource-lists', broken, '/resource-lists/list[@name="friends"]', status=409)

        # 409 <not-parent>
        r = self.put('resource-lists', nancy, '/resource-lists/list[@name="others"]/entry[2]', status=409)

        # 409 <uniqueness-failure>
        r = self.put('resource-lists', nancy, '/resource-lists/list[@name="friends"]/entry[1]', status=409)

if __name__ == '__main__':
    runSuiteFromModule()
