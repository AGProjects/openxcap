
OpenXCAP
========

Copyright (c) 2007-present AG Projects
http://ag-projects.com

Home page: http://openxcap.org


Installation
------------

Components
----------

* OpenXCAP, the XCAP server itself

* python3-xcaplib, an optional component that can be used for developing an
  XCAP client or for testing the server using the xcapclient command line
  utility


Dependencies
------------

 * Python 3 - http://www.python.org
 * Twisted - http://twistedmatrix.com
 * python-lxml - https://lxml.de
 * python3-application - https://github.com/AGProjects/python3-application
 * python3-gnutls - https://github.com/AGProjects/python3-gnutls
 * Fast API - https://fastapi.tiangolo.com/
 * Uvicorn - https://www.uvicorn.org 
 * SQLModel - https://sqlmodel.tiangolo.com
 * python3-sipsimple - https://sipsimpleclient.org

The requirements and versions are listed in requirements.txt.

For OpenSIPS support/REST API, python3-sipsimple is required.


Debian packages
---------------

Binary packages are available for Debian and Ubuntu on i386 and amd64
architectures.

Install AG Projects debian repository signing key:

```
wget http://download.ag-projects.com/agp-debian-gpg.key
sudo apt-key add agp-debian-gpg.key
```

Add the following lines to /etc/apt/sources.list:

```
# Debian Stable
deb http://ag-projects.com/debian stable main
deb-src http://ag-projects.com/debian stable main

# Debian Unstable
deb http://ag-projects.com/debian unstable main
deb-src http://ag-projects.com/debian unstable main

# Ubuntu (run this as root)
echo "deb     http://ag-projects.com/ubuntu `lsb_release -c -s` main" >> /etc/apt/sources.list
echo "deb-src http://ag-projects.com/ubuntu `lsb_release -c -s` main" >> /etc/apt/sources.list
```

Update the list of available packages:

```
sudo apt-get update
```

Install OpenXCAP server:

```
sudo apt-get install openxcap
```


Tar Archives
------------

OpenXCAP and related software can be downloaded as tar archives from Github.

Extract the software using tar xzvf openxcap-version.tar.gz.

Install OpenXCAP:

```
cd openxcap
sudo python setup.py install
```

Download python3-xcaplib and extract it using tar xzvf
python-xcaplib-version.tar.gz.

Install python3-xcaplib:

```
cd python3-xcaplib
sudo python setup.py install
```

Version Control Repository
--------------------------

The source code is managed using darcs version control tool from
http://darcs.net. The darcs repository can be fetched with:

darcs get http://devel.ag-projects.com/repositories/openxcap

Other packages like python3-xcaplib, python3-sipsimple
can be obtained in the same way.

To obtain the incremental changes after the initial get:

```
cd openxcap
darcs pull -a
```

The respository is mirrored on Github at https://github.com/AGProjects/openxcap


Configuration
-------------

Database
--------

Both OpenXCAP backends (Database and OpenSIPS) depend on a database engine
to store the subscribers and their XCAP documents. The database creation
scripts are found in the scripts/ directory.

Creating database tables

If you use OpenSIPS backend, you must configure OpenXCAP to use the same
database as OpenSIPS.  If you want OpenXCAP to use its own database, you
need to create the database with its tables.

If you use sqlite and a venv, the database will be automatically created.

`mysqladmin create openxcap`

Add a MySQL user

Use this script as template, edit it first and run it against on your
database:

 * scripts/mysql-create-user.sql

If you run it in a venv and you have the requirements installed, alembic can
create the database, in debian you can go to /usr/share/doc/openxcap and run
the command:

`alembic upgrade heads`

You can also the tables using the sample script:

 * scripts/mysql-create-tables.sql

This script creates three tables:

 * subscriber, which is used to authenticate XCAP requests
 * xcap, where the XCAP documents are actually stored
 * watchers
 
The subscriber table is a subset of OpenSIPS's xcap subscriber table.

For the Debian package, the above sql sample scripts are installed in openxcap
shared directory, in /usr/share/docs/openxcap.


OpenXCAP
--------

For the Debian package edit /etc/openxcap/config.ini. For other Linux OS copy
config.ini.sample from the tar archive to the same directory. Edit config.ini
with your settings.

In a venv a config.ini can be read from the same location as the openxcap script.

The specific settings for an installation must be set from the configuration
file, which is split in several configuration sections.

The [Server] section contains global settings: the IP address and port where
OpenXCAP listens for client requests.

The XCAP root is the context that contains all the documents across all
applications and users that are managed by the server. Only the client requests
that address the root defined here are accepted. If the root URI has the
"https" scheme and a certificate and key file are configured, the server will
listen for requests in TLS mode. The X509 certificate and private key that will
identify the server are loaded using the values in the [TLS] section.

OpenXCAP supports multiple, interchangeable backend modules. Each backend
knows where and how to authorize and authenticate XCAP users and where to
store the XCAP documents. Currently, supported values are "Database" and
"OpenSIPS", the specific settings will be taken the corresponding sections,
[Database] or [OpenSIPS].

An XCAP request must be authenticated before it's handled, and the various
settings are found in the [Authentication] section.

A trusted peer IP list can be defined, requests matching this list will be
accepted without authentication.

Client requests must be authenticated in the context of a realm that is the
same as the SIP domain. This realm is derived in real time for each request
using the following logic:

 * if the user section of the XCAP URI (the section following the "users"
   path segment) is in the form of username@domain, the realm is taken from the
   domain part

 * some XCAP clients (e.g. CounterPath's Eyebeam), only put the
   username in the XCAP URI, so there is the need for a convention to
   determine the realm: it must be included in the XCAP root URI on the
   client side.  For example, if the XCAP root of the server is
   http://example.com/xcap-root, the client should be provisioned with
   http://example.com/xcap-root@domain/

 * if the above logic does not provide the realm, the realm will be taken
   from the default_realm setting of [Authentication] There are separate
   configuration settings for each backend. The current supported back-ends are
   Database and OpenSIPS.

The Database section contains the database connection URI to the database
where the service subscribers are kept (authentication_db_uri) and the
database connection URI to the database where XCAP documents are stored.
Currently, only MySQL database engine has been implemented.

The OpenSIPS section contains all the settings for OpenSIPS. 

When using TLS you must generate an X.509 certificate and the corresponding
key.  Consult Internet resources for how to do this.  The procedure is the
same as for any other TLS server like Apache web server.


Running the server
------------------

For non Debian systems copy the service file from the debian directory to
/etc/systemd/system/ edit it to match your system.

The reload systemd:

`sudo systemctl daemon-reload`

Start OpenXCAP server:

`sudo systemctl start openxcap`

You can also start OpenXCAP in the foreground, which is useful to debug the
configuration and requests in real time.  The server will log its messages
in the console where it was started:

```
~ ./openxcap --no-fork                                                                                                                                                                                                                                                                                5.2s  Mon Mar 24 15:55:18 2025
INFO     Started server process [99259]
INFO     Waiting for application startup.
INFO     Context impl SQLiteImpl.
INFO     Will assume non-transactional DDL.
INFO     Database initialized and migrations applied.
INFO     OpenXCAP app is running...
INFO     Application startup complete.
INFO     Uvicorn running on http://0.0.0.0:80 (Press CTRL+C to quit)
```

OpenXCAP logs its messages to /var/log/openxcap/ and to the system log. 

### Logging

OpenXCAP logs its start, stop and error messages to /var/log/syslog or the
journal. Client access requests are logged in /var/log/openxcap/access.log. You
can configure the logging of the headers and bodies of client requests and
responses in the Logging section of the configuration file.

### Adding Accounts

The accounts used for authentication of XCAP requests are stored in OpenSIPS
subscriber table. You can add subscribers by using your favorite OpenSIPS
subscriber management tool. Check the following script that can be used to
add manually account to opensips subscriber table:

 * scripts/add_openxcap_users.py


JSON API
--------

A RESTful API is available to manage in an easy way an addressbook, which handles the
modifications of XCAP documents. The API can show/update/delete contacts, groups
and policies.

A full description of the API can be accessed using a web browser at the
'/docs' or '/redoc' urls.  At this URL one can also test all API functions.

A working example is deployed with sip2sip.info SIP service at:

https://xcap.sipthor.net/docs

and

https://xcap.sipthor.net/redoc


Test Suite
----------

A test suite for testing the functionality the server is located in test in the
source. If you have installed the Debian Package it is not bundled.

Configure the credentials of a test account and the xcap root in a
configuration file ~/.xcapclient.ini

```
[Account_test]
sip_address=alice@example.com
password=123
xcap_root = http://xcap.example.com/xcap-root
```

Replace the xcap_root with the same xcap_root configured in the server and
make sure the hostname points to the IP address where the server listens to.

Add the same test account to the OpenSIPS subscriber table:

```
INSERT INTO `subscriber` (username,domain,password,ha1) VALUES
('alice','example.com','1234', 'fd7cab2287702c763e7b318b7fb2451a');
```

Run the test suite:

```
~$./test.py
test_operations1 (test_resourcelists.DocumentTest.test_operations1) ... ok
test_operations2 (test_resourcelists.DocumentTest.test_operations2) ... ok
test_operations3 (test_resourcelists.DocumentTest.test_operations3) ... ok
test_operations4 (test_resourcelists.DocumentTest.test_operations4) ... ok
test_conditional_PUT (test_etags2.ETagTest.test_conditional_PUT) ... ok
test_conditional_PUT_2 (test_etags2.ETagTest.test_conditional_PUT_2) ... ok
test_get (test_watchers.Test.test_get) ... ok
test_pidf_manipulation (test_presrules.PresenceRulesTest.test_pidf_manipulation) ... ok
test_conditional_GET (test_etags.ETagTest.test_conditional_GET) ... ok
test_conditional_PUT (test_etags.ETagTest.test_conditional_PUT) ... ok
test_conditional_PUT_2 (test_etags.ETagTest.test_conditional_PUT_2) ... ok
test_conditional_GET (test_etags.ETagTest2.test_conditional_GET) ... ok
test_conditional_PUT (test_etags.ETagTest2.test_conditional_PUT) ... ok
test_etag_parsing (test_etags.ETagTest2.test_etag_parsing) ... ok
test_pidf_manipulation (test_pidf.PIDFTest.test_pidf_manipulation) ... ok
test_xpath10_valid (test_xpath.XPathTest.test_xpath10_valid) ... ok
test_xpath11_valid (test_xpath.XPathTest.test_xpath11_valid) ... ok
test_xpath12_valid (test_xpath.XPathTest.test_xpath12_valid) ... ok
test_xpath1_valid (test_xpath.XPathTest.test_xpath1_valid) ... ok
test_xpath2_invalid (test_xpath.XPathTest.test_xpath2_invalid) ... ok
test_xpath3_invalid (test_xpath.XPathTest.test_xpath3_invalid) ... ok
test_xpath4_invalid (test_xpath.XPathTest.test_xpath4_invalid) ... ok
test_xpath5_invalid (test_xpath.XPathTest.test_xpath5_invalid) ... ok
test_xpath6_invalid (test_xpath.XPathTest.test_xpath6_invalid) ... ok
test_xpath7_invalid (test_xpath.XPathTest.test_xpath7_invalid) ... ok
test_xpath8_invalid (test_xpath.XPathTest.test_xpath8_invalid) ... ok
test_xpath9_valid (test_xpath.XPathTest.test_xpath9_valid) ... ok
test_global_auth (test_auth.AuthTest_org_openmobilealliance_pres_rules.test_global_auth) ... ok
test_users_auth (test_auth.AuthTest_org_openmobilealliance_pres_rules.test_users_auth) ... ok
test_global_auth (test_auth.AuthTest_pidf_manipulation.test_global_auth) ... ok
test_users_auth (test_auth.AuthTest_pidf_manipulation.test_users_auth) ... ok
test_global_auth (test_auth.AuthTest_pres_rules.test_global_auth) ... ok
test_users_auth (test_auth.AuthTest_pres_rules.test_users_auth) ... ok
test_global_auth (test_auth.AuthTest_resource_lists.test_global_auth) ... ok
test_users_auth (test_auth.AuthTest_resource_lists.test_users_auth) ... ok
test_global_auth (test_auth.AuthTest_rls_services.test_global_auth) ... ok
test_users_auth (test_auth.AuthTest_rls_services.test_users_auth) ... ok
test_global_auth (test_auth.AuthTest_test_app.test_global_auth) ... ok
test_users_auth (test_auth.AuthTest_test_app.test_users_auth) ... ok
test_global_auth (test_auth.AuthTest_watchers.test_global_auth) ... ok
test_users_auth (test_auth.AuthTest_watchers.test_users_auth) ... ok
test_global_auth (test_auth.AuthTest_xcap_caps.test_global_auth) ... ok
test_users_auth (test_auth.AuthTest_xcap_caps.test_users_auth) ... ok
test400_1 (test_errors.ErrorsTest.test400_1) ... ok
test400_2 (test_errors.ErrorsTest.test400_2) ... ok
test404 (test_errors.ErrorsTest.test404) ... ok
test405 (test_errors.ErrorsTest.test405) ... ok
test409 (test_errors.ErrorsTest.test409) ... ok
test_gibberish (test_errors.ErrorsTest.test_gibberish) ... ok
test_delete (test_element.ElementTest.test_delete) ... ok
test_get (test_element.ElementTest.test_get) ... WARNING: test with URI in att_value is disabled
ok
test_put_error (test_element.ElementTest.test_put_error) ... ok
test_creation (test_element_put.PutElementTest.test_creation)
Testing different ways of inserting an element as described in examples from Section 8.2.3 ... ok
test_creation_starattr (test_element_put.PutElementTest.test_creation_starattr)
Testing PUT requests of form '*[@att="some"]' which require looking into body of PUT ... ok
test_replacement (test_element_put.PutElementTest.test_replacement) ... ok
test_schema (test_xcap_caps.XCAPCaps.test_schema) ... ok
test_delete (test_attribute.AttributeTest.test_delete) ... ok
test_get (test_attribute.AttributeTest.test_get) ... WARNING: test with URI in att_value is disabled
ok
test_put (test_attribute.AttributeTest.test_put) ... ok
test_ns_bindings (test_nsbindings.NSBindingsTest.test_ns_bindings) ... ok
test_has_global (test_global.TestGlobal.test_has_global) ... ok
test_no_global (test_global.TestGlobal.test_no_global) ... ok
test_errors (test_fragment.FragmentTest.test_errors) ... ok
test_success (test_fragment.FragmentTest.test_success) ... ok
test_operations1 (test_rlsservices.DocumentTest.test_operations1) ... ok
test_operations2 (test_rlsservices.DocumentTest.test_operations2) ... ok
test_operations3 (test_rlsservices.DocumentTest.test_operations3) ... ok
test_operations4 (test_rlsservices.DocumentTest.test_operations4) ... ok

----------------------------------------------------------------------
Ran 68 tests in 1.491s

OK
```
Notes:

- Running the test suite for a given user will result in the destruction of
  all xcap documents belonging to that user

- Replacing 'test.py' with 'test_something.py' will run only the tests
  defined in test_something.py


xcapclient
----------

A command line client is available in the python-xcaplib package available
in same download repository of OpenXCAP server. The client can be used to
manipulate full or partial XML documents on XCAP servers (not limited to
OpenXCAP) and has a bash shell command line completion facility that makes
it very easy to browse through the structure of XML documents based on
XPATH.

See README of python3-xcaplib package for examples on how to create/retrieve
a document.

