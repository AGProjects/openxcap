# Copyright (C) 2007 AG-Projects.
#

"""Implementation of an OpenSER database storage"""

import time
from StringIO import StringIO
from lxml import etree

from twisted.enterprise import adbapi, util as dbutil
from twisted.internet import defer

from application.configuration import readSettings, ConfigSection
from application import log

from xcap.interfaces.backend import database
from xcap.interfaces.openser import ManagementInterface
from xcap.errors import ResourceNotFound

class StorageConfig(ConfigSection):
    db_uri = 'mysql://user:pass@db/openser'

## We use this to overwrite some of the settings above on a local basis if needed
readSettings('Storage', StorageConfig)

class Storage(database.Storage):

    def __init__(self):
        database.Storage.__init__(self)
        self._mi = ManagementInterface()

    def _get_watchers_from_database(self, trans, user):
        quote = dbutil.quote
        query = """SELECT w_user, w_domain, subs_status FROM watchers
                   WHERE p_user = %(username)s AND p_domain = %(domain)s""" % {
                       "username": quote(user.username, "char"),
                       "domain"  : quote(user.domain, "char")}
        trans.execute(query)
        result = trans.fetchall()
        active_watchers = [(r[0], r[1]) for r in result if r[2] == 'active']
        terminated_watchers = [(r[0], r[1]) for r in result if r[2] == 'terminated']
        return {'active': active_watchers, 'terminated': terminated_watchers}

    def _get_policy_from_xml(self, document):
        ## get the allow/block policy rules from the XCAP document
        xml_doc = etree.parse(StringIO(document))
        ns_dict = {"pr": "urn:ietf:params:xml:ns:pres-rules","cp": "urn:ietf:params:xml:ns:common-policy"}
        ## allowed watchers
        # TODO maybe use xpath evaluator?
        one = xml_doc.xpath("/cp:ruleset/cp:rule[cp:actions/pr:sub-handling='allow']/cp:conditions/cp:identity/cp:one", ns_dict)
        many = xml_doc.xpath("/cp:ruleset/cp:rule[cp:actions/pr:sub-handling='allow']/cp:conditions/cp:identity/cp:many", ns_dict)
        allowed_users = [w.attrib['id'].strip("sip:") for w in one]
        allowed_domains = [w.get('domain', '') for w in many]
        allow = {'users': allowed_users, 'domains': allowed_domains}
        ## blocked watchers
        one = xml_doc.xpath("/cp:ruleset/cp:rule[cp:actions/pr:sub-handling='block']/cp:conditions/cp:identity/cp:one", ns_dict)
        many = xml_doc.xpath("/cp:ruleset/cp:rule[cp:actions/pr:sub-handling='block']/cp:conditions/cp:identity/cp:many", ns_dict)
        blocked_users = [w.attrib['id'].strip("sip:") for w in one]
        blocked_domains = [w.get('domain', '') for w in many]
        block = {'users': blocked_users, 'domains': blocked_domains}
        return {'allow': allow, 'block': block}

    def _update_allowed_watchers(self, trans, user, db_watchers, auth_policy):
        allow = auth_policy['allow']
        to_delete = []
        to_add = []
        for w in db_watchers['active']:
            username, domain = w
            if '%s@%s' % (username, domain) not in allow['users'] and domain not in allow['domains']:
                to_delete.append(w)
        for w in allow['users']:
            u = tuple(w.split('@', 1))
            if u not in db_watchers['active']:
                to_add.append(u)
        quote = dbutil.quote
        for w in to_delete:
            w_username, w_domain = w
            query = """DELETE FROM watchers
                       WHERE p_user = %(username)s AND p_domain = %(domain)s
                       AND w_user = %(w_username)s AND w_domain = %(w_domain)s""" % {
                           "username": quote(user.username, "char"),
                           "domain"  : quote(user.domain, "char"),
                           "w_username": quote(w_username, "char"),
                           "w_domain": quote(w_domain, "char"),
                           }
            trans.execute(query)
            query = """UPDATE active_watchers
                       SET status = %(subs_status)s
                       WHERE pres_user = %(username)s AND pres_domain = %(domain)s
                       AND from_user = %(w_username)s AND from_domain = %(w_domain)s""" % {
                           "subs_status": quote("terminated", "char"),
                           "username": quote(user.username, "char"),
                           "domain"  : quote(user.domain, "char"),
                           "w_username": quote(w_username, "char"),
                           "w_domain": quote(w_domain, "char"),
                           }
            trans.execute(query)
        for w in to_add:
            w_username, w_domain = w
            query = """INSERT INTO watchers
                       (p_user, p_domain, w_user, w_domain, subs_status, inserted_time)
                       VALUES (%(username)s, %(domain)s, %(w_username)s, %(w_domain)s, %(subs_status)s, %(time)s)""" % {
                           "username": quote(user.username, "char"),
                           "domain"  : quote(user.domain, "char"),
                           "w_username": quote(w_username, "char"),
                           "w_domain": quote(w_domain, "char"),
                           "subs_status": quote("active", "char"),
                           "time": quote(int(time.time()), "int")
                           }
            try:
                trans.execute(query)
            except Exception, e: ## TODO the watcher existed, but it wasn't set to active
                query = """UPDATE watchers
                           SET subs_status = %(subs_status)s
                           WHERE p_user = %(username)s AND p_domain = %(domain)s
                           AND w_user = %(w_username)s AND w_domain = %(w_domain)s""" % {
                               "subs_status": quote("active", "char"),
                               "username": quote(user.username, "char"),
                               "domain"  : quote(user.domain, "char"),
                               "w_username": quote(w_username, "char"),
                               "w_domain": quote(w_domain, "char")}                
                trans.execute(query)
            
            query = """UPDATE active_watchers
                       SET status = %(subs_status)s
                       WHERE pres_user = %(username)s AND pres_domain = %(domain)s
                       AND from_user = %(w_username)s AND from_domain = %(w_domain)s""" % {
                           "subs_status": quote("active", "char"),
                           "username": quote(user.username, "char"),
                           "domain"  : quote(user.domain, "char"),
                           "w_username": quote(w_username, "char"),
                           "w_domain": quote(w_domain, "char"),
                           }
            trans.execute(query)

    def _update_blocked_watchers(self, trans, user, db_watchers, auth_policy):
        block = auth_policy['block']
        to_delete = []
        to_terminate = []
        ## daca erau intrari terminated in tabel, dar ele nu se afla in blocked, sterge-le
        for w in db_watchers['terminated']:
            username, domain = w
            if '%s@%s' % (username, domain) not in block['users'] and domain not in block['domains']:
                to_delete.append(w)
        for w in block['users']:
            u = tuple(w.split('@', 1))
            if u not in db_watchers['terminated']:
                to_terminate.append(u)
        quote = dbutil.quote
        for w in to_delete:
            w_username, w_domain = w
            query = """DELETE FROM watchers
                       WHERE p_user = %(username)s AND p_domain = %(domain)s
                       AND w_user = %(w_username)s AND w_domain = %(w_domain)s""" % {
                           "username": quote(user.username, "char"),
                           "domain"  : quote(user.domain, "char"),
                           "w_username": quote(w_username, "char"),
                           "w_domain": quote(w_domain, "char"),
                           }
            trans.execute(query)
        for w in to_terminate:
            ## block watcher permanently
            w_username, w_domain = w
            query = """INSERT INTO watchers
                       (p_user, p_domain, w_user, w_domain, subs_status, inserted_time)
                       VALUES (%(username)s, %(domain)s, %(w_username)s, %(w_domain)s, %(subs_status)s, %(time)s)""" % {
                           "username": quote(user.username, "char"),
                           "domain"  : quote(user.domain, "char"),
                           "w_username": quote(w_username, "char"),
                           "w_domain": quote(w_domain, "char"),
                           "subs_status": quote("terminated", "char"),
                           "time": quote(int(time.time()), "int")
                           }
            try:
                trans.execute(query)
            except Exception, e: ## TODO the watcher existed, but it wasn't set to active
                query = """UPDATE watchers
                           SET subs_status = %(subs_status)s
                           WHERE p_user = %(username)s AND p_domain = %(domain)s
                           AND w_user = %(w_username)s AND w_domain = %(w_domain)s""" % {
                               "subs_status": quote("terminated", "char"),
                               "username": quote(user.username, "char"),
                               "domain"  : quote(user.domain, "char"),
                               "w_username": quote(w_username, "char"),
                               "w_domain": quote(w_domain, "char")}                
                trans.execute(query)
            ## block watcher in server memory, let OpenSER purge the active watcher
            query = """UPDATE active_watchers
                       SET status = %(subs_status)s
                       WHERE pres_user = %(username)s AND pres_domain = %(domain)s
                       AND from_user = %(w_username)s AND from_domain = %(w_domain)s""" % {
                           "subs_status": quote("terminated", "char"),
                           "username": quote(user.username, "char"),
                           "domain"  : quote(user.domain, "char"),
                           "w_username": quote(w_username, "char"),
                           "w_domain": quote(w_domain, "char"),
                           }
            trans.execute(query)

    def _merge_watchers(self, trans, uri, document):
        user = uri.user
        db_watchers = self._get_watchers_from_database(trans, uri.user)
        auth_policy = self._get_policy_from_xml(document)
        self._update_allowed_watchers(trans, user, db_watchers, auth_policy)
        self._update_blocked_watchers(trans, user, db_watchers, auth_policy)

    def _put_document(self, trans, uri, document, check_etag):
        response = database.Storage._put_document(self, trans, uri, document, check_etag)
        self._merge_watchers(trans, uri, document)
        return response

    def _notify_watchers(self, response, user_id):
        def _eb_mi(f):
            log.error("Error while notifying OpenSER management interface for 'user' %s: %s" % (user_id, f.getErrorMessage()))
            return response
        d = self._mi.notify_watchers('%s@%s' % (user_id.username, user_id.domain))
        d.addCallback(lambda x: response)
        d.addErrback(_eb_mi)
        return d

    def put_document(self, uri, document, check_etag):
        application_id = uri.application_id
        if application_id in ('pres-rules', 'org.openmobilealliance.pres-rules'):
            ## apply additional insertion logic for these application
            put_handler = self._put_document
        else:
            put_handler = super(Storage, self)._put_document
        d = self.conn.runInteraction(put_handler, uri, document, check_etag)
        if application_id in ('pres-rules', 'org.openmobilealliance.pres-rules', 'pidf-manipulation'):
            ## signal OpenSER of the modification through the management interface
            d.addCallback(self._notify_watchers, uri.user)
        return d
