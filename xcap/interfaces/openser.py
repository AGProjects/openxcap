# Copyright (C) 2007 AG Projects.
#

"""The OpenSER Management Interface"""

from twisted.web import xmlrpc

from application.python.util import Singleton

class ManagementInterface(object):
    __metaclass__ = Singleton

    def __init__(self, url):
        self.proxy = xmlrpc.Proxy(url + '/RPC2')

    def notify_watchers(self, id, type=0):
        """Instruct OpenSER to NOTIFY all the watchers of this presentity.
           @type can be 0 to signal presence rules changes, or 1 for static PIDF changes."""
        d = self.proxy.callRemote('refreshWatchers', 'sip:' + id, 'presence', type)
        return d
