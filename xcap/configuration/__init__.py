from application.configuration import ConfigSection, ConfigSetting
from application.configuration.datatypes import IPAddress, NetworkRangeList

from xcap.configuration.datatypes import (DatabaseURI, Path, ResponseCodeList,
                                          XCAPRootURI)
from xcap.tls import Certificate, PrivateKey


class AuthenticationConfig(ConfigSection):
    __cfgfile__ = 'config.ini'
    __section__ = 'Authentication'

    type = 'digest'
    cleartext_passwords = False
    default_realm = ConfigSetting(type=str, value=None)
    trusted_peers = ConfigSetting(type=NetworkRangeList, value=NetworkRangeList('none'))


class ServerConfig(ConfigSection):
    __cfgfile__ = 'config.ini'
    __section__ = 'Server'

    address = ConfigSetting(type=IPAddress, value='0.0.0.0')
    port = ConfigSetting(type=int, value=80)
    root = ConfigSetting(type=XCAPRootURI, value=None)
    backend = ConfigSetting(type=str, value=None)
    allow_external_references = False
    tcp_port = ConfigSetting(type=int, value=35060)


class TLSConfig(ConfigSection):
    __cfgfile__ = 'config.ini'
    __section__ = 'TLS'

    certificate = ConfigSetting(type=Certificate, value=None)
    private_key = ConfigSetting(type=PrivateKey, value=None)


class DatabaseConfig(ConfigSection):
    __cfgfile__ = 'config.ini'
    __section__ = 'Database'

    authentication_db_uri = ConfigSetting(type=DatabaseURI, value=None)
    storage_db_uri = ConfigSetting(type=DatabaseURI, value=None)
    subscriber_table = 'subscriber'
    user_col = 'username'
    domain_col = 'domain'
    password_col = 'password'
    ha1_col = 'ha1'
    xcap_table = 'xcap'


class OpensipsConfig(ConfigSection):
    __cfgfile__ = 'config.ini'
    __section__ = 'OpenSIPS'

    publish_xcapdiff = False
    outbound_sip_proxy = ''


class LoggingConfig(ConfigSection):
    __cfgfile__ = 'config.ini'
    __section__ = 'Logging'

    directory = ConfigSetting(type=Path, value=Path('/var/log/openxcap'))

    log_request = ConfigSetting(type=ResponseCodeList, value=ResponseCodeList('none'))
    log_response = ConfigSetting(type=ResponseCodeList, value=ResponseCodeList('none'))


class ThorNodeConfig(ConfigSection):
    __cfgfile__ = "config.ini"
    __section__ = 'ThorNetwork'

    domain = ""
    multiply = 1000
    certificate = ConfigSetting(type=Certificate, value=None)
    private_key = ConfigSetting(type=PrivateKey, value=None)
    ca = ConfigSetting(type=Certificate, value=None)

