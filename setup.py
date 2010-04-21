#!/usr/bin/python
import os
import re
from distutils.core import setup, Command
from xcap import __version__

class BaseCommand(Command):
    user_options = []
    def initialize_options (self):
        pass
    def finalize_options (self):
        pass

def get_output(cmd):
    return os.popen(cmd).read().strip()

class UpdatePatchlevel(BaseCommand):
    """Query darcs for number of patches since the latest release and update
    patchlevel in xcap/__init__.py.

    Do not commit patchlevel into the repository, use remove_patchlevel to clean up"""

    filename = 'xcap/__init__.py'
    description = "update patchlevel in %s" % filename

    line_pattern = '\npatchlevel=\\d+\n'
    get_version = """darcs changes -t ^1. --reverse | tail -1 | cut -d ' ' -f 4"""
    get_patchlevel = """darcs changes --from-tag ^1. | grep '^  \*' | wc -l"""

    def run(self):
        version = get_output(self.get_version)
        if version != __version__:
            print 'xcap.__version__ and the latest tag do not match. cannot calculate patchlevel'
            return
        patchlevel = int(get_output(self.get_patchlevel))
        if self.patch(patchlevel):
            print 'patched it:'
            os.system('darcs diff %s' % self.filename)
        else:
            print "it's already there"

    def patch(self, new_patchlevel):
        line = self.line_pattern.replace('\\d+', str(new_patchlevel))
        try:
            from xcap import patchlevel
        except ImportError:
            if new_patchlevel==0:
                return False
            file(self.filename, 'a').write(line)
            return True
        else:
            if str(patchlevel) == str(new_patchlevel):
                return False
        repl, count = re.subn(self.line_pattern, line, file(self.filename).read())
        assert count==1, (count, repl)
        assert repl, repl
        file(self.filename, 'w').write(repl)
        return True


class RemovePatchlevel(BaseCommand):

    filename = UpdatePatchlevel.filename
    description = "remove patchlevel from %s" % filename

    def run(self):
        repl, count = re.subn(UpdatePatchlevel.line_pattern, '', file(self.filename).read())
        if not count:
            print "it's not there"
            return
        assert count==1, (count, repl)
        file(self.filename, 'w').write(repl)
        print 'removed it'
        os.system('darcs diff %s' % self.filename)


setup(name         = "openxcap",
      version      = __version__,
      author       = "Mircea Amarascu",
      author_email = "support@ag-projects.com",
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
      license      = "GPL",
      platforms    = ["Platform Independent"],
      classifiers  = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Service Providers",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
      ],
      packages = ['xcap', 'xcap.appusage', 'xcap.interfaces', 'xcap.interfaces.backend', 'xcap.sax', 'xcap.test'],
      scripts  = ['openxcap'],
      package_data = {'xcap': ['xml-schemas/*'],
                      'xcap.test': ['schemas/*']},
      cmdclass = {'set_patchlevel': UpdatePatchlevel,
                  'remove_patchlevel': RemovePatchlevel}
      )
