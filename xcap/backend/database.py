from typing import Any, Callable, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select

from xcap.backend import BackendInterface, StatusResponse
from xcap.db.manager import get_auth_db_session, get_db_session, shutdown_db
from xcap.db.models import XCAP, Subscriber, Watcher
from xcap.dbutil import make_random_etag
from xcap.uri import XCAPUri


class Error(Exception):
    def __init__(self):
        if hasattr(self, 'msg'):
            return Exception.__init__(self, self.msg)
        else:
            return Exception.__init__(self)


class MultipleResultsError(Error):
    """This should never happen. If it did happen. that means either the table
    was corrupted or there's a logic error"""

    def __init__(self, params):
        Exception.__init__(self, 'database request has more than one result: ' + repr(params))


class DeleteFailed(Error):
    msg = 'DELETE request failed'


class PasswordChecker(object):
    async def query_user(self, credentials) -> Any:
        async with get_auth_db_session() as db_session:
            result = await db_session.execute(select(Subscriber).where(
                Subscriber.username == credentials.username, Subscriber.domain == credentials.realm))
            return result.first()


class DatabaseStorage(BackendInterface):
    app_mapping = {"pres-rules"                             : 1 << 1,
                   "resource-lists"                         : 1 << 2,
                   "rls-services"                           : 1 << 3,
                   "pidf-manipulation"                      : 1 << 4,
                   "org.openmobilealliance.pres-rules"      : 1 << 5,
                   "org.openmobilealliance.pres-content"    : 1 << 6,
                   "org.openxcap.dialog-rules"              : 1 << 7,
                   "test-app"                               : 0}

    async def fetch_document(self, uri):
        username, domain = uri.user.username, uri.user.domain
        self._normalize_document_path(uri)
        doc_type = self.app_mapping[uri.application_id]
        document_path = uri.doc_selector.document_path

        async with get_db_session() as db_session:
            result = await db_session.execute(select(XCAP).where(
                XCAP.username == username,
                XCAP.domain == domain, XCAP.doc_type == doc_type,
                XCAP.doc_uri == document_path))
            results = result.all()
            if results and len(results) > 1:
                raise MultipleResultsError({"username": username,
                                            "domain": domain,
                                            "doc_type": doc_type,
                                            "document_path": document_path})
            return results

    async def get_document(self, uri: XCAPUri, check_etag: Callable) -> Optional[StatusResponse]:
        results = await self.fetch_document(uri)
        if results:
            doc = results[0][0].doc
            etag = results[0][0].etag

            if isinstance(doc, str):
                doc = doc.encode('utf-8')
            check_etag(etag)

            return StatusResponse(200, etag, doc)

        return StatusResponse(404)

    async def put_document(self, uri: XCAPUri, document: bytes, check_etag: Callable) -> Optional[StatusResponse]:
        results = await self.fetch_document(uri)
        if results:
            existing_doc = results[0][0]
            old_etag = existing_doc.etag
            doc = existing_doc.doc

            if isinstance(doc, str):
                doc = doc.encode('utf-8')

            if doc == document:
                return StatusResponse(200, old_etag, doc)

            check_etag(old_etag)  # Check if etag matches
            etag = make_random_etag(uri)  # Generate a new etag
            old_data = existing_doc

            # Update fields
            params = {
                "doc": document,
                "etag": etag
            }
            for key, value in params.items():
                setattr(old_data, key, value)

            async with get_db_session() as db_session:
                db_session.add(old_data)
                await db_session.commit()
                await db_session.refresh(old_data)

            return StatusResponse(200, etag, old_etag=old_etag)

        # If no document exists, create a new one
        username, domain = uri.user.username, uri.user.domain
        doc_type = self.app_mapping[uri.application_id]
        document_path = uri.doc_selector.document_path

        check_etag(None, False)
        etag = make_random_etag(uri)  # Generate a new etag for the new document
        params = {
            "username": username,
            "domain": domain,
            "doc_type": doc_type,
            "etag": etag,
            "doc": document,
            "doc_uri": document_path
        }
        new_doc = XCAP(**params)
        async with get_db_session() as db_session:
            db_session.add(new_doc)
            await db_session.commit()
            await db_session.refresh(new_doc)

        return StatusResponse(201, etag)

    async def delete_document(self, uri: XCAPUri, check_etag: Callable) -> Optional[StatusResponse]:
        results = await self.fetch_document(uri)

        if results:
            etag = results[0][0].etag
            check_etag(etag)
            async with get_db_session() as db_session:
                try:
                    await db_session.delete(results[0][0])
                    await db_session.commit()
                except SQLAlchemyError:
                    raise DeleteFailed

            return StatusResponse(200, old_etag=etag)
        return StatusResponse(404)

    async def get_watchers(self, uri):
        status_mapping = {1: "allow",
                          2: "confirm",
                          3: "deny"}
        presentity_uri = "sip:%s@%s" % (uri.user.username, uri.user.domain)

        async with get_db_session() as db_session:
            result = await db_session.execute(select(Watcher).where(
                Watcher.presentity_uri == presentity_uri))
            result_list = result.all()

            watchers = [{"id": "%s@%s" % (w_user, w_domain),
                         "status": status_mapping.get(subs_status, "unknown"),
                         "online": "false"} for w_user, w_domain, subs_status in result_list]

            result = await db_session.execute(select(Watcher).where(
                Watcher.presentity_uri == presentity_uri, Watcher.event == 'presence'))
            result_list = result.all()
            active_watchers = set("%s@%s" % pair for pair in result)
            for watcher in watchers:
                if watcher["id"] in active_watchers:
                    watcher["online"] = "true"
            return watchers

    def stop(self):
        shutdown_db()


Storage = DatabaseStorage
