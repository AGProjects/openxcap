
# Copyright (C) 2007-2010 AG-Projects.
#

from xcap.appusage import ApplicationUsage
from xcap.appusage.resourcelists import ResourceListsApplication

class RLSServicesApplication(ApplicationUsage):
    ## RFC 4826
    id = "rls-services"
    default_ns = "urn:ietf:params:xml:ns:rls-services"
    mime_type= "application/rls-services+xml"
    schema_file = 'rls-services.xsd'

    def _check_additional_constraints(self, xml_doc):
        """Check additional constraints (see section 3.4.5 of RFC 4826)."""
        ResourceListsApplication.check_list(xml_doc.getroot(), "{%s}list" % self.default_ns)



