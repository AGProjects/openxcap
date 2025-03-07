
"""TLS helper classes"""

__all__ = ['Certificate', 'PrivateKey']

from application import log
from application.process import process
from gnutls.crypto import X509Certificate, X509PrivateKey
from typing import Optional


class _FileError(Exception):
    pass


def file_content(filename: str) -> str:
    path: Optional[str] = process.configuration.file(filename)
    if path is None:
        raise _FileError('File %r does not exist' % filename)
    try:
        with open(path, "rt", encoding="utf-8") as f:
            return f.read()
    except Exception:
        raise _FileError('File %r could not be open' % filename)


class Certificate(object):
    """Configuration data type. Used to create a gnutls.crypto.X509Certificate object
       from a file given in the configuration file."""
    def __new__(cls, value: str) -> X509Certificate:
        if not isinstance(value, str):
            raise TypeError('value should be a string')

        try:
            cert = X509Certificate(file_content(value))
            cert.filename = value
            return cert
        except Exception as e:
            log.warning('Certificate file %r could not be loaded: %s' % (value, e))
            return None


class PrivateKey(object):
    """Configuration data type. Used to create a gnutls.crypto.X509PrivateKey object
       from a file given in the configuration file."""
    def __new__(cls, value) -> X509PrivateKey:
        if not isinstance(value, str):
            raise TypeError('value should be a string')

        try:
            key = X509PrivateKey(file_content(value))
            key.filename = value
            return key
        except Exception as e:
            log.warning('Private key file %r could not be loaded: %s' % (value, e))
            return None
