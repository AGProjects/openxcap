from common import *

pres_rules_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ruleset xmlns="urn:ietf:params:xml:ns:common-policy" xmlns:pr="urn:ietf:params:xml:ns:pres-rules" xmlns:cp="www.counterpath.com/privacy-lists">
      <rule id="pres_whitelist">
        <conditions>
          <identity>
            <one id="sip:2233350608@sip2sip.info"/>
            <one id="sip:31208005164@ag-projects.com"/>
          </identity>
        </conditions>
        <actions>
          <pr:sub-handling>allow</pr:sub-handling>
        </actions>
        <transformations>
          <pr:provide-services>
            <pr:all-services/>
          </pr:provide-services>
          <pr:provide-persons>
            <pr:all-persons/>
          </pr:provide-persons>
          <pr:provide-devices>
            <pr:all-devices/>
          </pr:provide-devices>
          <pr:provide-all-attributes/>
         </transformations>
        </rule>
      </ruleset>"""


class PresenceRulesTest(XCAPTest):

    def test_pidf_manipulation(self):
        self.delete_resource('pres-rules')
        self.assertStatus([200, 404])

        self.put_resource('pres-rules', pres_rules_xml)
        self.assertStatus(201)

        self.get_resource('pres-rules')
        self.assertStatus(200)
        self.assertBody(pres_rules_xml)
        self.assertHeader('Content-type', 'application/auth-policy+xml')

if __name__ == '__main__':
    runSuiteFromModule()
