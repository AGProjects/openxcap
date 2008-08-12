"""Test script for web access

  Usage:

    script.py OPTIONS ACTION APPLICATION

  ACTION is one of GET/PUT/DELETE
  when action is PUT, resource is expected on stdin
  type 'script.py -h' to see the options.
"""

import sys
from optparse import OptionParser
from common import XCAPSettings, XCAPClient

def main():
    settings = XCAPSettings()
    script = XCAPClient(settings)

    try:
        assert len(settings.args)==2, len(settings.args)
        cmd = getattr(script, settings.args[0].lower())
    except (AttributeError, IndexError, AssertionError):
        sys.exit(__doc__)

    if cmd == script.put:
        resource = sys.stdin.read()
        settings.args.append(resource)

    result = cmd(*settings.args[1:])
    sys.stderr.write('%s\n' % result.url)
    sys.stderr.write('%s %s\n' % (result.code, result.msg))
    sys.stderr.write('%s\n' % result.headers)
    if 200 <= result.code <= 200:
        if result.body:
            sys.stdout.write(result.body)
    else:
        sys.stderr.write('%s\n' % result.body)
        sys.exit(1)

if __name__=='__main__':
    main()
