
import os
import re

from application import log
from application.configuration import ConfigSection, ConfigSetting
from application.python.types import Singleton
from application.system import makedirs
from logging.handlers import WatchedFileHandler

import xcap


class Code(int):
    def __new__(cls, x):
        instance = super(Code, cls).__new__(cls, x)
        if not 100 <= instance <= 999:
            raise ValueError('Invalid HTTP response code: {}'.format(x))
        return instance


class MatchAnyCode(object):
    def __contains__(self, item):
        return True

    def __repr__(self):
        return '{0.__class__.__name__}()'.format(self)


class ResponseCodeList(object):
    def __init__(self, value):
        value = value.strip().lower()
        if value in ('all', 'any', 'yes', '*'):
            self._codes = MatchAnyCode()
        elif value in ('none', 'no'):
            self._codes = set()
        else:
            self._codes = {Code(code) for code in re.split(r'\s*,\s*', value)}

    def __contains__(self, item):
        return item in self._codes

    def __repr__(self):
        if isinstance(self._codes, MatchAnyCode):
            value = 'all'
        elif not self._codes:
            value = 'none'
        else:
            value = ','.join(sorted(self._codes))
        return '{0.__class__.__name__}({1!r})'.format(self, value)


class Logging(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Logging'

    directory = '/var/log/openxcap'  # directory where access.log will be created (if not specified, access logs will be logged as application log messages)

    log_request = ConfigSetting(type=ResponseCodeList, value=ResponseCodeList('none'))
    log_response = ConfigSetting(type=ResponseCodeList, value=ResponseCodeList('none'))


class _LoggedTransaction(object):
    def __init__(self, request, response):
        self._request = request
        self._response = response

    def __str__(self):
        return self.access_info

    @property
    def access_info(self):
        return '{request.remote_host} - {request.line!r} {response.code} {response.length} {request.user_agent!r} {response.etag!r}'.format(request=self._request, response=self._response)

    #
    # Request related properties
    #

    @property
    def line(self):
        return '{request.method} {request.uri} HTTP/{request.clientproto[0]}.{request.clientproto[1]}'.format(request=self._request)

    @property
    def remote_host(self):
        try:
            return self._request.remoteAddr.host
        except AttributeError:
            try:
                return self._request.chanRequest.getRemoteHost().host
            except (AttributeError, TypeError):
                return '-'

    @property
    def user_agent(self):
        return self._request.headers.getHeader('user-agent', '-')

    @property
    def request_content(self):
        headers = '\n'.join('{}: {}'.format(name, header) for name, headers in self._request.headers.getAllRawHeaders() for header in headers)
        body = getattr(self._request, 'attachment', '')
        content = '\n\n'.join(item for item in (headers, body) if item)
        return '\nRequest:\n\n{}\n\n'.format(content) if content else ''

    #
    # Response related properties
    #

    @property
    def code(self):
        return self._response.code

    @property
    def length(self):
        return self._response.stream.length if self._response.stream else 0

    @property
    def etag(self):
        etag = self._response.getHeader('etag') or '-'
        if hasattr(etag, 'tag'):
            etag = etag.tag
        return etag

    @property
    def response_content(self):
        headers = '\n'.join('{}: {}'.format(name, header) for name, headers in self._response.headers.getAllRawHeaders() for header in headers)
        body = self._response.stream.mem if self._response.stream else ''
        content = '\n\n'.join(item for item in (headers, body) if item)
        return '\nResponse:\n\n{}\n\n'.format(content) if content else ''


class WEBLogger(object):
    __metaclass__ = Singleton

    def __init__(self):
        self.logger = log.get_logger('weblog')
        self.logger.setLevel(log.level.INFO)
        if Logging.directory:
            if not os.path.exists(Logging.directory):
                try:
                    makedirs(Logging.directory)
                except OSError as e:
                    raise RuntimeError('Cannot create logging directory {}: {}'.format(Logging.directory, e))
            self.filename = os.path.join(Logging.directory, 'access.log')
            formatter = log.Formatter()
            formatter.prefix_format = ''
            handler = WatchedFileHandler(self.filename)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.propagate = False
        else:
            self.filename = None

    def log_access(self, request, response):
        web_transaction = _LoggedTransaction(request, response)
        self.logger.info(web_transaction.access_info)
        if response.code in Logging.log_request:
            request_content = web_transaction.request_content
            if request_content:
                self.logger.info(request_content)
        if response.code in Logging.log_response and web_transaction.length < 5000:
            response_content = web_transaction.response_content
            if response_content:
                self.logger.info(response_content)


root_logger = log.get_logger()
root_logger.name = 'server'
web_logger = WEBLogger()
