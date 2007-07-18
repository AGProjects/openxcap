
import unittest
from common import XCAPTest


resource_list_xml = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists">
     <list name="friends">
     </list>
   </resource-lists>"""


class DocumentTest(XCAPTest):
    
    def test_operations(self):
        self.delete_resource('resource-lists')
        self.assertStatus([200, 404])
        
        self.get_resource('resource-lists')
        self.assertStatus(404)
        
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus(201)
        
        self.get_resource('resource-lists')
        self.assertStatus(200)
        self.assertBody(resource_list_xml)
        self.assertHeader('Content-type', 'application/resource-lists+xml')
        
        self.put_resource('resource-lists', resource_list_xml)
        self.assertStatus(200)
        
        self.delete_resource('resource-lists')
        self.assertStatus(200)
        
        self.delete_resource('resource-lists')
        self.assertStatus(404)


def suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(DocumentTest)
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
