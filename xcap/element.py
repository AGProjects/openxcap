"""Element handling as described in RFC 4825.

This module implements
 * location of an element in xml document
 * location of insertion point for a new element in xml document

This allows to implement GET/PUT/DELETE for elements in XCAP server.

Syntax for element selectors is a subset of xpath, but a xpath implementation
was not used. One reason is that xpath only implements locating an element but not
an insertion point for element selectors which do not point to an existing
element, but will point to the inserted element after PUT.

For element selectors of type *[@att="value"] insertion point depends on
the content of a new element. For RFC compliant behavior, fix such requests
by replacing '*' with root tag of new element's body.
"""
from xml import sax
from StringIO import StringIO
from xcap import uri

class Step:
    # to be matched against uri.Step

    def __init__(self, name, position = 0):
        self.name = name

        # this integer holds index of a child element currently in processing
        self.position = position

    def __repr__(self):
        return '%s[pos=%s]' % (self.name, self.position)


class ContentHandlerBase(sax.ContentHandler):

    def __init__(self, selector):
        sax.ContentHandler.__init__(self)
        self.selector = selector
        self.state = None
        self.locator = None

    def setDocumentLocator(self, locator):
        self.locator = locator

    def pos(self):
        return self.locator._ref._parser.CurrentByteIndex

    def set_state(self, new_state):
        #print new_state, 'at %s' % str(self.pos())
        self.state = new_state

    def set_end_pos(self, end_pos, end_tag = None, end_pos_2 = None):
        self.end_pos = end_pos
        self.end_tag = end_tag
        self.end_pos_2 = end_pos_2

    def fix_end_pos(self, document):
        if self.end_tag is not None and self.end_tag in document[self.end_pos:self.end_pos_2]:
            if self.end_pos_2 is None:
                self.end_pos = 1 + document.index('>', self.end_pos)
            else:
                self.end_pos = 1 + document.index('>', self.end_pos, self.end_pos_2)

    def __repr__(self):
        return '<%s selector=%r state=%r>' % (self.__class__.__name__, self.selector, self.state)


class ElementLocator(ContentHandlerBase):
    """Locates element in a document by element selector expression (subset
    of XPATH defined in RFC 4825)

    There's an intentional difference from XPATH (at least as implemented
    in lxml): tail following closing tag is not included in the end result
    (this doesn't make sense for XCAP and incompatible with some of the
    requirements in RFC).
    """

    def startDocument(self):
        if self.locator is None:
            raise RuntimeError("The parser doesn't support locators")
        self.path = []
        self.state = 'LOOKING'
        self.curstep = 0
        self.skiplevel = 0
        self.set_end_pos(None, None, None)

    def startElementNS(self, name, qname, attrs):
        #print '-' * (len(self.path) + self.skiplevel), '<', name, '/' + '/'.join(map(str, self.path))
        if self.state=='DONE' and self.end_pos_2 is None:
            self.end_pos_2 = self.pos()

        if self.skiplevel>0:
            self.skiplevel += 1
            return

        if self.curstep>=len(self.selector):
            self.skiplevel = 1
            return

        if self.path:
            parent = self.path[-1]
        else:
            parent = None

        curstep = self.selector[self.curstep]
        #print `name`, `curstep.name`

        if curstep.name == '*' or curstep.name == name:
            if parent:
                parent.position += 1
        else:
            self.skiplevel = 1
            return

        if curstep.position is not None and curstep.position != parent.position:
            self.skiplevel = 1
            return

        if curstep.att_name is not None and attrs.get(curstep.att_name)!=curstep.att_value:
            self.skiplevel = 1
            return

        #print '%r matched' % curstep
        self.curstep += 1
        self.path.append(Step(qname))

        if len(self.path)==len(self.selector):
            if self.state=='LOOKING':
                self.set_state('FOUND')
                self.start_pos = self.pos()
            elif self.state=='DONE':
                self.set_state('MANY')

    def endElementNS(self, name, qname):
        #print '-' * (len(self.path) + self.skiplevel-1), '>', name, '/' + '/'.join(map(str, self.path))
        if self.state=='DONE' and self.end_pos_2 is None:
            self.end_pos_2 = self.pos()

        if self.skiplevel>0:
            self.skiplevel -= 1
            return

        if len(self.path)==len(self.selector) and self.state=='FOUND':
            self.set_state('DONE')
            # QQQ why qname passed to endElementNS is None?
            qname = self.path[-1].name
            self.set_end_pos(self.pos(), '</' + qname + '>')
            # where does pos() point to? two cases:
            # 1. <name>....*HERE*</name>
            # 2. <name/>*HERE*...
            # If it's the first case we need to adjust pos() by len('</name>')
            # To determine the case, let's mark the position of the next startElement/endElement
            # and see if there '</name>' substring right after end_pos limited by end_pos_2
            # 1. <name>....*end_pos*</name>...*end_pos_2*<...
            # 2. <name/>*end_pos*...*end_pos_2*<...

        element = self.path.pop()
        self.curstep -= 1


class InsertPointLocator(ContentHandlerBase):
    """Locate the insertion point -- where in the document a new element should be inserted.

    It operates under assumption that the request didn't yield any matches
    with ElementLocator (its state was 'LOOKING' after parsing).

    Note, that this class doesn't know what will be inserted and therefore
    may do not do what you want with requests like 'labels/*[att="new-att"]'.
    """

    def startDocument(self):
        if self.locator is None:
            raise RuntimeError("The parser doesn't support locators")
        self.path = []
        self.state = 'LOOKING'
        self.curstep = 0
        self.skiplevel = 0
        self.set_end_pos(None, None, None)

    def startElementNS(self, name, qname, attrs):
        #print '<' * (1+len(self.path) + self.skiplevel), name, '/' + '/'.join(map(str, self.path)),
        #print self.curstep, self.skiplevel

        if self.state=='DONE' and self.end_pos_2 is None:
            self.end_pos_2 = self.pos()

        if self.skiplevel>0:
            self.skiplevel += 1
            return

        if self.curstep>=len(self.selector):
            self.skiplevel = 1
            return

        if self.path:
            parent = self.path[-1]
        else:
            parent = None

        curstep = self.selector[self.curstep]

        if curstep.name == '*' or curstep.name == name:
            if parent:
                parent.position += 1
        else:
            self.skiplevel = 1
            return

        is_last_step = len(self.path)+1 == len(self.selector)

        if not is_last_step:
            if curstep.position is not None and curstep.position != parent.position:
                self.skiplevel = 1
                return
            if curstep.att_name is not None and \
               attrs.get(curstep.att_name)!=curstep.att_value:
                self.skiplevel = 1
                return
        else:
            if curstep.position == 1 and parent.position == 1:
                self.set_state('DONE')
                self.set_end_pos(self.pos(), end_pos_2=self.pos())

        self.curstep += 1
        self.path.append(Step(qname))

    def endElementNS(self, name, qname):
        #print '>' * (1+len(self.path)+self.skiplevel-1), name, '/' + '/'.join(map(str, self.path)),
        #print self.curstep, self.skiplevel

        if self.state=='DONE' and self.end_pos_2 is None:
            self.end_pos_2 = self.pos()

        if self.skiplevel>0:
            self.skiplevel -= 1
            return

        qname = self.path[-1].name

        curstep = self.selector[-1]
        if len(self.path)==len(self.selector):
            parent = self.path[-2]
            if curstep.position is None:
                if self.state=='DONE':
                    self.set_state('MANY')
                else:
                    self.set_state('CLOSED')
                self.set_end_pos(self.pos(), '</' + qname + '>')
            elif curstep.position-1 == parent.position:
                if self.state=='DONE':
                    self.set_state('MANY')
                else:
                    self.set_state('DONE')
                self.set_end_pos(self.pos(), '</' + qname + '>')
        elif len(self.path)+1==len(self.selector):
            if self.state == 'CLOSED':
                self.set_state('DONE')
                if curstep.name=='*' and curstep.position is None:
                    self.set_end_pos(self.pos(), end_pos_2 = self.pos())
            elif self.state == 'LOOKING':
                self.set_state('DONE')
                self.set_end_pos(self.pos(), end_pos_2 = self.pos())

        element = self.path.pop()
        self.curstep -= 1


class LocatorError(ValueError):

    def __init__(self, msg, handler=None):
        ValueError.__init__(self, msg)
        self.handler = handler

    @staticmethod
    def generate_error(locator, element_selector):
        if locator.state == 'LOOKING':
            return None
        elif locator.state == 'MANY':
            raise SelectorError(element_selector, locator)
        else:
            raise LocatorError('Internal error in %s' % locator.__class__.__name__, locator)


class SelectorError(LocatorError):
    def __init__(self, msg, handler=None):
        msg = 'more than one element matches: %s' % msg
        LocatorError.__init__(self, msg, handler)


class XCAPElement:

    @classmethod
    def make_parser(cls):
        parser = sax.make_parser()
        parser.setFeature(sax.handler.feature_namespaces, 1)

        # Q: SAXNotSupportedException: expat does not report namespace prefixes
        # A: you need pyxml library which provides _xmlplus package;
        #    on debian: aptitude install python-xml
        parser.setFeature(sax.handler.feature_namespace_prefixes, 1) # need _xmlplus package
        return parser

    @classmethod
    def find(cls, document, element_selector):
        """Return an element as (first index, last index+1)

        If it couldn't be found, return None.
        If there're several matches, raise SelectorError.
        """
        parser = cls.make_parser()
        el = ElementLocator(element_selector)
        parser.setContentHandler(el)
        parser.parse(StringIO(document))
        if el.state == 'DONE':
            el.fix_end_pos(document)
            return (el.start_pos, el.end_pos)
        else:
            return LocatorError.generate_error(el, element_selector)

    @classmethod
    def get(cls, document, element_selector):
        """Return an element as a string.

        If it couldn't be found, return None.
        If there're several matches, raise SelectorError.
        """
        location = cls.find(document, element_selector)
        if location is not None:
            start, end = location
            return document[start:end]

    @classmethod
    def delete(cls, document, element_selector):
        """Return document with element deleted.

        If it couldn't be found, return None.
        If there're several matches, raise SelectorError.
        """
        location = cls.find(document, element_selector)
        if location is not None:
            start, end = location
            return document[:start] + document[end:]

    @classmethod
    def put(cls, document, element_selector, element_str):
        """Return a 2-items tuple: (new_document, created).
        new_document is a copy of document with element_str inside.
        created is True if insertion was performed as opposed to replacement.

        If element_selector matches an existing element, it is replaced with element_str.
        If not, it is inserted at appropriate place.

        If it's impossible to insert at this location, return None.
        If element_selector matches more than one element or more than one possible
        place to insert and there're no rule to resolve the ambiguity then SelectorError
        is raised.
        """
        location = cls.find(document, element_selector)
        if location is None:
            ipl = InsertPointLocator(element_selector)
            parser = cls.make_parser()
            parser.setContentHandler(ipl)
            parser.parse(StringIO(document))
            if ipl.state == 'DONE':
                ipl.fix_end_pos(document)
                start, end = ipl.end_pos, ipl.end_pos
                created = True
            else:
                return LocatorError.generate_error(ipl, element_selector)
        else:
            start, end = location
            created = False
        return (document[:start] + element_str + document[end:], created)

# Q: why create a new parser for every parsing?
# A: when sax.make_parser() was called once, I've occasionaly encountered an exception like this:
#
#   File "/usr/lib/python2.5/site-packages/xcap/appusage/__init__.py", line 178, in _cb_get_element
#     result = XCAPElement.get(response.data, uri.node_selector.element_selector)
#   File "/usr/lib/python2.5/site-packages/xcap/element.py", line 323, in get
#     location = cls.find(document, element_selector)
#   File "/usr/lib/python2.5/site-packages/xcap/element.py", line 308, in find
#     cls.parser.setContentHandler(el)
#   File "/usr/lib/python2.5/site-packages/_xmlplus/sax/expatreader.py", line 128, in setContentHandler
#     self._reset_cont_handler()
#   File "/usr/lib/python2.5/site-packages/_xmlplus/sax/expatreader.py", line 234, in _reset_cont_handler
#     self._cont_handler.processingInstruction
# exceptions.AttributeError: 'NoneType' object has no attribute 'ProcessingInstructionHandler'
#
# I have no idea what does that mean, but probably something to do with parser's state becoming invalid
# under some circumstances.

# prevent openxcap from starting if _xmlplus is not installed
XCAPElement.make_parser() # test parser creation

class _test:

    source1 = """<?xml version="1.0" encoding="iso-8859-1"?>
<labels>
  <label added="2003-06-20">
    <quote>
      <emph>Midwinter Spring</emph> is its own season&#8230;
    </quote>
    <name>Thomas Eliot</name>
    <address>
      <street>3 Prufrock Lane</street>
      <city>Stamford</city>
      <state>CT</state>
    </address>
  </label>
  <comment>hello</comment>
  <first>
    <second>hi!</second>
  </first>
  <label added="2003-06-10">
    <name>Ezra Pound</name>
    <address>
      <street>45 Usura Place</street>
      <city>Hailey</city>
      <state>ID</state>
    </address>
  </label>
  <label added="yesterday"/>
  <label added="&quot;quoted&quot;"/>
  <comment>world</comment>
</labels>
"""

    source2 = """<?xml version="1.0"?>
    <root>
     <el1 att="first"/>
     <el1 att="second"/>
     <!-- comment -->
     <el2 att="first"/>
    </root>"""

    rls_services_xml = """<?xml version="1.0" encoding="UTF-8"?>
   <rls-services xmlns="urn:ietf:params:xml:ns:rls-services"
      xmlns:rl="urn:ietf:params:xml:ns:resource-lists"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <service uri="sip:mybuddies@example.com">
     <resource-list>http://xcap.example.com/resource-lists/users/sip:joe@example.com/index/~~/resource-lists/list%5b@name=%22l1%22%5d</resource-list>
     <packages>
      <package>presence</package>
     </packages>
    </service>
    <service uri="sip:marketing@example.com">
      <list name="marketing">
        <rl:entry uri="sip:joe@example.com"/>
        <rl:entry uri="sip:sudhir@example.com"/>
      </list>
      <packages>
        <package>presence</package>
      </packages>
    </service>
   </rls-services>"""

    @staticmethod
    def trim(s0):
        "remove tail from the result"
        s = s0
        while s and s[-1]!='>':
            s = s[:-1]
        if s:
            return s
        else:
            return s0

    @classmethod
    def lxml_xpath_get(cls, xpath_expr, source=source1, namespace=None, namespaces={}):
        "First, use xpath from lxml, which should produce the same results for existing nodes"
        assert '/'.startswith(xpath_expr[:1]), xpath_expr
        doc = etree.parse(StringIO(source))
        try:
            # where to put namespace?
            r = doc.xpath(xpath_expr, namespaces=namespaces)
        except etree.XPathEvalError:
            return uri.NodeParsingError
        except Exception, ex:
            traceback.print_exc()
            return ex
        if len(r)==1:
            return cls.trim(etree.tostring(r[0]))
        elif len(r)>1:
            return SelectorError

    @staticmethod
    def xcap_get(xpath_expr, source=source1, namespace=None, namespaces={}):
        "Second, use xpath_get_element"
        try:
            selector = uri.parse_node_selector(xpath_expr, namespace, namespaces)[0]
            return XCAPElement.get(source, selector)
        except (uri.NodeParsingError, SelectorError), ex :
            return ex.__class__
        except Exception, ex:
            traceback.print_exc()
            return ex

    @staticmethod
    def xcap_put(xpath_expr, element, source=source1, namespace=None, namespaces={}):
        try:
            selector = uri.parse_node_selector(xpath_expr, namespace, namespaces)[0]
            return XCAPElement.put(source, selector, element)[0]
        except (uri.NodeParsingError, SelectorError), ex :
            return ex.__class__
        except Exception, ex:
            traceback.print_exc()
            return ex

    @classmethod
    def test_get(cls):
        emph1 = '<emph>Midwinter Spring</emph>'
        thomas = '<name>Thomas Eliot</name>'
        ezra = '<name>Ezra Pound</name>'
        hi = '<second>hi!</second>'
        yesterday = '<label added="yesterday"/>'

        for xpath_get in [cls.lxml_xpath_get, cls.xcap_get]:
            #print '\n' + xpath_get.__doc__

            def check(expected, argument, **kwargs):
                result = xpath_get(argument, **kwargs)
                if expected != result:
                    print 'EXPR: %s(%r)\nEXPECT: %r\nRESULT: %r\n' % \
                          (xpath_get.__name__, argument, expected, result)
                #else:
                    #print '%s(%r)..ok!' % (xpath_get.__name__, argument)

            # simple expr
            check(hi, '/labels/first/second')

            # error, ambiguity - there're two labels
            check(SelectorError, '/labels/label')

            # no ambiguity, only one label has <quote>
            check(emph1, '/labels/label/quote/emph')

            check(None, '/labels/labelx')

            # there're minor differences between lxml/xpath and this module:
            if xpath_get == cls.lxml_xpath_get:
                check(uri.NodeParsingError, '/labels\label')
                check(None, '/')
                expected1 = '<el1/>'
                expected2 = None
            else:
                check(None, '/labels\label')
                check(uri.NodeParsingError, '/')
                expected1 = '<el1></el1>'
                expected2 = '<rl:entry uri="sip:joe@example.com"/>'

            check(expected1, '/el1/el1', source='<?xml version="1.0"?><el1><el1></el1></el1>')

            # lxml doesn't allow to have default namespace in the XPATH
            check(expected2,
                  '/rls-services/service[2]/list/rl:entry[1]',
                  source=cls.rls_services_xml,
                  namespace="urn:ietf:params:xml:ns:rls-services",
                  namespaces={'rl': 'urn:ietf:params:xml:ns:resource-lists'})


            check(emph1, '/labels/*[1]/quote/emph')
            check(emph1, '/labels/label[1]/quote/emph')
            check(thomas, '/labels/label[1]/name')
            check(ezra, '/labels/label[@added="2003-06-10"]/name')
            check(ezra, '/labels/label[2][@added="2003-06-10"]/name')
            check(ezra, '/labels/label[2]/name')
            check(ezra, '/labels/*[4]/name')
            check(ezra, '/labels/*[4][@added="2003-06-10"]/name')

            check(uri.NodeParsingError, '')
            check(cls.source1.split('\n', 1)[1].rstrip('\n'), '/labels')

            check(yesterday, '/labels/label[@added="yesterday"]')
            check(yesterday, '/labels/label[3]')
            check(yesterday, '/labels/label[3][@added="yesterday"]')
            check(yesterday, '/labels/*[@added="yesterday"]')
            check(yesterday, '/labels/*[5]')
            check(yesterday, '/labels/*[5][@added="yesterday"]')

            check(SelectorError, '/labels/*')
            check(None, '/labels/first/second/*')

            check('<labels/>', '/labels', source='<labels/>')

            check('<el3 att="first"/>', '/root/el3', source="""<?xml version="1.0"?>
    <root>
     <el1 att="first"/>
     <el1 att="second"/>
     <!-- comment -->
     <el2 att="first"/>
    <el3 att="first"/></root>""")

            check('<el1/>', '/el1/el1', source='<?xml version="1.0"?><el1><el1/></el1>')
            check('<el1 att="second"/>', '/root/el1[2]', source=cls.source2)

#           what is the problem with this?
#             check('<label added="&quot;quoted&quot;"/>',
#                   '''/labels/label[@added='"quoted"']''',
#                   source=cls.source1)

    @classmethod
    def xcap_get2(cls, expr, source=source2):
        "get node using SourceElement.get_element, but check the result with lxml_xpath_get"
        retrieved = cls.xcap_get(expr, source=source)
        retrieved2 = cls.lxml_xpath_get(expr, source=source)
        if retrieved2 != retrieved:
            print 'xcap_get and lxml_xcap_get results differ! %r' % expr
            print 'xcap_get: %s' % retrieved
            print 'lxml_xpath_get: %s' % retrieved2
        return retrieved

    # if true, ignore the value to put and put '*' instead, so it can be easily spotted by human
    simplify_check = False

    @classmethod
    def check(cls, insert_pos, what, expected, source=source2, **kwargs):
        if cls.simplify_check:
            if isinstance(expected, basestring):
                expected = expected.replace(what, '*')
                what = '*'
        result = cls.xcap_put(insert_pos, what, source=source, **kwargs)

        if callable(expected):
            result_check = expected
        else:
            result_check = lambda s: s == expected

        if not result_check(result):
            print 'insert_pos: %s' % insert_pos
            print 'result: %s' % result
            print 'expected: %s' % expected
            return

        if not cls.simplify_check:
            retrieved = cls.xcap_get2(insert_pos, result)
            if retrieved != what.strip():
                print 'GET(PUT(x))!=x'
                print 'PUT: %r' % what
                print 'GOT: %r' % retrieved

    @classmethod
    def test_put0(cls):
        pos = '/rls-services/service[2]/list/rl:entry[1]'
        what = '<rl:entry uri="sip:first@example.com"/>'
        namespace="urn:ietf:params:xml:ns:rls-services"
        namespaces={'rl': 'urn:ietf:params:xml:ns:resource-lists'}
        result = cls.xcap_put(pos,
                              what,
                              source=cls.rls_services_xml,
                              namespace=namespace,
                              namespaces=namespaces)

        retrieved = cls.xcap_get(pos, result, namespace, namespaces)
        if retrieved != what.strip():
            print 'GET(PUT(x))!=x'
            print 'PUT: %r' % what
            print 'GOT: %r' % retrieved


    @classmethod
    def test_put1(cls):
        "now something xpath alone cannot do: locate position for insertion of a new node"

        check = cls.check

        check('/labels/label[@added="2008-08-21"]',
              '<label added="2008-08-21"/>',
              lambda x: x and '<label added="2008-08-21"/>' in x, source=cls.source1)

        for selector in ['/root/el1[@att="third"]',
                         '/root/el1[3][@att="third"]',
                         '/root/*[3][@att="third"]']:
            check(selector, '<el1 att="third"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"/>
     <el1 att="second"/><el1 att="third"/>
     <!-- comment -->
     <el2 att="first"/>
    </root>""")

        check('/root/el3', '<el3 att="first"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"/>
     <el1 att="second"/>
     <!-- comment -->
     <el2 att="first"/>
    <el3 att="first"/></root>""")

        for selector in ['/root/el2[@att="2"]',
                         '/root/el2[2][@att="2"]']:
            check(selector, '<el2 att="2"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"/>
     <el1 att="second"/>
     <!-- comment -->
     <el2 att="first"/><el2 att="2"/>
    </root>""")

        check('/root/*[2][@att="2"]', '<el2 att="2"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"/><el2 att="2"/>
     <el1 att="second"/>
     <!-- comment -->
     <el2 att="first"/>
    </root>""")

        check('/root/el2[1][@att="2"]', '<el2 att="2"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"/>
     <el1 att="second"/>
     <!-- comment -->
     <el2 att="2"/><el2 att="first"/>
    </root>""")

        # Not RFC-compliant, because xcap_put_element doesn't look inside
        # new element. To make it RFC-compliant, fix the selector, replacing
        # '*' with 'el2'
        check('/root/*[@att="2"]', '<el2 att="2"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"/>
     <el1 att="second"/>
     <!-- comment -->
     <el2 att="first"/>
    <el2 att="2"/></root>""")

        # spaces can be inserted along with element (but not comments)
        check('/root/el2[1][@att="2"]', ' <el2 att="2"/> ', '''<?xml version="1.0"?>
    <root>
     <el1 att="first"/>
     <el1 att="second"/>
     <!-- comment -->
      <el2 att="2"/> <el2 att="first"/>
    </root>''')

    source3 = """<?xml version="1.0"?>
    <root>
     <el1 att="first"></el1>
     <el1 att="second"></el1>
     <!-- comment -->
     <el2 att="first"></el2>
    </root>"""

    @classmethod
    def test_put2(cls):
        "the same as before, with <tag/> replaced by <tag></tag>"

        def check(insert_pos, what, expected, source=cls.source3):
            return cls.check(insert_pos, what, expected, source)

        for selector in ['/root/el1[@att="third"]',
                         '/root/el1[3][@att="third"]',
                         '/root/*[3][@att="third"]']:
            check(selector, '<el1 att="third"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"></el1>
     <el1 att="second"></el1><el1 att="third"/>
     <!-- comment -->
     <el2 att="first"></el2>
    </root>""")

        check('/root/el3', '<el3 att="first"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"></el1>
     <el1 att="second"></el1>
     <!-- comment -->
     <el2 att="first"></el2>
    <el3 att="first"/></root>""")

        for selector in ['/root/el2[@att="2"]',
                         '/root/el2[2][@att="2"]']:
            check(selector, '<el2 att="2"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"></el1>
     <el1 att="second"></el1>
     <!-- comment -->
     <el2 att="first"></el2><el2 att="2"/>
    </root>""")

        check('/root/*[2][@att="2"]', '<el2 att="2"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"></el1><el2 att="2"/>
     <el1 att="second"></el1>
     <!-- comment -->
     <el2 att="first"></el2>
    </root>""")

        check('/root/el2[1][@att="2"]', '<el2 att="2"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"></el1>
     <el1 att="second"></el1>
     <!-- comment -->
     <el2 att="2"/><el2 att="first"></el2>
    </root>""")

        # NOTE: depending on what `star' is, 'el1', 'el2' or something else it should
        # be put in a different position (right after the latest <el1>, right after <el2>,
        # or before </root> correspondingly)
        # Such element selectors therefore, should be fixed: replace star with the actual
        # element name (take it from the body of XCAP request).
        # Beware though, that if you do that, you still must guarantee that [@att="2"]
        # doesn't match any of the existing elements, no matter what their names are.
        # This suggests 2-pass procedure for PUT:
        # First try to match element using the original element selector.
        # If it did match, run replacement procedure.
        # If it didn't match, fix the element selector and try to locate insertion point.
        # This will guarantee, that when if client uses non-fixed request next time,
        # it will match exactly once
        check('/root/*[@att="2"]', '<el2 att="2"/>', """<?xml version="1.0"?>
    <root>
     <el1 att="first"></el1>
     <el1 att="second"></el1>
     <!-- comment -->
     <el2 att="first"></el2>
    <el2 att="2"/></root>""")

if __name__ == "__main__":
    from lxml import etree
    import traceback
    _test.test_get()
    _test.test_put0()
    _test.test_put1()
    _test.test_put2()
