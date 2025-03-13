
"""Database utilities"""

import random
import time
from hashlib import md5


def make_random_etag(uri):
    to_hash = "%s%s%s" % (uri, time.time(), random.random())
    return md5(to_hash.encode('utf-8')).hexdigest()


def make_etag(uri, document):
    combined_string = f"{uri}{document}".encode('utf-8')
    return md5(combined_string).hexdigest()

