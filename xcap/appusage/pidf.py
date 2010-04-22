
# Copyright (C) 2007-2010 AG-Projects.
#

from xcap.appusage import ApplicationUsage

class PIDFManipulationApplication(ApplicationUsage):
    ## RFC 4827
    id = "pidf-manipulation"
    default_ns = "urn:ietf:params:xml:ns:pidf"
    mime_type= "application/pidf+xml"
    schema_file = 'pidf.xsd'


