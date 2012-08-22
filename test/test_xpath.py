#!/usr/bin/env python

# Copyright (C) 2007-2010 AG-Projects.
#

# All tests where ported from a test suite created by
# Inaki Baz Castillo <ibc@aliax.net>

import unittest
import sys
sys.path = ['../..'] + sys.path
import xcap.xpath
from xcap.uri import XCAPUri


default_namespaces = {'org.openxcap.watchers': 'http://openxcap.org/ns/watchers',
                      'org.openmobilealliance.pres-rules': 'urn:ietf:params:xml:ns:pres-rules',
                      'rls-services': 'urn:ietf:params:xml:ns:rls-services',
                      'resource-lists': 'urn:ietf:params:xml:ns:resource-lists',
                      'xcap-caps': 'urn:ietf:params:xml:ns:xcap-caps',
                      'org.openxcap.dialog-rules': 'http://openxcap.org/ns/dialog-rules',
                      'test-app': 'test-app',
                      'org.openmobilealliance.pres-content': 'urn:oma:xml:prs:pres-content',
                      'pidf-manipulation': 'urn:ietf:params:xml:ns:pidf',
                      'pres-rules': 'urn:ietf:params:xml:ns:pres-rules',
                      'org.openmobilealliance.xcap-directory': 'urn:oma:xml:xdm:xcap-directory'}

class XPathTest(unittest.TestCase):

    def test_xpath1_valid(self):
        selector = '/pres-rules/users/sip:%61lice@domain.org/Mis%20Documentos/index?xmlns(pr=urn:ietf:params:xml:ns:pres-rules)xmlns(cp=urn:ietf:params:xml:ns:common-policy)'
        u = XCAPUri('https://xcap.sipthor.net/xcap-root', selector, default_namespaces)
        self.assertEqual(str(u), 'https://xcap.sipthor.net/xcap-root/pres-rules/users/sip:alice@domain.org/Mis Documentos/index?xmlns(pr=urn:ietf:params:xml:ns:pres-rules)xmlns(cp=urn:ietf:params:xml:ns:common-policy)')

    def test_xpath2_invalid(self):
        selector = ''
        self.assertRaises(xcap.xpath.DocumentSelectorError, XCAPUri, 'https://xcap.sipthor.net/xcap-root', selector, default_namespaces)

    def test_xpath3_invalid(self):
        selector = '/pres-rules/global/mydoc/~~/'
        self.assertRaises(xcap.xpath.NodeParsingError, XCAPUri, 'https://xcap.sipthor.net/xcap-root', selector, default_namespaces)

    def test_xpath4_invalid(self):
        selector = 'pres-rules/global/mydoc'
        self.assertRaises(xcap.xpath.DocumentSelectorError, XCAPUri, 'https://xcap.sipthor.net/xcap-root', selector, default_namespaces)

    def test_xpath5_invalid(self):
        selector = '/pres-rules/lalala/presrules'
        self.assertRaises(xcap.xpath.DocumentSelectorError, XCAPUri, 'https://xcap.sipthor.net/xcap-root', selector, default_namespaces)

    def test_xpath6_invalid(self):
        selector = '/pres-rules/users/sip:alice@domain.org/'
        self.assertRaises(xcap.xpath.DocumentSelectorError, XCAPUri, 'https://xcap.sipthor.net/xcap-root', selector, default_namespaces)

    def test_xpath7_invalid(self):
        selector = '/pres-rules/users/sip:alice@domain.org'
        self.assertRaises(xcap.xpath.DocumentSelectorError, XCAPUri, 'https://xcap.sipthor.net/xcap-root', selector, default_namespaces)

    def test_xpath8_invalid(self):
        selector = '/pres-rules/users/sip:alice@domain.org/My%20presrules/~~/cp:ruleset/cp:rule%5b@id=%22pres_whitelist%22%5d/cp:conditions/cp:identity/cp:one%5b@id=%22sip:alice@example.org%22%5d'
        self.assertRaises(xcap.xpath.NodeParsingError, XCAPUri, 'https://xcap.sipthor.net/xcap-root', selector, default_namespaces)

    def test_xpath9_valid(self):
        selector = '/pres-rules/users/sip:alice@domain.org/My%20presrules/~~/cp:ruleset/cp:rule%5b@id=%22pres_whitelist%22%5d/cp:conditions/cp:identity/cp:one%5b@id=%22sip:alice@example.org%22%5d?xmlns(cp=urn:ietf:params:xml:ns:common-policy)'
        u = XCAPUri('https://xcap.sipthor.net/xcap-root', selector, default_namespaces)

    def test_xpath10_valid(self):
        selector = '/pres-rules/users/sip:alice@domain.org/My%20presrules/~~/cp:ruleset/cp:rule%5b@id=%22pres_whitelist%22%5d/cp:conditions/cp:identity/cp:one%5b@id=%22sip:alice@example.org%22%5d?xmlns(cp=urn:ietf:params:xml:ns:common-policy)'
        u = XCAPUri('https://xcap.sipthor.net/xcap-root', selector, default_namespaces)

    def test_xpath11_valid(self):
        selector = '/pres-rules/users/sip:alice@domain.org/presrules/~~/cp:ruleset/cp:rule%5b@id=%22pres_whitelist%22%5d/cp:conditions/cp:identity/@name?xmlns(cp=urn:ietf:params:xml:ns:common-policy)'
        u = XCAPUri('https://xcap.sipthor.net/xcap-root', selector, default_namespaces)
        self.assertEqual(xcap.xpath.AttributeSelector, type(u.node_selector.terminal_selector))
        self.assertEqual('@name', str(u.node_selector.terminal_selector))

    def test_xpath12_valid(self):
        selector = '/pres-rules/users/sip:alice@domain.org/presrules/~~/cp:ruleset/cp:rule%5b@id=%22pres_whitelist%22%5d/cp:conditions/cp:identity/namespace::*?xmlns(cp=urn:ietf:params:xml:ns:common-policy)'
        u = XCAPUri('https://xcap.sipthor.net/xcap-root', selector, default_namespaces)
        self.assertEqual(xcap.xpath.NamespaceSelector, type(u.node_selector.terminal_selector))


if __name__ == '__main__':
    unittest.main()

