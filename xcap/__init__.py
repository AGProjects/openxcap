
# Copyright (C) 2007-2010 AG-Projects.
#

"""XCAP package"""

__version__ = "1.2.1"
__cfgfile__ = "config.ini"


# python-lxml and python-sqlobject don't provide any usable version attribute.
package_requirements = {'python-application': '1.2.0',
                        'python-gnutls':      '1.1.8',
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

# web2 is not included anymore with twisted tarballs, but it's still on svn
# and all functionality hasn't been migrated to web yet. -Saul
try:
    import twisted.web2
except ImportError:
    raise DependencyError("Twisted's web2 component is missing. Check http://twistedmatrix.com/trac/wiki/Downloads")
del twisted.web2

