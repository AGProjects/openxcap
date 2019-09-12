#!/usr/bin/env python

import os
import xcap

from distutils.core import setup

long_description = """XCAP protocol allows a client to read, write, and modify application
configuration data stored in XML format on a server. XCAP maps XML document
sub-trees and element attributes to HTTP URIs, so that these components can
be directly accessed by HTTP. An XCAP server is used by the XCAP clients to
store data like Presence policy in combination with a SIP Presence server
that supports PUBLISH/SUBSCRIBE/NOTIFY methods to provide a complete
[http://www.tech-invite.com/Ti-sip-WGs.html#wg-simple SIP SIMPLE] server
solution."""


def find_packages(toplevel):
    return [directory.replace(os.path.sep, '.') for directory, subdirs, files in os.walk(toplevel) if '__init__.py' in files]


setup(
    name='openxcap',
    version=xcap.__version__,

    description='XCAP server',
    long_description=long_description,
    url='http://openxcap.org/',

    author='AG Projects',
    author_email='support@ag-projects.com',

    license='GPL',
    platforms=['Platform Independent'],

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Service Providers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
    ],

    packages=find_packages('xcap'),
    package_data={'xcap.appusage': ['xml-schemas/*']},
    data_files=[('/etc/openxcap', ['config.ini.sample']), ('/etc/openxcap/tls', ['tls/README'])],
    scripts=['openxcap']
)
