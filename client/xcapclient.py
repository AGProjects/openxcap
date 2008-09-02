#!/usr/bin/env python
"urllib2-based XCAP client"

import urllib2
from urllib2 import HTTPError, URLError, addinfourl

# Q: where's asynchronous twisted-based client?
# A: Twisted implementation of http client in both twisted-web and twisted-web2
#    packages seems rather incomplete. So, it is easier to implement
#    a client using a nice blocking API, then wrap it in a worker thread and thus get
#    an unblocking one.

AGENT = 'xcapclient.py'

__all__ = ['Resource',
           'Document',
           'Element',
           'AttributeValue',
           'NSBindings',
           'XCAPClient',
           'HTTPError',
           'URLError',
           'addinfourl']

class Resource(str):
    """Result of XCAP GET request: document + etag"""

    def __new__(cls, source, _etag, _content_type=None):
        return str.__new__(cls, source)

    def __init__(self, _source, etag, content_type=None):
        self.etag = etag
        if content_type is not None:
            self.content_type = content_type

    @staticmethod
    def get_class(content_type):
        "For given content-type, return an appropriate subclass of Resource"
        if content_type == Element.content_type:
            return Element
        elif content_type == AttributeValue.content_type:
            return AttributeValue
        elif content_type == NSBindings.content_type:
            return NSBindings
        else:
            return lambda source, etag: Document(source, etag, content_type)

    @staticmethod
    def get_content_type(node):
        "For given node selector, return an appropriate content-type for PUT request"
        if node is None:
            return None
        elif node.endswith('namespace::*'):
            return NSBindings.content_type
        elif node[node.rindex('/'):][:1] == '@':
            return AttributeValue.content_type
        else:
            return Element.content_type

class Document(Resource):
    content_type = None # depends on the application

class Element(Resource):
    content_type = 'application/xcap-el+xml'

class AttributeValue(Resource):
    content_type = 'application/xcap-att+xml'

class NSBindings(Resource):
    content_type = 'application/xcap-ns+xml'


class HTTPRequest(urllib2.Request):
    """Hack urllib2.Request to support PUT and DELETE methods."""
    
    def __init__(self, url, method="GET", data=None, headers={},
                 origin_req_host=None, unverifiable=False):
        urllib2.Request.__init__(self,url,data,headers,origin_req_host,unverifiable)
        self.url = url
        self.method = method
    
    def get_method(self):
        return self.method


# XCAPClient uses HTTPConnectionWrapper-like class for HTTP handling.
# if HTTPConnectionWrapper blocks, XCAPClient should blocks,
# if it's not (returning Deferred), XCAPClient is async as well
# This means XCAPClient doesn't look into results of HTTP resuests.
class HTTPConnectionWrapper(object):

    def __init__(self, base_url, user, password, auth):
        self.base_url = base_url
        if self.base_url[-1:]!='/':
            self.base_url += '/'

        self.username, self.domain = user.split('@')
        self.password = password

        self.authhandler = None
        if password is not None:
            if auth == 'basic':
                self.authhandler = urllib2.HTTPBasicAuthHandler()
            elif auth == "digest":
                self.authhandler = urllib2.HTTPDigestAuthHandler()
            else:
                raise ValueError('Invalid auth: %r' % auth) # if auth==None, password must be also None
            self.authhandler.add_password(self.domain, self.base_url, self.username, password)
            self.opener = urllib2.build_opener(self.authhandler)
        else:
            self.opener = urllib2.build_opener()

    def request(self, method, path, headers=None, data=None):
        if path[:1]=='/':
            path = path[1:]
        if headers==None:
            headers = {}
        url = self.base_url+path
        req = HTTPRequest(url, method=method, headers=headers, data=data)
        try:
            return self.opener.open(req)
            # contrary to what documentation for urllib2 says, this can return addinfourl
            # instead of HTTPError which is though has all the relevant attributes (code, msg etc)
        except HTTPError, e:
            if 200 <= e.code <= 299:
                return e
            raise

    def get(self, path, headers=None, data=None):
        response = self.request('GET', path, headers, data)
        if 200 <= response.code <= 299:
            content_type = response.headers.get('content-type')
            klass = Resource.get_class(content_type)
            etag = response.headers.get('etag')
            return klass(response.read(), etag)
        else:
            raise response


class XCAPClient(object):

    HTTPConnectionWrapper = HTTPConnectionWrapper

    def __init__(self, root, user, password=None, auth='basic', connection=None):
        self.root = root
        if self.root[-1:] == '/':
            self.root = self.root[:-1]
        if user[:-4] == 'sip:':
            user = user[4:]
        self.user = user
        if connection is None:
            self.con = self.HTTPConnectionWrapper(self.root, user, password, auth)
        else:
            self.con = connection

    def get_path(self, application, node):
        path = "/%s/users/%s/index.xml" % (application, self.user)
        if node:
            path += '~~' + node
        return path

    def get_url(self, application, node):
        return (self.root or '') + self.get_path(application, node)

    def get(self, application, node=None):
        path = self.get_path(application, node)
        return self.con.get(path)

    def put(self, application, resource, node=None):
        path = self.get_path(application, node)
        headers = {}
        content_type = Resource.get_content_type(node)
        if content_type:
            headers['Content-Type'] = content_type
        return self.con.request('PUT', path, headers, resource)

    def delete(self, application, node=None):
        path = self.get_path(application, node)
        return self.con.request('DELETE', path)


if __name__ == '__main__':

    root = 'http://127.0.0.1:8000'
    user = 'alice@example.com'
    client = XCAPClient(root, user)

    document = file('resource-lists.xml').read()

    # put the whole document
    client.put('resource-lists', document)

    # get the whole document
    got = client.get('resource-lists')

    # it must be the same
    assert document==got, (document, got)

    # get an element:
    res = client.get('resource-lists', '/resource-lists/list/entry/display-name')
    assert res == '<display-name>Bill Doe</display-name>', res

    # get an attribute:
    res = client.get('resource-lists', '/resource-lists/list/entry/@uri')
    assert res == 'sip:bill@example.com', res

    # put an element
    bob_uri = 'sip:bob@example.com'
    bob = '<entry uri="%s"/>' % bob_uri
    node_selector = '/resource-lists/list/entry[@uri="%s"]' % bob_uri
    res = client.put('resource-lists', bob, node_selector)
    assert res.code == 201, (res.code, res)

    # replace an element
    bob = '<entry uri="%s"><display-name>The Bob</display-name></entry>' % bob_uri
    res = client.put('resource-lists', bob, node_selector)
    assert res.code == 200, (res.code, res)

    # delete an element
    res = client.delete('resource-lists', node_selector)
    assert res.code == 200, (res.code, res)

    # common http errors:
    try:
        res = client.delete('resource-lists', node_selector)
        assert res.code == 200, (res.code, res)
    except HTTPError, e:
        assert e.code == 404, e

    # connection errors:
    client2 = XCAPClient('http://www.fdsdfgh.com:32452', user)
    try:
        client2.get('resource-lists')
        assert False, 'should not get there'
    except URLError:
        pass

    # https and authentication:
    root = 'https://xcap.sipthor.net/xcap-root'
    client3 = XCAPClient(root, 'poc@umts.ro', 'poc', auth='basic')
    watchers = client3.get('watchers')
    assert isinstance(watchers, Document), `watchers`
    assert watchers.content_type == 'application/xml', watchers.content_type
