
# Copyright (C) 2007-2010 AG-Projects.
#

import os
import re
from StringIO import StringIO
from twisted.web2 import responsecode
from twisted.python.logfile import LogFile
from twisted.python.log import FileLogObserver, startLoggingWithObserver
from application import log
from application.configuration import ConfigSection, ConfigSetting

import xcap


class ErrorCodeList(set):
    """
    >>> ErrorCodeList('BadRequest')
    ErrorCodeList([400])

    >>> big = ErrorCodeList('200, 201,NotFound, Conflict,  Internal_Server_Error , Bad Request ')
    >>> sorted(big)
    [200, 201, 400, 404, 409, 500]

    >>> 500 in big, 501 in big
    (True, False)

    >>> ErrorCodeList('*')
    AnyErrorCode

    >>> 200 in ErrorCodeList('all')
    True

    >>> ErrorCodeList('')
    ErrorCodeList([])

    >>> 200 in ErrorCodeList('')
    False

    >>> ErrorCodeList('InternalServerError, 10')
    Traceback (most recent call last):
     ...
    ValueError: 10 cannot be an HTTP error code
    """

    names = {}

    for k, v in responsecode.__dict__.iteritems():
        if isinstance(v, int) and 100<=v<=999:
            names[k.replace('_', '').lower()] = v
    del k, v

    def __new__(cls, value):
        if value.lower() in ('*', 'any', 'all', 'yes'):
            return AnyErrorCode
        return set.__new__(cls, value)

    def __init__(self, value):
        value = value.strip()
        if value.lower() in ('none', '', 'no'):
            return
        for x in re.split(r'\s*,\s*', value):
            x = x.lower()
            n = self.names.get(x.replace(' ', '').replace('_', ''))
            if n is None:
                n = int(x)
                if not 100<=n<=999:
                    raise ValueError, '%s cannot be an HTTP error code' % n
                self.add(n)
            else:
                self.add(n)

class AnyErrorCode(ErrorCodeList):
    def __new__(cls, value):
        return set.__new__(cls)

    def __init__(self, value):
        pass

    def __contains__(self, anything):
        return True

    def __repr__(self):
        return "AnyErrorCode"

AnyErrorCode = AnyErrorCode('')


class Logging(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Logging'

    # directory where access.log will be created
    # if directory is empty, everything (access and error) will be
    # printed to console
    directory = '/var/log/openxcap'

    # each log message is followed by the headers of the request
    log_request_headers = ConfigSetting(type=ErrorCodeList, value=[500])

    log_request_body = ConfigSetting(type=ErrorCodeList, value=[500])

    log_response_headers = ConfigSetting(type=ErrorCodeList, value=[500])

    # each log message is followed by the body of the response sent to the client
    log_response_body = ConfigSetting(type=ErrorCodeList, value=[500])

    # each log message is followed by the stacktrace if there was underlying exception
    log_stacktrace = ConfigSetting(type=ErrorCodeList, value=[500])


def log_format_request_headers(code, r):
    if matches(Logging.log_request_headers, code):
        return format_headers(r, 'REQUEST headers:\n')
    return ''

def log_format_response_headers(code, r):
    if matches(Logging.log_response_headers, code):
        return format_headers(r, 'RESPONSE headers:\n')
    return ''

def log_format_request_body(code, request):
    if matches(Logging.log_request_body, code):
        return format_request_body(request)
    return ''

def log_format_response_body(code, response):
    if matches(Logging.log_response_body, code):
        return format_response_body(response)
    return ''

def log_format_stacktrace(code, reason):
    if reason is not None and matches(Logging.log_stacktrace, code):
        return format_stacktrace(reason)
    return ''


def matches(cfg, code):
    return cfg == '*' or code in cfg

def format_response_body(response):
    res = ''
    content_type = None
    if hasattr(response, 'headers'):
        content_type = response.headers.getRawHeaders('content-type')
    if hasattr(response, 'stream') and hasattr(response.stream, 'mem'):
        res = str(response.stream.mem)
    if res:
        msg = ''
        if content_type:
            for x in content_type:
                msg += 'Content-Type: %s\n' % x
        msg += res
        return 'RESPONSE: ' + msg.replace('\n', '\n\t') + '\n'
    return res

def format_headers(r, msg='REQUEST headers:\n'):
    res = ''
    if hasattr(r, 'headers'):
        for (k, v) in r.headers.getAllRawHeaders():
            for x in v:
                res += '\t%s: %s\n' % (k, x)
    if res:
        res = msg + res
    return res

def format_request_body(request):
    res = ''
    if hasattr(request, 'attachment'):
        res = str(request.attachment)
        if res:
            return 'REQUEST: ' + res.replace('\n', '\n\t') + '\n'
    return res

def format_stacktrace(reason):
    if hasattr(reason, 'getTracebackObject') and reason.getTracebackObject() is not None:
        f = StringIO()
        reason.printTraceback(file=f)
        res = f.getvalue()
        first, rest = res.split('\n', 1)
        if rest[-1:]=='\n':
            rest = rest[:-1]
        if rest:
            return first.replace('Traceback', 'TRACEBACK') + '\n\t' + rest.replace('\n', '\n\t')
        return first
    return ''

def _repr(p):
    if p is None:
        return '-'
    else:
        return repr(p)

def _str(p):
    if p is None:
        return '-'
    else:
        return str(p)

def _etag(etag):
    if etag is None:
        return '-'
    if hasattr(etag, 'generate'):
        return etag.generate()
    else:
        return repr(etag)

def get_ip(request):
    if hasattr(request, 'remoteAddr'):
        return str(getattr(request.remoteAddr, 'host', '-'))
    else:
        return '-'

def get(obj, attr):
    return _repr(getattr(obj, attr, None))

def format_access_record(request, response):

    def format_clientproto(proto):
        try:
            return "HTTP/%d.%d" % (proto[0], proto[1])
        except IndexError:
            return ""

    ip = get_ip(request)
    request_line = "'%s %s %s'" % (request.method, request.unparseURL(), format_clientproto(request.clientproto))
    code = get(response, 'code')

    if hasattr(request, 'stream'):
        request_length = get(request.stream, 'length')
    else:
        request_length = '-'

    if hasattr(response, 'stream'):
        response_length = get(response.stream, 'length')
    else:
        response_length = '-'

    if hasattr(request, 'headers'):
        user_agent = _repr(request.headers.getHeader('user-agent'))
    else:
        user_agent = '-'

    if hasattr(response, 'headers'):
        response_etag = _etag(response.headers.getHeader('etag'))
    else:
        response_etag = '-'

    params = [ip, request_line, code, request_length, response_length, user_agent, response_etag]
    return ' '.join(params)

def format_log_message(request, response, reason):
    msg = ''
    info = ''
    try:
        msg = format_access_record(request, response)
        code = getattr(response, 'code', None)
        info += log_format_request_headers(code, request)
        info += log_format_request_body(code, request)
        info += log_format_response_headers(code, response)
        info += log_format_response_body(code, response)
        info += log_format_stacktrace(code, reason)
    except Exception:
        log.error('Formatting log message failed')
        log.err()
    if info[-1:]=='\n':
        info = info[:-1]
    if info:
        info = '\n' + info
    return msg + info

def log_access(request, response, reason=None):
    if getattr(request, '_logged', False):
        return
    msg = format_log_message(request, response, reason)
    request._logged = True
    if msg:
        log.msg(msg, access_log=True)

def log_error(request, response, reason):
    msg = format_log_message(request, response, reason)
    request._logged = True
    if msg:
        log.error(msg)


class ApacheLogObserver(object):

    params = {
        'rotateLength': 2*1024*1024,
        'maxRotatedFiles': 10 }

    def __init__(self, directory):
        access_file = LogFile('access.log', directory, **self.params)
        self.access = FileLogObserver(access_file)
        error_file = LogFile('error.log', directory, **self.params)
        self.error  = FileLogObserver(error_file)

    def emit(self, eventDict):
        if eventDict.get('access_log'):
            self.access.emit(eventDict)
        else:
            self.error.emit(eventDict)


def start_log(setStdout=True):
    if Logging.directory:
        if not os.path.exists(Logging.directory):
            os.mkdir(Logging.directory)
        obs = ApacheLogObserver(Logging.directory)
        startLoggingWithObserver(obs.emit, setStdout=setStdout)
    else:
        log.start_syslog('openxcap')


if __name__=='__main__':
    import doctest
    doctest.testmod()
    format_log_message(None, None, None)
    Logging.log_request_headers = AnyErrorCode
    Logging.log_response_body = AnyErrorCode
    Logging.log_stacktrace = AnyErrorCode
    format_log_message(None, None, None)
