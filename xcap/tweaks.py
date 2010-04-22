
# Copyright (C) 2007-2010 AG-Projects.
#

from hashlib import md5
from twisted.cred import credentials, error
from twisted.web2.auth.digest import IUsernameDigestHash, DigestCredentialFactory

from zope.interface import implements

def makeHash(username, realm, password):
    s = '%s:%s:%s' % (username, realm, password)
    return md5(s).hexdigest()

class BasicCredentials(credentials.UsernamePassword):
    """Custom Basic Credentials, which support both plain and hashed checks."""

    implements(credentials.IUsernamePassword, IUsernameDigestHash)

    def __init__(self, username, password, realm):
        self.username = username
        self.password = password
        self.realm = realm

    def checkHash(self, digestHash):
        return digestHash == makeHash(self.username, self.realm, self.password)


def decode(self, response, request):
    try:
        creds = (response + '===').decode('base64')
    except Exception:
        raise error.LoginFailed('Invalid credentials')

    creds = creds.split(':', 1)
    if len(creds) == 2:
        creds = BasicCredentials(creds[0], creds[1], self.realm) # our change
        return creds
    else:
        raise error.LoginFailed('Invalid credentials')

def tweak_BasicCredentialFactory():
    import new
    from twisted.web2.auth.basic import BasicCredentialFactory
    method = new.instancemethod(decode, None, BasicCredentialFactory)
    BasicCredentialFactory.decode = method

class tweak_DigestCredentialFactory(DigestCredentialFactory):

    def generateOpaque(self, nonce, clientip):
        """ 
        Generate an opaque to be returned to the client.  This is a unique
        string that can be returned to us and verified.
        """
        # Now, what we do is encode the nonce, client ip and a timestamp in the
        # opaque value with a suitable digest.
        now = str(int(self._getTime()))
        if clientip is None:
            clientip = ''
        key = "%s,%s,%s" % (nonce, clientip, now)
        digest = md5(key + self.privateKey).hexdigest()
        ekey = key.encode('base64')
        return "%s-%s" % (digest, ekey.replace('\n', ''))

