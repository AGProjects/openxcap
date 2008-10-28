import os
import re
from subprocess import Popen, PIPE
from xcaplib.httpclient import HTTPResponse

DEBUG = 0

def make_client(options):
    return XCAPClient(options.xcap_root, options.sip_address, options.password)

class XCAPClient(object):
    """Wrapper of command-line utility xcapclient.

    Pointless, unless you want to test xcapclient itself.
    """

    XCAPCLIENT = '/home/denis/work/python-xcaplib/xcapclient'

    def __init__(self, xcap_root, sip_address, password):
        self.params = ['--xcap-root', xcap_root, '--sip-address', sip_address, '--password', password]

    def get_params(self, etag=None, globaltree=False, filename=None, headers=None):
        params = self.params[:]
        if etag is not None:
            params += ['--etag', etag]
        if globaltree:
            params += ['-c', 'global']
        else:
            params += ['-c', 'users']
        if filename is not None:
            params += ['--filename', filename]
        for k, v in (headers or {}).iteritems():
            if v is None:
                params += ['--add-header', k]
            else:
                params += ['--add-header', '%s:%s' % (k, v)]
        return params

    def request(self, method, application, input=None, node=None, **params):
        params = ['--app', application] + self.get_params(**params)
        params.append(method)
        if node is not None:
            if node[:1]!='/':
                node = '/' + node
            params.append(node)
        return self._run(params, input)

    def _get(self, application, node=None, **params):
        return self.request('get', application, node=node, **params)

    def _put(self, application, resource, node=None, **params):
        return self.request('put', application, input=resource, node=node, **params)

    def _delete(self, application, node=None, **params):
        return self.request('delete', application, node=node, **params)

    def _run(self, params, input=None):
        params = [self.XCAPCLIENT] + params
        p = Popen(params, stdin=input and PIPE, stdout=PIPE, stderr=PIPE, env=os.environ)
        (stdout, stderr) = p.communicate(input=input)
        if DEBUG:
            print '\n______________'
            print stdout
            print '--------------'
            print stderr
            print '^^^^^^^^^^^^^^'
        code, comment, etag, content_type = parse_stderr(stderr)

        hdrs = headers()

        if p.wait() == 0:
            if code is None:
                code, comment = 200, 'OK'
        else:
            assert code is not None, `stderr`
            assert comment is not None, `stderr`

        if etag is not None:
            hdrs['ETag'] = etag
        if content_type is not None:
            hdrs['Content-Type'] = content_type

        return HTTPResponse(None, code, comment, hdrs, stdout)

class headers(dict):
    def gettype(self):
        typ = self.get('Content-Type')
        if typ is None:
            return typ
        return typ.split(';', 1)[0]

re_status_line = re.compile("^(\d\d\d) (.*?)$", re.M)
re_etag = re.compile('^etag: (".*?")$', re.M | re.I)
re_content_type = re.compile("^content-type: (.*?)$", re.M | re.I)

def findone(re, str):
    m = re.findall(str)
    assert len(m)<=1, (m, str)
    if not m:
        return None
    elif len(m)==1:
        return m[0]

def parse_stderr(stderr):
    """
    >>> parse_stderr('''url: https://10.1.1.3/xcap-root/resource-lists/listxx
    ... 404 Not Found
    ... content-length: 121
    ... ''')
    (404, 'Not Found', None, None)

    >>> parse_stderr('''url: https://10.1.1.3/xcap-root/resource-lists/users/alice@example
    ... etag: "5342d9c443c7fad5d76669c7253688f0"
    ... content-length: 1829
    ... ''')
    (None, None, '"5342d9c443c7fad5d76669c7253688f0"', None)

    >>> parse_stderr('url: https://10.1.1.3/xcap-root/xcap-caps/global/index\\netag: "6fc08e7c18116bb145c7052fc9a2d6bf"\\ncontent-length: 826\\n\\n')
    (None, None, '"6fc08e7c18116bb145c7052fc9a2d6bf"', None)
    """
    m = findone(re_status_line, stderr)
    if m is None:
        code, comment = None, None
    else:
        code, comment = m
        code = int(code)
    etag = findone(re_etag, stderr)
    content_type = findone(re_content_type, stderr)
    return code, comment, etag, content_type

if __name__=='__main__':
    import doctest
    doctest.testmod()
