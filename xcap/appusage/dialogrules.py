
# Copyright (C) 2007-2010 AG-Projects.
#

from xcap.appusage import ApplicationUsage

class DialogRulesApplication(ApplicationUsage):
    id = "dialog-rules"
    default_ns = "urn:ietf:params:xml:ns:dialog-rules"
    mime_type = "application/auth-policy+xml"
    schema_file = 'common-policy.xsd'


