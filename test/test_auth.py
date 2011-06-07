#!/usr/bin/env python

# Copyright (C) 2007-2010 AG-Projects.
#

from common import *

class AuthTest(XCAPTest):
    
    def test_users_auth(self):
        self.get(self.app, status=[200,404])

        self.options.password += 'x'
        self.update_client_options()
        self.get(self.app, status=[401])

    def test_global_auth(self):
        self.get_global(self.app, status=[200,404])
            
        #self.options.password += 'x'
        #self.update_client_options()
        #for app in apps:
        #    self.get_global(app, status=401)

    # XXX test PUT/DELETE auth as well?
    # XXX test digest authentication
    # XXX test authorization

    #def test_authorization(self):
        ### the request cannot be authorized (we're trying to access someone else' resource)
        #account = self.account
        #self.account = "dummy" + self.account
        #r = self.get('resource-lists', status=401)
        #self.client.account = account

for app in apps:
    exec """class AuthTest_%s(AuthTest):
    app = %r
""" % (app.replace('-', '_').replace('.', '_'), app)

del AuthTest

if __name__ == '__main__':
    runSuiteFromModule()
