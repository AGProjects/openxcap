from common import *
from StringIO import StringIO
from lxml import etree

class XCAPCaps(XCAPTest):

    def test_schema(self):
        r = self.get_global('xcap-caps')
        validate_xcapcaps_schema(r.body)
        # TODO: auto check schema for every get

schema = load_schema('xcap-caps.xsd')

def validate_xcapcaps_schema(document):
    xml = validate(document, schema)
    assert xml.find('{urn:ietf:params:xml:ns:xcap-caps}auids') is not None
    assert xml.find('{urn:ietf:params:xml:ns:xcap-caps}extensions') is not None
    assert xml.find('{urn:ietf:params:xml:ns:xcap-caps}namespaces') is not None

if __name__ == '__main__':
    runSuiteFromModule()
