from common import *

resource_lists_xml = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <list name="friends">
     <entry uri="sip:bill@example.com">
      <display-name>Bill Doe</display-name>
     </entry>
     <entry-ref ref="resource-lists/users/sip:bill@example.com/index/~~/resource-lists/list%5b@name=%22list1%22%5d/entry%5b@uri=%22sip:petri@example.com%22%5d"/>
     <list name="close-friends">
      <display-name>Close Friends</display-name>
      <entry uri="sip:joe@example.com">
       <display-name>Joe Smith</display-name>
      </entry>
      <entry uri="sip:nancy@example.com">
       <display-name>Nancy Gross</display-name>
      </entry>
      <external anchor="http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list%5b@name=%22mkting%22%5d">
        <display-name>Marketing</display-name>
       </external>
     </list>
    </list>
   </resource-lists>"""

resource_lists_xml_badformed = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <list name="friends">
     <entry uri="sip:bill@example.com">
      <display-name>Bill Doe</display-name>
     </entry>
     <entry-ref ref="resource-lists/users/sip:bill@example.com/index/~~/resource-lists/list%5b@name=%22list1%22%5d/entry%5b@uri=%22sip:petri@example.com%22%5d"/>
     <list name="close-friends">
      <display-name>Close Friends</display-name>
      <entry uri="sip:joe@example.com">
       <display-name>Joe Smith</display-name>
      </entry>
      <entry uri="sip:nancy@example.com">
       <display-name>Nancy Gross</display-name>
      </entry>
      <external anchor="http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list%5b@name=%22mkting%22%5d">
        <display-name>Marketing</display-name>
       </external>
     </list>
    </list>
   </resource-listsXXXXXXXXXXXXXXXXXXXXX>"""

# well-formed, but fails to meet constraints
resource_lists_xml_non_unique_list = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <list name="friends">
     <entry uri="sip:bill@example.com">
      <display-name>Bill Doe</display-name>
     </entry>
     <entry-ref ref="resource-lists/users/sip:bill@example.com/index/~~/resource-lists/list%5b@name=%22list1%22%5d/entry%5b@uri=%22sip:petri@example.com%22%5d"/>
     <list name="close-friends">
      <display-name>Close Friends</display-name>
      <entry uri="sip:joe@example.com">
       <display-name>Joe Smith</display-name>
      </entry>
      <entry uri="sip:nancy@example.com">
       <display-name>Nancy Gross</display-name>
      </entry>
      <external anchor="http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list%5b@name=%22mkting%22%5d">
        <display-name>Marketing</display-name>
       </external>
     </list>
    </list>
   <list name="friends"/>
   </resource-lists>"""

resource_lists_xml_baduri = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <list name="friends">
     <entry uri="sip:bill@example.com">
      <display-name>Bill Doe</display-name>
     </entry>
     <entry-ref ref="resource-lists/users/sip:bill@example.com/index/~~/resource-lists/list%5b@name=%22list1%22%5d/entry%5b@uri=%22sip:petri@example.com%22%5d"/>
     <list name="close-friends">
      <display-name>Close Friends</display-name>
      <entry uri="sip:joeXexample.com">
       <display-name>Joe Smith</display-name>
      </entry>
      <entry uri="sip:nancy@example.com">
       <display-name>Nancy Gross</display-name>
      </entry>
      <external anchor="http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list%5b@name=%22mkting%22%5d">
        <display-name>Marketing</display-name>
       </external>
     </list>
    </list>
   </resource-lists>"""


class DocumentTest(XCAPTest):
  
    def test_operations(self):
        self.getputdelete_successful('resource-lists', resource_lists_xml, 'application/resource-lists+xml')

        self.put_rejected('resource-lists', resource_lists_xml_badformed)
        # check body for <schema-validation-error>

        self.put_rejected('resource-lists', resource_lists_xml_non_unique_list)
        # check body for <uniqueness-failure>

#TODO
#        self.put_rejected('resource-lists', resource_lists_xml_baduri)
#        # check body for <contstraint-failure>


if __name__ == '__main__':
    runSuiteFromModule()
