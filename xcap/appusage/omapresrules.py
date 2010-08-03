
# Copyright (C) 2007-2010 AG-Projects.
#

from xcap.appusage import ApplicationUsage

class OMAPresenceRulesApplication(ApplicationUsage):
    id = "pres-rules"
    default_ns = "urn:ietf:params:xml:ns:pres-rules"
    mime_type = "application/auth-policy+xml"
    schema_file = 'presence-rules.xsd'


