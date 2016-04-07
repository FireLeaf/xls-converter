#coding=utf8
import yaml

def _log(msg, struct, idx=None):
    return "struct:%s def error, idx:<%s>, %s"%(struct, idx, msg)

def parse(fn):
    deps = {}
    try:
        fp = open(fn, "r")
    except IOError:
        return {}
    struct_d = yaml.load(fp)
    fp.close()
    for name, cfg in struct_d.iteritems():
        assert isinstance(cfg, list), _log("elem def isn't list", name)
        assert name[:1].isupper(), _log("First must upper!", name)
        for idx, entry in enumerate(cfg):
            assert len(entry)==1, _log("field def error", name, idx)
            type_s = entry.values()[0]
            assert type_s in ["int", "float", "string"], _log("field type error:<%s>"%type_s, name, idx)
            entry[entry.keys()[0]] = type_s
    return struct_d

def _deps_log(msg, struct, field=None):
    return "struct:%s deps def error, field:<%s>, %s"%(struct, field, msg)

def parse_deps(fn, struct_d):
    try:
        fp = open(fn, "r")
    except IOError:
        return {}
    deps_d = yaml.load(fp)
    fp.close()
    if not deps_d:
        return {}
    for name, cfg in deps_d.iteritems():
        assert name in struct_d, _deps_log("struct没有定义", name)
        fields = [i.keys()[0] for i in struct_d[name]]
        for field, dep in cfg.iteritems():
            assert field in fields, _deps_log("字段没有定义", name, field)
    return deps_d

