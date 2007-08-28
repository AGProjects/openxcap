#!/usr/bin/python

from distutils.core import setup, Extension
from xcap import __version__

setup(name         = "openxcap",
      version      = __version__,
      author       = "Mircea Amarascu",
      author_email = "mircea@ag-projects.com",
      url          = "http://openxcap.org/",
      description  = "An open source XCAP server.",
      long_description = """XCAP protocol allows a client to read, write, and modify application
configuration data stored in XML format on a server. XCAP maps XML document
sub-trees and element attributes to HTTP URIs, so that these components can
be directly accessed by HTTP. An XCAP server is used by the XCAP clients to
store data like Presence policy in combination with a SIP Presence server
that supports PUBLISH/SUBSCRIBE/NOTIFY methods to provide a complete
[http://www.tech-invite.com/Ti-sip-WGs.html#wg-simple SIP SIMPLE] server
solution.""",
      license      = "BSD",
      platforms    = ["Platform Independent"],
      classifiers  = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Service Providers",
        "License :: OSI Approved :: Berkeley Software Distribution License (BSD)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
      ],
      packages = ['xcap', 'xcap.appusage', 'xcap.interfaces', 'xcap.interfaces.backend', 'xcap.test'],
      scripts  = ['openxcap'],
      package_data = {'xcap': ['xml-schemas/*']},
      data_files=[('/etc/openxcap', ['config.ini.sample'])]
      )
