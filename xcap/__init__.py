# Copyright (C) 2007 AG-Projects.
#

"""XCAP package"""

__version__ = "1.1.1"
__cfgfile__ = "config.ini"

def extended_version():
    patchlevel = globals().get('patchlevel')
    if patchlevel is None:
        return __version__
    elif patchlevel==1:
        return __version__ + ' (+ 1 patch)'
    elif patchlevel>1:
        return __version__ + ' (+ %s patches)' % patchlevel
    return __version__

# patchlevel is appended by `setup.py set_patchlevel' command

package_requirements = {'python-application': '1.1.5',
                        'python-gnutls':      '1.1.8',
                        'twisted':            '8.1.0'}

try:
    from application.dependency import ApplicationDependencies, DependencyError
except ImportError:
    class DependencyError(Exception): pass

    class ApplicationDependencies(object):
        def __init__(self, *args, **kw):
            pass
        def check(self):
            required_version = package_requirements['python-application']
            raise DependencyError("need python-application version %s or higher but it's not installed" % required_version)

dependencies = ApplicationDependencies(**package_requirements)

