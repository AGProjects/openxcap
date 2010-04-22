
# Copyright (C) 2007-2010 AG-Projects.
#

from xcap.appusage import ApplicationUsage

class TestApplication(ApplicationUsage):
    "Application for tests described in Section 8.2.3. Creation of RFC 4825"
    id = "test-app"
    default_ns = 'test-app'
    mime_type= "application/test-app+xml"
    schema_file = None


