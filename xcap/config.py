import os
from application.configuration import ConfigFile as _ConfigFile, ConfigParser, ConfigSection, datatypes
from application.process import process
from application import log

from xcap import __cfgfile__

class ConfigFile(_ConfigFile):
    "Mostly the same as base, except that it allows filename be None, thus not reading anything"

    def __new__(cls, file=__cfgfile__):
        if not cls.instances.has_key(file):
            instance = object.__new__(cls)
            instance.parser = ConfigParser()
            if filename:
                files = [os.path.join(path, filename) for path in process.get_config_directories() if path is not None]
                instance.parser.read(files)
            cls.instances[filename] = instance
        return cls.instances[filename]
       
    def read_settings(self, section, cls):
        """Update cls's attributes with values read from the given section"""
        if not issubclass(cls, ConfigSection):
            raise TypeError("cls must be a subclass of ConfigSection")
        for prop in dir(cls):
            if prop[0]=='_':
                continue
            ptype = cls._datatypes.get(prop, eval('cls.%s.__class__' % prop))
            try:
                val = self.parser.get(section, prop)
            except:
                continue
            else:
                try:
                    if ptype is bool:
                        value = bool(datatypes.Boolean(val))
                    else:
                        value = ptype(val)
                except Exception, why:
                    msg = "ignoring invalid config value: %s.%s=%s (%s)." % (section, prop, val, why)
                    log.warn(msg, **ConfigFile.log_context)
                else:
                    setattr(cls, prop, value)
