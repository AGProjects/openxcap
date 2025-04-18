#!/usr/bin/env python3

"""This is an example that shows how a new user could be added to
`subscriber' table. It does NOT actually create a new record in
the database.
"""

import sys
from hashlib import md5

print(__doc__)

try:
    username, domain, password = sys.argv[1:]
except ValueError:
    sys.exit('USAGE: %s username domain password' % sys.argv[0])
hash = md5(":".join([username, domain, password]).encode('utf-8')).hexdigest()
query = """INSERT INTO subscriber (username, domain, password, ha1) VALUES ("%(username)s", "%(domain)s", "%(password)s", "%(hash)s");""" % locals()
print(query)
