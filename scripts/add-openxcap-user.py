import sys
import md5
username, domain, password = sys.argv[1:]
hash = md5.new(":".join([username, domain, password])).hexdigest()
query = """INSERT INTO subscriber (username, domain, password, ha1) VALUES ("%(username)s", "%(domain)s", "%(password)s", "%(hash)s");""" % locals()
print query