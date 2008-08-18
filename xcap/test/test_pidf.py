from common import *

pidf_xml = """<?xml version='1.0' encoding='UTF-8'?>
        <presence xmlns='urn:ietf:params:xml:ns:pidf' 
                  xmlns:dm='urn:ietf:params:xml:ns:pidf:data-model' 
                  xmlns:rpid='urn:ietf:params:xml:ns:pidf:rpid'
                  xmlns:c='urn:ietf:params:xml:ns:pidf:cipid'
                  entity='sip:test@example.com'>
          <tuple id='xa432124'>
            <status>
              <basic>open</basic>
            </status>
          </tuple>
          <dm:person id='p57123abx'>
            <rpid:activities><rpid:unknown/></rpid:activities>
          </dm:person>
        </presence>"""


class PIDFTest(XCAPTest):

    def test_pidf_manipulation(self):
        self.delete_resource('pidf-manipulation')
        self.assertStatus([200, 404])

        self.get_resource('pidf-manipulation')
        self.assertStatus(404)

        self.put_resource('pidf-manipulation', pidf_xml)
        self.assertStatus(201)

        self.get_resource('pidf-manipulation')
        self.assertStatus(200)
        self.assertBody(pidf_xml)
        self.assertHeader('Content-type', 'application/pidf+xml')

        self.put_resource('pidf-manipulation', pidf_xml)
        self.assertStatus(200)

        self.delete_resource('pidf-manipulation')
        self.assertStatus(200)

        self.delete_resource('pidf-manipulation')
        self.assertStatus(404)

if __name__ == '__main__':
    runSuiteFromModule()
