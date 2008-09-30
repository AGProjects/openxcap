from common import *
from copy import copy
from lxml import etree
from StringIO import StringIO

class XCAPCaps(XCAPTest):

    def test_schema(self):
        r = self.get_global('xcap-caps')
        check_schema(r.body)
        # TODO: auto check schema for every get

def check_schema(document):
    schema_doc = etree.parse(StringIO(xcaps_schema))
    schema = etree.XMLSchema(schema_doc)
    parser = etree.XMLParser(schema = schema)
    xml = etree.fromstring(document, parser)
    assert xml.find('{urn:ietf:params:xml:ns:xcap-caps}auids') is not None
    assert xml.find('{urn:ietf:params:xml:ns:xcap-caps}extensions') is not None
    assert xml.find('{urn:ietf:params:xml:ns:xcap-caps}namespaces') is not None

xcaps_schema = """<?xml version="1.0" encoding="UTF-8"?>
   <xs:schema targetNamespace="urn:ietf:params:xml:ns:xcap-caps"
    xmlns="urn:ietf:params:xml:ns:xcap-caps"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    elementFormDefault="qualified" attributeFormDefault="unqualified">
    <xs:element name="xcap-caps">
     <xs:annotation>
      <xs:documentation>Root element for xcap-caps</xs:documentation>
     </xs:annotation>
     <xs:complexType>
      <xs:sequence>
       <xs:element name="auids">
        <xs:annotation>
         <xs:documentation>List of supported AUID.</xs:documentation>
        </xs:annotation>
        <xs:complexType>
         <xs:sequence minOccurs="0" maxOccurs="unbounded">
          <xs:element name="auid" type="auidType"/>
         </xs:sequence>
        </xs:complexType>
       </xs:element>
       <xs:element name="extensions" minOccurs="0">
        <xs:annotation>
         <xs:documentation>List of supported extensions.
         </xs:documentation>
        </xs:annotation>
        <xs:complexType>
         <xs:sequence minOccurs="0" maxOccurs="unbounded">
          <xs:element name="extension" type="extensionType"/>
         </xs:sequence>
        </xs:complexType>
       </xs:element>
       <xs:element name="namespaces">
        <xs:annotation>
         <xs:documentation>List of supported namespaces.
         </xs:documentation>
        </xs:annotation>
        <xs:complexType>
         <xs:sequence minOccurs="0" maxOccurs="unbounded">
          <xs:element name="namespace" type="namespaceType"/>
         </xs:sequence>
        </xs:complexType>
       </xs:element>
       <xs:any namespace="##other" processContents="lax"
        minOccurs="0" maxOccurs="unbounded"/>
      </xs:sequence>
     </xs:complexType>
    </xs:element>
    <xs:simpleType name="auidType">
     <xs:annotation>
      <xs:documentation>AUID Type</xs:documentation>
     </xs:annotation>
     <xs:restriction base="xs:string"/>
    </xs:simpleType>
    <xs:simpleType name="extensionType">
     <xs:annotation>
      <xs:documentation>Extension Type</xs:documentation>
     </xs:annotation>
     <xs:restriction base="xs:string"/>
    </xs:simpleType>
    <xs:simpleType name="namespaceType">
     <xs:annotation>
      <xs:documentation>Namespace type</xs:documentation>
     </xs:annotation>
     <xs:restriction base="xs:anyURI"/>
    </xs:simpleType>
   </xs:schema>
"""

if __name__ == '__main__':
    runSuiteFromModule()
