from cStringIO import StringIO
from collections import deque

from twisted.protocols.basic import LineReceiver
from twisted.internet.defer import Deferred, fail

class MemcacheError(Exception):
    pass


class NoSuchCommand(MemcacheError):
    pass


class ClientError(MemcacheError):
    pass


class ServerError(MemcacheError):
    pass


class DisconnectedError(MemcacheError):
    pass


class UnexpectedResponseError(MemcacheError):
    pass


class CommandUnsuccessful(MemcacheError):
    pass


class CommandBase(object):

    def __init__(self):
        self.defer = Deferred()

    def got_ERROR(self, nothing):
        raise NoSuchCommand()

    def got_CLIENT_ERROR(self, error):
        raise ClientError(error)

    def got_SERVER_ERROR(self):
        raise ServerError(error)


class CommandBaseStored(CommandBase):
    command = None

    def __init__(self, key, value, flags = 0, exptime = 0):
        CommandBase.__init__(self)
        self.key = key
        self.value = value
        self.flags = flags
        self.exptime = exptime

    def __str__(self):
        cmd_line = " ".join([self.command, self.key, str(self.flags), str(self.exptime), str(len(self.value))])
        return "\r\n".join([cmd_line, self.value, ""])

    def got_STORED(self, nothing):
        self.defer.callback(True)
        return 1


class CommandBaseNotStored(CommandBaseStored):

    def got_NOT_STORED(self, nothing):
        raise CommandUnsuccessful("Not stored")


class Command_set(CommandBaseStored):
    command = "set"


class Command_add(CommandBaseNotStored):
    command = "add"


class Command_replace(CommandBaseNotStored):
    command = "replace"


class Command_append(CommandBaseStored):
    command = "append"


class Command_prepend(CommandBaseStored):
    command = "prepend"


class Command_cas(CommandBaseStored):
    command = "cas"

    def __init__(self, key, value, cas_unique, flags = 0, exptime = 0):
        CommandBaseStored.__init__(self, key, value, flags = 0, exptime = 0)
        self.cas_unique = cas_unique

    def __str__(self):
        cmd_line = " ".join([self.command, self.key, str(self.flags), str(self.exptime), str(len(self.value)), str(self.cas_unique)])
        return "\r\n".join([cmd_line, self.value, ""])

    def got_EXISTS(self, nothing):
        raise CommandUnsuccessful("Exists")

    def got_NOT_FOUND(self, nothing):
        raise CommandUnsuccessful("Not found")


class Command_get(CommandBase):

    def __init__(self, key):
        CommandBase.__init__(self)
        self.key = key
        self._data_buf = StringIO()
        self._buf_len = 0
        self._found = False

    def __str__(self):
        return "get %s\r\n" % self.key

    def got_VALUE(self, parameters):
        self._found = True
        key, flags, bytes = parameters.split()
        self.flags = int(flags)
        return int(bytes) + 2

    def add_data(self, data):
        self._data_buf.write(data)
        self._buf_len += len(data)

    def got_END(self, nothing):
        if self._found:
            self._data_buf.seek(0)
            data = self._data_buf.read(self._buf_len - 2)
            self.defer.callback((data, self.flags))
            return 1
        else:
            raise CommandUnsuccessful("Not found")


class Command_gets(CommandBase):

    def __init__(self, key):
        CommandBase.__init__(self)
        self.key = key
        self._data_buf = StringIO()
        self._buf_len = 0
        self._found = False

    def __str__(self):
        return "gets %s\r\n" % self.key

    def got_VALUE(self, parameters):
        self._found = True
        key, flags, bytes, cas_unique = parameters.split()
        self.flags = int(flags)
        self.cas_unique = int(cas_unique)
        return int(bytes) + 2

    def add_data(self, data):
        self._data_buf.write(data)
        self._buf_len += len(data)

    def got_END(self, nothing):
        if self._found:
            self._data_buf.seek(0)
            data = self._data_buf.read(self._buf_len - 2)
            self.defer.callback((data, self.flags, self.cas_unique))
            return 1
        else:
            raise CommandUnsuccessful("Not found")


# incr and decr are not implemented as the API is damn inconsistent

class Command_delete(CommandBase):

    def __init__(self, key, timeout = 0):
        CommandBase.__init__(self)
        self.key = key

    def __str__(self):
        return "delete %s %d\r\n" % (self.key, self.timeout)

    def got_DELETED(self, nothing):
        raise CommandUnsuccessful("Deleted")

    def got_NOT_FOUND(self, nothing):
        raise CommandUnsuccessful("Not found")


class Command_stats(CommandBase):

    def __init__(self, args = None):
        CommandBase.__init__(self)
        self.args = args
        self.stats = {}

    def __str__(self):
        if self.args:
            return "stats %s\r\n" % args
        else:
            return "stats\r\n"

    def got_STAT(self, stat):
        stat_name, stat_value = stat.split(" ", 1)
        self.stats[stat_name] = stat_value
        return 0

    def got_END(self, nothing):
        self.defer.callback(self.stats)
        return 1

class Command_flush_all(CommandBase):

    def __init__(self, timeout = 0):
        CommandBase.__init__(self)
        self.timeout = timeout

    def __str__(self):
        if self.timeout:
            return "flush_all %d\r\n" % self.timeout
        else:
            return "flush_all\r\n"

    def got_OK(self, nothing):
        self.defer.callback(True)
        return 1


class Command_version(CommandBase):

    def __str__(self):
        return "version\r\n"

    def got_VERSION(self, version):
        self.defer.callback(version)
        return 1


class MemcacheProtocol(LineReceiver):
    DEFAULT_PORT = 11211

    def __init__(self, timeout = 5):
        self.queue = deque()
        self.timeout = timeout
        self.raw_bytes = 0

    def __getattr__(self, name):
        try:
            eval("Command_%s" % cmd)
        except NameError:
            raise AttributeError
        return lambda *args, **kwargs: self.do_command(name, *args, **kwargs)

    def do_command(self, cmd, *args, **kwargs):
        try:
            cmd_cls = eval("Command_%s" % cmd)
        except NameError:
            return fail(NoSuchCommand(cmd))
        command = cmd_cls(*args, **kwargs)
        self.transport.write(str(command))
        self.queue.append(command)
        return command.defer

    def lineReceived(self, line):
        if self.queue:
            command = self.queue[0]
            try:
                response, parameters = line.split(" ", 1)
            except:
                response = line
                parameters = None
            try:
                method = getattr(command, "got_%s" % response)
            except AttributeError:
                command.defer.errback(UnexpectedResponseError(line))
                self.queue.popleft()
            else:
                try:
                    result = method(parameters)
                except Exception, e:
                    command.defer.errback(e)
                    self.queue.popleft()
                else:
                    if result == 1:
                        self.queue.popleft()
                    elif result >= 2:
                        self.raw_bytes = result
                        self.setRawMode()

    def rawDataReceived(self, data):
        if self.queue:
            command = self.queue[0]
            if len(data) >= self.raw_bytes:
                rest = data[self.raw_bytes:]
                command.add_data(data[:self.raw_bytes])
                self.raw_bytes = 0
                self.setLineMode(rest)
            else:
                command.add_data(data)
                self.raw_bytes -= len(data)

    def connectionLost(self, reason):
        for command in self.queue:
            command.defer.errback(DisconnectedError(reason))
        self.queue = deque()


__all__ = ["MemcacheError", "NoSuchCommand", "ClientError", "ServerError",
           "DisconnectedError", "UnexpectedResponseError", "MemcacheProtocol"]
