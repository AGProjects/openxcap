from common import *

resource_list_xml = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists">
     <list name="friends">
     </list>
   </resource-lists>"""

class AuthTest(XCAPTest):
    
    def test_authorization(self):
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus([200, 201])
        
        self.get_resource('resource-lists')
        self.assertStatus(200)
        
        self.get_resource('dummy-application')
        self.assertStatus(404)
        
        ### the request cannot be authenticated
        #password = self.account
        #self.password += "dummy"
        #self.get_resource('resource-lists')
        #self.assertStatus(401)
        #self.password = password
        
        ### the request cannot be authorized (we're trying to access someone else' resource)
        #account = self.account
        #self.account = "dummy" + self.account
        #self.get_resource('resource-lists')
        #self.assertStatus(401)
        #self.account = account

if __name__ == '__main__':
    runSuiteFromModule(__name__)
