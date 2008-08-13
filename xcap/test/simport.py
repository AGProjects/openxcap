import sys
import os
import __builtin__

__real_import__ = __builtin__.__import__


def has_module(dir, modulename):
    package = os.path.join(dir, modulename)
    if os.path.isdir(package) and os.path.exists(os.path.join(package, '__init__.py')):
        return os.path.split(package)[0]
    module = package + '.py'
    if os.path.exists(module) and os.path.isfile(module):
        return os.path.split(package)[0]

def find_module_path(modulename, start='.'):
    modulename = modulename.split('.', 1)[0]
    d = os.path.abspath(start)
    while d:
        result = has_module(d, modulename)
        if result:
            return result
        for x in os.listdir(d):
            x = os.path.join(d, x)
            if os.path.isdir(x):
                result = has_module(x, modulename)
                if result:
                    return result
        new_d = os.path.split(d)[0]
        if len(d)==len(new_d):
            break
        d = new_d

def seeking_import(name, *args, **kwargs):
    try:
        return __real_import__(name, *args, **kwargs)
    except ImportError:
        path = find_module_path(name)
        if not path:
            raise
        sys.stderr.write('importing %r from %s\n' % (name, path))
        sys.path.append(path)
        try:
            return __real_import__(name, *args, **kwargs)
        finally:
            del sys.path[-1]

def setup():
    __builtin__.__import__ = seeking_import

def restore():
    __builtin__.__import__ = __real_import__
