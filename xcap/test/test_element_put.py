from common import *

app = 'test-app'

start = '''<?xml version='1.0' encoding='UTF-8'?>
<root xmlns="test-app">
<el1 att="first"/>
<el1 att="second"/>
<!-- comment -->
<el2 att="first"/>
</root>'''

# when changing <root xmlns="test-app"> to <root> the document could be put, but
# element GET respons with 404.
# either GET should return what expected or a document without namespaces declaration
# should be rejected

headers = {'Content-type' : 'application/xcap-el+xml'}

class PutElementTest(XCAPTest):

    def reverse(self, node_selector):
        self.delete(app, node_selector)
        self.assertDocument(app, start)

    def test_creation(self):
        """Testing different ways of inserting an element as described in examples from Section 8.2.3
        (http://tools.ietf.org/html/rfc4825#section-8.2.3)

        After each PUT, DELETE is executed on the same URI and the resulting document must
        be the same as before the insertion.
        """
        self.put(app, start)

        for node_selector in ['/root/el1[@att="third"]',
                              '/root/el1[3][@att="third"]',
                              '/root/*[3][@att="third"]']:
            self.put_new(app, '<el1 att="third"/>', node_selector, headers=headers)
            self.assertDocument(app, '''<?xml version='1.0' encoding='UTF-8'?>
<root xmlns="test-app">
<el1 att="first"/>
<el1 att="second"/><el1 att="third"/>
<!-- comment -->
<el2 att="first"/>
</root>''')
            self.reverse(node_selector)

        # out-of-bound positional index in node selector results in 409 (XXX or 404?)
        for node_selector in ['root/el1[4][@att="third"]',
                              'root/*[0][@att="third"]']:
            self.put_new(app, '<el1 att="third"/>', node_selector, status=409, headers=headers)
            self.assertDocument(app, start)

        # replace 500 with something more appropriate
        #for node_selector in ['root/*[-1][@att="third"]']:
        #    self.put_new(app, '<el1 att="third"/>', node_selector, status=500, headers=headers)
        #    self.assertDocument(app, start)


        # following request would fail idempotency requirement (GET(PUT(x))=>x) if succeeded
        for node_selector in ['root/el1[@att="third"]',
                              'root/el1[3][@att="third"]',
                              'root/*[3][@att="third"]']:
            r = self.put_new(app, '<el1 att="fourth"/>', node_selector, status=409, headers=headers)
            self.assertInBody(r, 'cannot-insert')
            self.assertDocument(app, start)

        self.put_new(app, '<el3 att="first"/>', 'root/el3', headers=headers)
        self.assertDocument(app, '''<?xml version='1.0' encoding='UTF-8'?>
<root xmlns="test-app">
<el1 att="first"/>
<el1 att="second"/>
<!-- comment -->
<el2 att="first"/>
<el3 att="first"/></root>''')
        self.reverse('root/el3')

        for node_selector in ['root/el2[@att="2"]',
                              'root/el2[2][@att="2"]']:
            self.put_new(app, '<el2 att="2"/>', node_selector, headers=headers)
            self.assertDocument(app, '''<?xml version='1.0' encoding='UTF-8'?>
<root xmlns="test-app">
<el1 att="first"/>
<el1 att="second"/>
<!-- comment -->
<el2 att="first"/><el2 att="2"/>
</root>''')
            self.reverse(node_selector)

        self.put_new(app, '<el2 att="2"/>', 'root/*[2][@att="2"]', headers=headers)
        self.assertDocument(app, '''<?xml version='1.0' encoding='UTF-8'?>
<root xmlns="test-app">
<el1 att="first"/><el2 att="2"/>
<el1 att="second"/>
<!-- comment -->
<el2 att="first"/>
</root>''')
        self.reverse('root/*[2][@att="2"]')

        self.put_new(app, '<el2 att="2"/>', 'root/el2[1][@att="2"]', headers=headers)
        self.assertDocument(app, '''<?xml version='1.0' encoding='UTF-8'?>
<root xmlns="test-app">
<el1 att="first"/>
<el1 att="second"/>
<!-- comment -->
<el2 att="2"/><el2 att="first"/>
</root>''')
        self.reverse('root/el2[1][@att="2"]')

    def test_creation_starattr(self):
        """Testing PUT requests of form '*[@att="some"]' which require looking into body of PUT"""
        self.put(app, start)

        for selector in ['root/*[@att="2"]',
                         'root/el1[@att="2"]']:
            self.put_new(app, '<el1 att="2"/>', selector, headers=headers)
            self.assertDocument(app, '''<?xml version='1.0' encoding='UTF-8'?>
<root xmlns="test-app">
<el1 att="first"/>
<el1 att="second"/><el1 att="2"/>
<!-- comment -->
<el2 att="first"/>
</root>''')
            self.reverse(selector)

        # the same request - different body
        for selector in ['root/*[@att="2"]',
                         'root/el2[@att="2"]']:
            self.put_new(app, '<el2 att="2"/>', selector, headers=headers)
            self.assertDocument(app, '''<?xml version='1.0' encoding='UTF-8'?>
<root xmlns="test-app">
<el1 att="first"/>
<el1 att="second"/>
<!-- comment -->
<el2 att="first"/><el2 att="2"/>
</root>''')
            self.reverse(selector)

        # the same request - different body
        for selector in ['root/*[@att="2"]',
                         'root/el3[@att="2"]']:
            self.put_new(app, '<el3 att="2"/>', selector, headers=headers)
            self.assertDocument(app, '''<?xml version='1.0' encoding='UTF-8'?>
<root xmlns="test-app">
<el1 att="first"/>
<el1 att="second"/>
<!-- comment -->
<el2 att="first"/>
<el3 att="2"/></root>''')
            self.reverse(selector)

    def test_replacement(self):

        self.put(app, start)
        for node_selector in ['root/el1[@att="first"]',
                              'root/el1[1][@att="first"]',
                              'root/*[1][@att="first"]']:
            self.put(app, '<el1 att="third"/>', node_selector, status=409, headers=headers)
            self.assertDocument(app, start)

        for node_selector in ['root/el1[1]',
                              'root/*[1]']:
            self.put(app, start)
            self.put(app, '<el1 att="third"/>', node_selector, status=200, headers=headers)
            self.assertDocument(app, '''<?xml version='1.0' encoding='UTF-8'?>
<root xmlns="test-app">
<el1 att="third"/>
<el1 att="second"/>
<!-- comment -->
<el2 att="first"/>
</root>''')

if __name__ == '__main__':
    runSuiteFromModule()
