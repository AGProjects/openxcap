
from setuptools import find_packages, setup

import xcap

long_description = """XCAP protocol allows a client to read, write, and modify application
configuration data stored in XML format on a server. XCAP maps XML document
sub-trees and element attributes to HTTP URIs, so that these components can
be directly accessed by HTTP. An XCAP server is used by the XCAP clients to
store data like Presence policy in combination with a SIP Presence server
that supports PUBLISH/SUBSCRIBE/NOTIFY methods to provide a complete SIP
SIMPLE server solution."""

setup(
    name=xcap.__project__,
    version=xcap.__version__,

    description=xcap.__description__,
    long_description=long_description,
    url=xcap.__url__,

    author=xcap.__author__,
    author_email=xcap.__author_email__,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Intended Audience :: Service Providers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    packages=find_packages(where="xcap"),  # Looking for packages in the "xcap" folder
    package_data={'xcap.appusage': ['xml-schemas/*']},
    data_files=[('/etc/openxcap', ['config.ini.sample']), ('/etc/openxcap/tls', ['tls/README'])],
    scrips=['openxcap'],
    include_package_data=True,
)

