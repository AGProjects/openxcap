# Copyright (C) 2007 AG-Projects.
#

"""Interface to the backend subsystem"""

__all__ = ['database', 'openser']

from zope.interface import Interface


class StatusResponse(object):
    def __init__(self, code, etag=None, data=None):
        self.code = code
        self.etag = etag
        self.data = data

class StorageError(Exception): pass


class IStorage(Interface):
    """Storage interface. It defines the methods an XCAP storage class must implement."""

    def get_document(self, uri, check_etag):
        """Fetch an XCAP document.

        @param uri: an XCAP URI that contains the XCAP user and the document selector
        
        @param check_etag: a callable used to check the etag of the stored document

        @returns: a deferred that'll be fired when the document is fetched"""

    def put_document(self, uri, document, check_etag):
        """Insert or replace an XCAP document.
        
        @param uri: an XCAP URI that contains the XCAP user and the document selector
        
        @param document: the XCAP document
        
        @param check_etag: a callable used to check the etag of the stored document
        
        @returns: a deferred that'll be fired when the action was completed."""

    def delete_document(self, uri, check_etag):
        """Delete an XCAP document.
        
        @param uri: an XCAP URI that contains the XCAP user and the document selector
        
        @param check_etag: a callable used to check the etag of the document to be deleted
        """

    def generate_etag(self, uri, document):
        """Generate an etag for the give XCAP URI and document.

        @param uri: an XCAP URI that contains the XCAP user and the document selector

        @param document: an XCAP document
        """
