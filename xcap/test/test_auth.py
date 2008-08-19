from common import *

resource_list_xml = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists">
     <list name="friends">
     </list>
   </resource-lists>"""

class AuthTest(XCAPTest):
    
    def test_authorization(self):
        self.put('resource-lists', resource_list_xml)
        self.get('dummy-application', status=404)
        
        ### the request cannot be authenticated
        #password = self.account
        #self.client.password += "dummy"
        #self.get('resource-lists', status=401)
        #self.client.password = password
        
        ### the request cannot be authorized (we're trying to access someone else' resource)
        #account = self.account
        #self.account = "dummy" + self.account
        #r = self.get('resource-lists', status=401)
        #self.client.account = account

if __name__ == '__main__':
    runSuiteFromModule()
