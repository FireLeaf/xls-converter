#coding=utf8
from __future__ import unicode_literals
import os, sys
import yaml

def make_key(bname, sname):
    return "%s.%s"%(bname, sname)

def _parse_sheets(conf):
    ret = []
    for k, v in conf.iteritems():
        if isinstance(v, str):
            assert v == "all", v
            ret.append(k)
        else:
            assert isinstance(v, list), v
            for i in v:
                ret.append(make_key(k, i))
    return ret

def _log(msg, fn, cfgname, xls=None, sheet=None):
    return "alias error, %s, file:<%s>, cfg:<%s>, xls:<%s>, sheet:<%s>"%(msg, fn, cfgname, xls, sheet)
        

def _parse_deps(depsd):
    return depsd


def parse(path):
    raw = {}
    field_alias = {}
    deps = {}
    cfg_defs = set()
    all_defs = set()
    sheet_defs = set()

    for fn in [os.path.join(path, i) for i in os.listdir(path)]:
        if not fn.endswith(".yaml"):
            continue
        fp = open(fn, "r")
        try:
            d = yaml.load(fp)
        except Exception, e:
            raise Exception("alias file:<%s> parse error, maybe tab, space..., msg:%s"%(fn, e))
        fp.close()
        for cfgname, item in d.iteritems():
            assert cfgname not in cfg_defs, _log("cfg dup", fn, cfgname)
            cfg_defs.add(cfgname)
            if ".sheets" not in item:
                continue
            sheets = item[".sheets"]
            del item[".sheets"]
            cfg = {}
            if ".deps" in item:
                deps[cfgname] = item[".deps"]
                cfg["deps"] = item[".deps"]
                del item[".deps"]
            raw[cfgname] = item
            cfg["alias"] = item
            def _process_all(cont):
                assert cont == "all",  _log("sheet def error", fn, cfgname, xls, cont)
                assert xls not in all_defs, _log("all def dup", fn, cfgname, xls, cont)
                all_defs.add(xls)
                assert xls not in sheet_defs, _log("all def after sheet", fn, cfgname, xls, cont)
                field_alias[xls] = cfg
            def _process_list(cont):
                assert isinstance(cont, list), _log("sheet def type error", fn, cfgname, xls, cont)
                for sh in cont:
                    assert xls not in all_defs, _log("sheet def after all", fn, cfgname, xls, cont)
                    key = make_key(xls, sh)
                    assert key not in field_alias, _log("sheet def after sheet", fn, cfgname, xls, cont)
                    sheet_defs.add(xls)
                    field_alias[key] = cfg
            for xls, cont in sheets.iteritems():
                if cont == "all":
                    _process_all(cont)
                else:
                    if isinstance(cont, str) or isinstance(cont, unicode):
                        cont = [cont,]
                    _process_list(cont)
    return raw, field_alias, deps

if __name__ == "__main__":
    parse("./alias")
