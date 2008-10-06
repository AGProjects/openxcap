# Copyright (C) 2007 AG-Projects.
#

"""XCAP package"""

__version__ = "1.0.3"
__cfgfile__ = "config.ini"

def extended_version():
    try:
        if patchlevel==1:
            return __version__ + ' (+ 1 patch)'
        elif patchlevel>1:
            return __version__ + ' (+ %s patches)' % patchlevel
    except NameError:
        pass
    return __version__

# patchlevel is appended by setup.py
