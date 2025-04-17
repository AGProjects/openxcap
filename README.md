 
OpenXCAP
--------

Home page: http://openxcap.org


Authors
-------

Mircea Amarascu
Ruud Klaver
Lucian Stanescu
Denis Bilenko
Saul Ibarra
Tijmen de Mes


Description
-----------

OpenXCAP is an open source fully featured XCAP server. An XCAP server is
used by SIP SIMPLE clients and servers to manage buddy lists and policy for
subscriptions to presence or other types of events published using SIP
protocol. OpenXCAP server works out of the box with OpenSIPS Presence Agent.

The software is licensed according to the GNU General Public License version
3. For other licensing options please contact sales-request@ag-projects.com


Background
----------

XCAP protocol allows a client to read, write, and modify application
configuration data stored in XML format on a server. XCAP maps XML document
sub-trees and element attributes to HTTP URIs, so that these components can
be directly accessed by clients using HTTP protocol. An XCAP server is used
by XCAP clients to store data like buddy lists and presence policy in
combination with a SIP Presence server that supports PUBLISH, SUBSCRIBE and
NOTIFY methods to provide a complete SIP SIMPLE server solution.


Features
--------

The server is written in Python programming language and implements the
following standards:

RFC4825, RFC4826, RFC4827, RFC5025, 5874

 * Suport for multiple domains
 * Full and partial XML document manipulation
 * XML schema validation
 * Supports multiple back-end storage systems
 * Works out of the box with OpenSIPS Presence agent
 * TLS encryption and digital certificates using GnuTLS library
 * Digest or basic HTTP authentication with support for multiple realms
 * Database passwords can be stored in an encrypted format
 * Supports a JSON REST API for interacting with a resource-list document
   containing a sipsimple addressbook

Supported XCAP applications

 * XCAP capabilities (auid = xcap-caps). Lists the capabilities of the
   OpenXCAP server.
 * Resource lists (auid = resource-lists). A resource lists application is
   any application that needs access to a list of resources, identified by a
   URI, to which operations, such as subscriptions, can be applied.
 * Presence rules (auid = pres-rules, org.openmobilealliance.pres-rules). A
   Presence Rules application is an application which uses authorization
   policies, also known as authorization rules, to specify what presence
   information can be given to which watchers, and when.
 * RLS services (auid = rls-services). A Resource List Server (RLS) services
   application is Session Initiation Protocol (SIP) application whereby a
   server receives SIP SUBSCRIBE requests for resource, and generates
   subscriptions towards the resource list. See the README file for more
   details about of the implementation.
 * PIDF manipulation (auid = pidf-manipulation). Pidf-manipulation
   application usage defines how XCAP is used to manipulate the contents of
   PIDF based presence documents.
 * XCAP directory (auid = org.openmobilealliance.xcap-directory).
   Lists the documents stored in the XCAP server for a given user.
 * icon (auid = oma_status-icon). Manipulate the user icon for
   a given user and provide icon download capability from HTTP clients.
 * Dialog rules (auid = org.openxcap.dialog-rules). Dialog Rules application
   is a private application modeled after Presence rules that uses
   authorization policies, to specify when dialog information can be given
   to which watchers.
 * Watchers (auid = org.openxcap.watchers, private application). This
   application returns the list of watchers from OpenSIPS presence agent.


Installation
------------

See INSTALL file.


Support
-------

The project is developed and supported by AG Projects. The support is
provided on a best-effort basis. "best-effort" means that we try to solve
the bugs you report or help fix your problems as soon as we can, subject to
available resources.

To request support you must use the mailing list available at

https://lists.ag-projects.com/mailman/listinfo/sipbeyondvoip

