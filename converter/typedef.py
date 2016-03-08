#coding=utf8
import yaml

def _log(msg, struct, idx=None):
    return "struct:%s def error, idx:<%s>, %s"%(struct, idx, msg)

def parse(fn):
    deps = {}
    fp = open(fn, "r")
    struct_d = yaml.load(fp)
    fp.close()
    for name, cfg in struct_d.iteritems():
        assert isinstance(cfg, list), _log("elem def isn't list", name)
        assert name[:1].isupper(), _log("First must upper!", name)
        for idx, entry in enumerate(cfg):
            assert len(entry)==1, _log("field def error", name, idx)
            type_sl = entry.values()[0].split(",")
            if len(type_sl) == 2:
                deps[name] = {entry.keys()[0]: type_sl[1].strip()}
            assert type_sl[0] in ["int", "float", "string"], _log("field type error")
            entry[entry.keys()[0]] = type_sl[0]
    return struct_d, deps
