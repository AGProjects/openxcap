# Copyright (C) 2007 AG-Projects.
#

"""XCAP package"""

__version__ = "1.1.3"
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

# python-lxml and python-sqlobject don't provide any usable version attribute.
package_requirements = {'python-application': '1.2.0',
                        'python-gnutls':      '1.1.8',
                        'python-xml':         '0.8.4',
                        'twisted':            '8.1.0'}

try:
    from application.dependency import ApplicationDependencies, PackageDependency, DependencyError
except ImportError:
    class DependencyError(Exception): pass

    class ApplicationDependencies(object):
        def __init__(self, *args, **kw):
            pass
        def check(self):
            required_version = package_requirements['python-application']
            raise DependencyError("need python-application version %s or higher but it's not installed" % required_version)

    class PackageDependency(object):
        def __init__(self, name, required_version, version_attribute=None):
            required_version = package_requirements['python-application']
            raise DependencyError("need python-application version %s or higher but it's not installed" % required_version)

package_dependencies = [PackageDependency('python-mysqldb', '1.2.2', 'MySQLdb.__version__')]
dependencies = ApplicationDependencies(*package_dependencies, **package_requirements)

