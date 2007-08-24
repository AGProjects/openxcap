from twisted.cred import credentials

## Redefine 

def decode(self, response, request):
    try:
        creds = (response + '===').decode('base64')
    except:
        raise error.LoginFailed('Invalid credentials')

    creds = creds.split(':', 1)
    if len(creds) == 2:
        creds = credentials.UsernamePassword(*creds)
        creds.realm = self.realm
        return creds
    else:
        raise error.LoginFailed('Invalid credentials')

## Now we tweak what we need

import new
from twisted.web2.auth.basic import BasicCredentialFactory

method = new.instancemethod(decode, None, BasicCredentialFactory)
setattr(BasicCredentialFactory, 'decode', method)
