
"""XCAP URI module

http://tools.ietf.org/html/rfc4825#section-6

The algorithm to decode the URI is as following:

 * First, percent-decode the whole URI (urllib.unquote)
 * Split document selector from node selector (str.split('~~'))
 * Then use xpath_tokenizer from lxml to parse the whole node selector
   and extract individual steps

Although after doing percent-decoding first, we cannot use s.split('/'),
using lexer from lxml alleviates that fact a bit and produces good results.

A potential problem can arise with URIs that contain [percent-encoded] double quotes.
Here's an example:

/resource-lists/list[@name="friends"]/external[@anchor="/list[@name=%22mkting%22]"]

which would be converted to

/resource-lists/list[@name="friends"]/external[@anchor="/list[@name="mkting"]"]

and that would confuse the parser.

I'm not sure if it's legal to have such URIs, but if it is this module has to be fixed.
Meanwhile, the safe approach is to use &quot;

/resource-lists/list[@name="friends"]/external[@anchor="/list[@name=&quot;mkting&quot;]"]

"""

from typing import Any, Optional, Union
from urllib.parse import unquote

from xcap.configuration.datatypes import XCAPRootURI
from xcap.xpath import DocumentSelector, NodeSelector


class XCAPUser(object):

    def __init__(self, username: Optional[str] = None, domain: Optional[str] = None):
        self.username = username
        self.domain = domain

    @property
    def uri(self) -> str:
        return 'sip:%s@%s' % (self.username, self.domain)

    def __eq__(self, other) -> bool:
        return isinstance(other, XCAPUser) and self.uri == other.uri

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __bool__(self) -> bool:
        return bool(self.username) and bool(self.domain)

    def __str__(self) -> str:
        return "%s@%s" % (self.username, self.domain)

    def __repr__(self) -> str:
        return 'XCAPUser(%r, %r)' % (self.username, self.domain)

    def __hash__(self) -> int:
        return hash(self.username)

    @classmethod
    def parse(cls, user_id: str, default_domain: Optional[str] = None) -> "XCAPUser":
        if user_id.startswith("sip:"):
            user_id = user_id[4:]
        _split = user_id.split('@', 1)
        username = _split[0]
        if len(_split) == 2:
            domain = _split[1]
        else:
            domain = default_domain if default_domain else ''
        return cls(username, domain)


class XCAPUri(object):
    """An XCAP URI containing the XCAP root, document selector and node selector."""

    def __init__(self, xcap_root: XCAPRootURI, resource_selector: str, namespaces: dict[Any, Any]):
        "namespaces maps application id to default namespace"
        self.xcap_root = xcap_root
        self.resource_selector = unquote(resource_selector)
        realm = None

        # convention to get the realm if it's not contained in the user ID section
        # of the document selector (bad eyebeam)
        if self.resource_selector.startswith("@"):
            first_slash = self.resource_selector.find("/")
            realm = self.resource_selector[1:first_slash]
            self.resource_selector = self.resource_selector[first_slash:]

        _split = self.resource_selector.split('~~', 1)

        doc_selector = _split[0]
        self.doc_selector = DocumentSelector(doc_selector)
        self.application_id = self.doc_selector.application_id
        self.node_selector: Union[NodeSelector, None] = None
        if len(_split) == 2:
            self.node_selector = NodeSelector(_split[1], namespaces.get(self.application_id))
        if self.doc_selector.user_id:
            self.user = XCAPUser.parse(self.doc_selector.user_id, realm)
        else:
            self.user = XCAPUser(None, realm)

    def __str__(self) -> str:
        return self.xcap_root + self.resource_selector

