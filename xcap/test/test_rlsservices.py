
# Copyright (C) 2007-2010 AG-Projects.
#

from common import *

rls_services_xml = """<?xml version="1.0" encoding="UTF-8"?>
   <rls-services xmlns="urn:ietf:params:xml:ns:rls-services"
      xmlns:rl="urn:ietf:params:xml:ns:resource-lists"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <service uri="sip:mybuddies@example.com">
     <resource-list>http://xcap.example.com/resource-lists/users/sip:joe@example.com/index/~~/resource-lists/list%5b@name=%22l1%22%5d</resource-list>
     <packages>
      <package>presence</package>
     </packages>
    </service>
    <service uri="sip:marketing@example.com">
      <list name="marketing">
        <rl:entry uri="sip:joe@example.com"/>
        <rl:entry uri="sip:sudhir@example.com"/>
      </list>
      <packages>
        <package>presence</package>
      </packages>
    </service>
   </rls-services>"""


rls_services_xml_badformed = """<?xml version="1.0" encoding="UTF-8"?>
   <rls-services xmlns="urn:ietf:params:xml:ns:rls-services"
      xmlns:rl="urn:ietf:params:xml:ns:resource-lists"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <service uri="sip:mybuddies@example.com">
     <resource-list>http://xcap.example.com/resource-lists/users/sip:joe@example.com/index/~~/resource-lists/list%5b@name=%22l1%22%5d</resource-list>
     <packages>
      <package>presence</package>
     </packages>
    </service>
    <service uri="sip:marketing@example.com">
      <list name="marketing">
        <rl:entry uri="sip:joe@example.com"/>
        <rl:entry uri="sip:sudhir@example.com"/>
      </list>
      <packages>
        <package>presence</package>
      </packages>
    </service>
   </rls-servicesXXXX>"""

# resource-lists constraints should be checked as well
rls_services_xml_non_unique_list = """<?xml version="1.0" encoding="UTF-8"?>
   <rls-services xmlns="urn:ietf:params:xml:ns:rls-services"
      xmlns:rl="urn:ietf:params:xml:ns:resource-lists"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <service uri="sip:mybuddies@example.com">
     <resource-list>http://xcap.example.com/resource-lists/users/sip:joe@example.com/index/~~/resource-lists/list%5b@name=%22l1%22%5d</resource-list>
     <packages>
      <package>presence</package>
     </packages>
    </service>
    <service uri="sip:marketing@example.com">
      <list name="marketing">
        <rl:entry uri="sip:joe@example.com"/>
        <rl:entry uri="sip:sudhir@example.com"/>
      </list>
      <list name="marketing"/>
      <packages>
        <package>presence</package>
      </packages>
    </service>
   </rls-services>"""

# this one is actually caught by schema validation, not by code
rls_services_xml_non_unique_service = """<?xml version="1.0" encoding="UTF-8"?>
   <rls-services xmlns="urn:ietf:params:xml:ns:rls-services"
      xmlns:rl="urn:ietf:params:xml:ns:resource-lists"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <service uri="sip:mybuddies@example.com">
     <resource-list>http://xcap.example.com/resource-lists/users/sip:joe@example.com/index/~~/resource-lists/list%5b@name=%22l1%22%5d</resource-list>
     <packages>
      <package>presence</package>
     </packages>
    </service>
    <service uri="sip:marketing@example.com">
      <list name="marketing">
        <rl:entry uri="sip:joe@example.com"/>
        <rl:entry uri="sip:sudhir@example.com"/>
      </list>
      <list name="marketing"/>
      <packages>
        <package>presence</package>
      </packages>
    </service>
   <service uri="sip:mybuddies@example.comx"/>
   </rls-services>"""

# check for that service uniqueness is enforced across different users
# check index

class DocumentTest(XCAPTest):
    
    def test_operations(self):
        self.getputdelete('rls-services', rls_services_xml, 'application/rls-services+xml')

        self.put_rejected('rls-services', rls_services_xml_badformed)
        self.put_rejected('rls-services', rls_services_xml_non_unique_list)
        self.put_rejected('rls-services', rls_services_xml_non_unique_service)

        #self.account = 'test2@example.com'
        #self.delete_resource('rls-services')
        #self.assertStatus([200, 404])

        ## we aint doing that
        ## rejected because the other user has the services with the same name
        ##self.put_rejected('rls-services', rls_services_xml)

if __name__ == '__main__':
    runSuiteFromModule()
