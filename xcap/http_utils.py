import datetime
from typing import List, Optional, Union


def tokenize(header, foldCase=True):
    """Tokenize a string according to normal HTTP header parsing rules.

    In particular:
     - Whitespace is irrelevant and eaten next to special separator tokens.
       Its existence (but not amount) is important between character strings.
     - Quoted string support including embedded backslashes.
     - Case is insignificant (and thus lowercased), except in quoted strings.
        (unless foldCase=False)
     - Multiple headers are concatenated with ','

    NOTE: not all headers can be parsed with this function.

    Takes a raw header value (list of strings), and
    Returns a generator of strings.
    """
    tokens = set("()<>@,;:\\\"/[]?={} \t")  # Special separator characters
    ctls = set(chr(i) for i in range(0, 32))  # Control characters

    string = ",".join(header)
    start = 0
    cur = 0
    quoted = False
    qpair = False
    inSpaces = -1
    qstring = None

    for x in string:
        if quoted:
            if qpair:
                qpair = False
                qstring = qstring + string[start:cur-1] + x
                start = cur + 1
            elif x == '\\':
                qpair = True
            elif x == '"':
                quoted = False
                yield qstring + string[start:cur]
                qstring = None
                start = cur + 1
        elif x in tokens:
            if start != cur:
                if foldCase:
                    yield string[start:cur].lower()
                else:
                    yield string[start:cur]

            start = cur + 1
            if x == '"':
                quoted = True
                qstring = ""
                inSpaces = False
            elif x in " \t":
                if inSpaces is False:
                    inSpaces = True
            else:
                inSpaces = -1
                yield x  # Yield the special character directly as a string
        elif x in ctls:
            raise ValueError(f"Invalid control character: {ord(x)} in header")
        else:
            if inSpaces is True:
                yield ' '  # Yield space as a plain string
                inSpaces = False

            inSpaces = False
        cur = cur + 1

    if qpair:
        raise ValueError("Missing character after '\\'")
    if quoted:
        raise ValueError("Missing end quote")

    if start != cur:
        if foldCase:
            yield string[start:cur].lower()
        else:
            yield string[start:cur]


def quoteString(s):
    return '"%s"' % s.replace('\\', '\\\\').replace('"', '\\"')


# Helper function to parse comma-separated header values
def parse_list_header(header_value: Optional[str]) -> List[Optional[str]]:
    if header_value:
        parsed_etags = []
        for token in header_value.split(','):
            stripped_token = token.strip('"')  # Remove any surrounding quotes
            if stripped_token == '*':
                parsed_etags.append('*')  # Append '*' if it's a star
            else:
                parsed_etags.append(ETag.parse(tokenize([stripped_token])))  # Parse the ETag if it's not a star
        return parsed_etags
    return []


# Helper function to parse date-time headers like If-Modified-Since
def parse_datetime(value: str) -> Optional[datetime.datetime]:
    try:
        return datetime.datetime.strptime(value, "%a, %d %b %Y %H:%M:%S GMT")
    except ValueError:
        return None


class ETag(object):
    def __init__(self, tag, weak=False):
        self.tag = str(tag)
        self.weak = weak

    def match(self, other, strongCompare):
        # Sec 13.3.
        # The strong comparison function: in order to be considered equal, both
        #   validators MUST be identical in every way, and both MUST NOT be weak.
        #
        # The weak comparison function: in order to be considered equal, both
        #   validators MUST be identical in every way, but either or both of
        #   them MAY be tagged as "weak" without affecting the result.

        if not isinstance(other, ETag) or other.tag != self.tag:
            return False

        if strongCompare and (other.weak or self.weak):
            return False
        return True

    def __eq__(self, other):
        return isinstance(other, ETag) and other.tag == self.tag and other.weak == self.weak

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "Etag(%r, weak=%r)" % (self.tag, self.weak)

    def parse(tokens):
        tokens = tuple(tokens)
        if len(tokens) == 1 and isinstance(tokens[0], str):
            return ETag(tokens[0])

        if(len(tokens) == 3 and tokens[0] == "w"
           and tokens[1] == '/'):
            return ETag(tokens[2], weak=True)

        raise ValueError("Invalid ETag.")

    parse = staticmethod(parse)

    def generate(self):
        if self.weak:
            return 'W/'+quoteString(self.tag)
        else:
            return quoteString(self.tag)
