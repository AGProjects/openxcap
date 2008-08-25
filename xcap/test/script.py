#!/usr/bin/env python
"""Test script for web access

  Usage:

    script.py OPTIONS ACTION APPLICATION NODE

  ACTION is one of GET/PUT/DELETE
  when action is PUT, resource is expected on stdin
  type 'script.py -h' to see the options.
"""

import sys
from optparse import OptionParser
from common import *

class MyDebugOutput(DebugOutput):
    def log_trans(self, req, result):
        if self.level==0:
            if not result.succeed:
                self.log_result_code(result)
                self.log_result_body(result)
            else:
                self.log_etag(result)
        if self.level==1:
            self.log_method_url(req)
            self.log_result_code(result)
            self.log_etag(result)
        elif self.level==2:
            self.log_method_url(req)
            self.log_req_headers(req)
            self.log_result_code(result)           
            self.log_result_headers(result)
        elif self.level>=3:
            self.log_method_url(req)
            self.log_req_headers(req)
            self.log_req_body(req)
            self.log_result_code(result)           
            self.log_result_headers(result)
            # and body will be printed to stdout

XCAPClient.DebugOutput = MyDebugOutput

def main():
    parser = OptionParser(conflict_handler='resolve')
    XCAPClient.setupOptionParser(parser)
    client = XCAPClient()
    options, args = parser.parse_args()
    client.initialize(options, args)

    try:
        cmd = getattr(client, args[0].lower())
    except AttributeError:
        sys.exit(__doc__ + '\nInvalid action\n')
    except IndexError:
        sys.exit(__doc__)

    if cmd == client.put:
        resource = sys.stdin.read()
        headers = {'Content-type' : 'application/xcap-el+xml'}
    else:
        resource = None
        headers = {}

    if len(args)==2:
        application = args[1]
        node = None
    else:
        application, node = args[1:]

    if cmd in [client.get, client.delete]:
        result = cmd(application, node)
    elif cmd == client.put:
        result = client.put(application, resource, node, headers)
    else:
        wtf

    if 200 <= result.code <= 200:
        if result.body:
            sys.stdout.write(result.body)
    else:
        sys.stderr.write(result.body)
        sys.exit(1)

if __name__=='__main__':
    main()
