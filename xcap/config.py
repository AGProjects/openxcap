import os
from ConfigParser import NoOptionError
from application.configuration import ConfigFile as _ConfigFile, ConfigParser, ConfigSection, datatypes
from application.process import process
from application import log

from xcap import __cfgfile__

class mdict(dict):
    """keep __setitem__ history for chosen keys

    >>> x = mdict(['root'])
    >>> x.setdefault('root', 1)
    1
    >>> x['root'] = 2
    >>> x.update({'root': 3})
    >>> x['other'] = 4
    >>> x._mykeys
    {'root': [1, 2, 3]}
    """
    def __init__(self, mykeys=[]):
        self._mykeys = dict((x, []) for x in mykeys)

    def __setitem__(self, item, value):
        dict.__setitem__(self, item, value)
        if item in self._mykeys:
            self._mykeys[item].append(value)
           
    # DictMixin.setdefault
    def setdefault(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            self[key] = default
        return default

    # DictMixin.update
    def update(self, other=None, **kwargs):
        # Make progressively weaker assumptions about "other"
        if other is None:
            pass
        elif hasattr(other, 'iteritems'):  # iteritems saves memory and lookups
            for k, v in other.iteritems():
                self[k] = v
        elif hasattr(other, 'keys'):
            for k in other.keys():
                self[k] = other[k]
        else:
            for k, v in other:
                self[k] = v
        if kwargs:
            self.update(kwargs)

    def get_values_unique(self, option):
        lst = []
        for x in self._mykeys[option]:
            if x not in lst:
                lst.append(x)
        return lst


class MyConfigParser(ConfigParser):
    def __init__(self):
        ConfigParser.__init__(self)
        server_section = mdict(['root'])
        server_section['__name__'] = 'Server'
        self._sections = {'Server': server_section}


class ConfigFile(_ConfigFile):
    "Mostly the same as base, except that it allows filename be None, thus not reading anything"

    def __new__(cls, file=__cfgfile__):
        if not cls.instances.has_key(file):
            instance = object.__new__(cls)
            instance.parser = MyConfigParser()
            if hasattr(file, 'readline'):
                instance.parser.readfp(file)
            elif file:
                files = [os.path.join(path, file) for path in process.get_config_directories() if path is not None]
                # QQQ this loads the same file twice when system config dir == local config dir
                instance.parser.read(files)
            cls.instances[file] = instance
        return cls.instances[file]

    def get_values_unique(self, section, option):
        try:
            result = self.parser.get(section, option)
        except NoOptionError:
            return []
        try:
            return self.parser._sections[section].get_values_unique(option)
        except KeyError:
            return [result]
