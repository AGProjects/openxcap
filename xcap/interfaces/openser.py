# Copyright (C) 2007 AG Projects.
#

"""The OpenSER Management Interface"""

from twisted.web import xmlrpc

from application.configuration import readSettings, ConfigSection
from application.python.util import Singleton

class ManagementInterface(object):
    __metaclass__ = Singleton

    def __init__(self, url):
        self.proxy = xmlrpc.Proxy(url + '/RPC2')

    def notify_watchers(self, id):
        d = self.proxy.callRemote('refreshWatchers', 'sip:' + id, 'presence' )
        return d
