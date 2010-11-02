'''
Make strings safe for use as ASCII filenames, while trying to preserve as much
meaning as possible.
'''

import re
import os
from math import ceil

from utils.unidecode.unidecoder import Unidecoder
udc = Unidecoder()

def ascii_text(orig):
    try:
        ascii = udc.decode(orig)
    except:
        if isinstance(orig, unicode):
            ascii = orig.encode('ascii', 'replace')
        ascii = orig.decode('utf-8',
                'replace').encode('ascii', 'replace')
    return ascii


def ascii_filename(orig, substitute='_'):
    ans = []
    orig = ascii_text(orig).replace('?', '_').replace(' ','_')
    for x in orig:
        if ord(x) < 32:
            x = substitute
        ans.append(x)
    return sanitize_file_name(''.join(ans), substitute=substitute)

def supports_long_names(path):
    t = ('a'*300)+'.txt'
    try:
        p = os.path.join(path, t)
        open(p, 'wb').close()
        os.remove(p)
    except:
        return False
    else:
        return True
    
_filename_sanitize = re.compile(r'[\xae\0\\|\?\*<":>\+/]')

def sanitize_file_name(name, substitute='_', as_unicode=False):
    '''
    Sanitize the filename `name`. All invalid characters are replaced by `substitute`.
    The set of invalid characters is the union of the invalid characters in Windows,
    OS X and Linux. Also removes leading and trailing whitespace.
    **WARNING:** This function also replaces path separators, so only pass file names
    and not full paths to it.
    *NOTE:* This function always returns byte strings, not unicode objects. The byte strings
    are encoded in the filesystem encoding of the platform, or UTF-8.
    '''
    if isinstance(name, unicode):
        name = name.encode('utf-8', 'ignore')
    one = _filename_sanitize.sub(substitute, name)
    one = re.sub(r'\s', ' ', one).strip()
    one = re.sub(r'^\.+$', '_', one)
    if as_unicode:
        one = one.decode('utf-8')
    one = one.replace('..', substitute)
    # Windows doesn't like path components that end with a period
    if one.endswith('.'):
        one = one[:-1]+'_'
    return one