# Copyright (C) 2007 AG Projects.
#

"""The OpenSER Management Interface"""

from twisted.web import xmlrpc

from application.configuration import readSettings, ConfigSection
from application.python.util import Singleton

class OpenSERConfig(ConfigSection):
    xmlrpc_url = 'http://localhost:8080'

## We use this to overwrite some of the settings above on a local basis if needed
readSettings('OpenSER', OpenSERConfig)

class ManagementInterface(object):
    __metaclass__ = Singleton

    def __init__(self):
        self.proxy = xmlrpc.Proxy(OpenSERConfig.xmlrpc_url + '/RPC2')

    def notify_watchers(self, id):
        d = self.proxy.callRemote('refreshWatchers', 'sip:' + id, 'presence' )
        return d
