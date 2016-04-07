#coding=utf8
from __future__ import unicode_literals
import os, sys

def _format_list(l):
    s = ",".join([tolua(i) for i in l])
    return "{%s}"%s

def _format_dict(d):
    l = []
    for k, v in d.iteritems():
        l.append("[%s]=%s"%(tolua(k), tolua(v)))
    s = ",".join(l)
    return "{%s}"%s

def _format_bool(b):
    return "true" if b else "false"

def _format_unicode(obj):
    temp = obj.encode("utf8")
    return _format_basic(temp)

def _format_basic(obj):
    if isinstance(obj, str):
        sep = "'" if obj.find('"') != -1 else '"'
        repl_sep = "'" if sep == '"' else '"'
        s = "%s%s%s"%(sep, obj.replace(sep, repl_sep).replace("\\", "\\\\").replace("\n", "\\n"), sep)
        return s
    if obj == None:
        return "nil"
    return str(obj)

def tolua(obj):

    if isinstance(obj, list):
        return _format_list(obj)
    elif isinstance(obj, dict):
        return _format_dict(obj)
    elif isinstance(obj, bool):
        return _format_bool(obj)
    elif isinstance(obj, unicode):
        return _format_unicode(obj)
    else:
        return _format_basic(obj)


if __name__ == "__main__":
    reload(sys)
    sys.setdefaultencoding("utf8")
    l = ["haha", "很", 1, 1.0]
    d = {
            "中国":l,
            "aaaa":"asdf'fdd'",
            "b":[1,2,3]
            }
    print d
    print tolua(d)
