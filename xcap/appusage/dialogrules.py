
# Copyright (C) 2007-2010 AG-Projects.
#

from xcap.appusage import ApplicationUsage

class DialogRulesApplication(ApplicationUsage):
    id = "org.openxcap.dialog-rules"
    default_ns = "http://openxcap.org/ns/dialog-rules"
    mime_type = "application/auth-policy+xml"
    schema_file = 'common-policy.xsd'


