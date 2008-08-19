#!/usr/bin/env python
"""This test will
 1) SUBSCRIBE to xcap-diff event
 2) read NOTIFY if any
 3) delete the document, just in case
 3) put a new document, remember ETag
 4) read NOTIFY with that document url and new_etag=ETag
 5) update the document, remember ETag
 6) read NOTIFY with that document url, new_etag=ETag, old_etag=previous ETag 
 7) delete the document
 8) read NOTIFY with that document url, old_etag=ETag, new_etag=Empty
"""

import re
import time
import unittest
from Queue import Queue, Empty
from optparse import OptionParser, OptionValueError

from common import *

import simport; simport.setup()
from pypjua import *
from xcap.xcapdiff import xml_document, xml_xcapdiff
simport.restore()


expires=20
event='xcap-diff'
content_type='application/xcap-diff+xml'
resource = 'resource-lists'
body = """<?xml version="1.0" encoding="UTF-8"?>
   <resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <list name="friends">
     <entry uri="sip:bill@example.com">
      <display-name>Bill Doe</display-name>
     </entry>
     <entry-ref ref="resource-lists/users/sip:bill@example.com/index/~~/resource-lists/list%5b@name=%22list1%22%5d/entry%5b@uri=%22sip:petri@example.com%22%5d"/>
     <list name="close-friends">
      <display-name>Close Friends</display-name>
      <entry uri="sip:joe@example.com">
       <display-name>Joe Smith</display-name>
      </entry>
      <entry uri="sip:nancy@example.com">
       <display-name>Nancy Gross</display-name>
      </entry>
      <external anchor="http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list%5b@name=%22mkting%22%5d">
        <display-name>Marketing</display-name>
       </external>
     </list>
    </list>
   </resource-lists>
"""


def get_xcapdiff(xcap_root, resource, username, old_etag, new_etag):
    uri = xcap_root + '/' + resource + '/users/' + username + '/index.xml'
    return xml_xcapdiff(xcap_root, xml_document(uri, old_etag, new_etag))

queue = Queue()
packet_count = 0
start_time = None
is_subscribed = False

def event_handler(event_name, **kwargs):
    global start_time, packet_count, is_subscribed
    if event_name == "Subscription_state":
        if kwargs["state"] == "ACTIVE":
            is_subscribed = True
        #elif kwargs["state"] == "TERMINATED":
        #    if kwargs.has_key("code"):
        #        print "Unsubscribed: %(code)d %(reason)s" % kwargs
        #    else:
        #        print "Unsubscribed"
    elif event_name == "Subscription_notify":
        queue.put(("NOTIFY", kwargs))
    elif event_name == "siptrace":
        if start_time is None:
            start_time = kwargs["timestamp"]
        packet_count += 1
        if kwargs["received"]:
            direction = "RECEIVED"
        else:
            direction = "SENDING"
        print "%s: Packet %d, +%s" % (direction, packet_count, (kwargs["timestamp"] - start_time))
        print "%(timestamp)s: %(source_ip)s:%(source_port)d --> %(destination_ip)s:%(destination_port)d" % kwargs
        print kwargs["data"]
    elif event_name=='log':
        pass
    else:
        print 'UNHANDLED EVENT', event_name, kwargs


def get(queue, blocking=True, timeout=1):
    try:
        return queue.get(blocking, timeout)
    except Empty:
        return None

class Test(XCAPTest):

    def assertContains(self, element, list):
        if element not in list:
            raise self.failureException("%s not in %s" % (element, list))

    @classmethod
    def setupOptionParser(_cls, parser):
        parser.set_defaults(outbound_proxy='127.0.0.1', proxy_ip='127.0.0.1', proxy_port=5060)
        parser.add_option("-p", "--outbound-proxy", type="string", action="callback",
                          callback=parse_proxy_cb,
                          help="Outbound SIP proxy to use. By default a lookup is performed based on SRV and A records.",
                          metavar="IP[:PORT]")
        parser.add_option("-t", "--siptrace", default=False, action='store_true')
        XCAPClient.setupOptionParser(parser)

    def test(self):
        opts = self.options

        self.delete(resource, status=[200,404])

        username, domain = opts.username.split('@')

        initial_events = Engine.init_options_defaults["initial_events"]
        if content_type is not None:
            initial_events[event] = [content_type]

        e = Engine(event_handler, do_siptrace=opts.siptrace, auto_sound=False, initial_events=initial_events)
        e.start()
       
        try:
           
            if opts.outbound_proxy is None:
                route = None
            else:
                route = Route(opts.proxy_ip, opts.proxy_port)
            sub = Subscription(Credentials(SIPURI(user=username, host=domain), opts.password),
                               SIPURI(user=username, host=domain), event, route=route, expires=expires)
            sub.subscribe()

            try:

                # wait for SUBSCRIBE to succeed AND absorb out-of-date NOTIFYs
                end = time.time() + 1.5

                while time.time() < end:
                    get(queue, timeout=0.1)
                self.failUnless(is_subscribed, 'SUBSCRIBE failed')

    #             try:
    #                 X = queue.get(True, timeout = 1)
    #             except Empty:
    #                 pass
    #             else:
    #                 self.assertEqual(X[0], 'NOTIFY')

                def get_notify(comment = ''):
                    try:
                        X = queue.get(True, timeout = 1)
                    except Empty:
                        self.fail("Didn't get a NOTIFY %s" % comment)
                    self.assertEqual(X[0], 'NOTIFY')
                    return X[1]

                r = self.put(resource, body)
                etag = r.headers['ETag'].strip('"')
                X = get_notify('after put')

                xcap_root = opts.xcap_root.replace(':8000', '')
                self.assertEqual(X['body'], get_xcapdiff(xcap_root, resource, opts.username, None, etag))
                #print etag

                r = self.put(resource, body.replace('Close', 'Intimate'))
                new_etag = r.headers['ETag'].strip('"')
                X = get_notify()
                self.assertEqual(X['body'], get_xcapdiff(xcap_root, resource, opts.username, etag, new_etag))
                #print etag, new_etag

                r = self.delete(resource)
                X = get_notify()
                self.assertEqual(X['body'], get_xcapdiff(xcap_root, resource, opts.username, new_etag, None))
                #print new_etag, None

            finally:
                sub.unsubscribe()
                time.sleep(2)

        finally:
            e.stop()

re_ip_port = re.compile("^(?P<proxy_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:(?P<proxy_port>\d+))?$")
def parse_proxy(value, parser):
    match = re_ip_port.match(value)
    if match is None:
        raise OptionValueError("Could not parse supplied outbound proxy address")
    parser.values.proxy_ip = match.group('proxy_ip')
    parser.values.proxy_port = int(match.group('proxy_port') or '5060')

def parse_proxy_cb(_option, _opt_str, value, parser):
    return parse_proxy(value, parser)

if __name__ == '__main__':
    runSuiteFromModule()
