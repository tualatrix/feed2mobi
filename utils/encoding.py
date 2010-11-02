import codecs

_ENCODING_ALIASES = dict({})
_ENCODING_ALIASES.update([])

def encoding_exists(encoding, _aliases=_ENCODING_ALIASES):
    """Returns ``True`` if encoding is valid, otherwise returns ``False``"""
    try:
        codecs.lookup(resolve_encoding(encoding, _aliases))
    except LookupError:
        return False
    return True

def resolve_encoding(alias, _aliases=_ENCODING_ALIASES):
    """Return the encoding the given alias maps to, or the alias as passed if
    no mapping is found.
    """
    return _aliases.get(alias.lower(), alias)
