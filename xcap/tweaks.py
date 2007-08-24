import md5

from twisted.cred import credentials
from twisted.web2.auth.digest import IUsernameDigestHash

from zope.interface import implements, Interface

class BasicCredentials(credentials.UsernamePassword):
    """Custom Basic Credentials, which support both plain and hashed checks."""

    implements(credentials.IUsernamePassword, IUsernameDigestHash)

    def __init__(self, username, password, realm):
        self.username = username
        self.password = password
        self.realm = realm

    def checkHash(self, digestHash):
        s = '%s:%s:%s' % (self.username, self.realm, self.password)
        return digestHash == md5.new(s).hexdigest()


def decode(self, response, request):
    try:
        creds = (response + '===').decode('base64')
    except:
        raise error.LoginFailed('Invalid credentials')

    creds = creds.split(':', 1)
    if len(creds) == 2:
        creds = BasicCredentials(creds[0], creds[1], self.realm) # our change
        return creds
    else:
        raise error.LoginFailed('Invalid credentials')

## Now we tweak what we need

import new
from twisted.web2.auth.basic import BasicCredentialFactory

method = new.instancemethod(decode, None, BasicCredentialFactory)
setattr(BasicCredentialFactory, 'decode', method)
