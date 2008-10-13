# Copyright (C) 2007 AG-Projects.
#

"""XCAP package"""

__version__ = "1.0.4"
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
