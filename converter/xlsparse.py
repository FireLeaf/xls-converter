#coding=utf8
from __future__ import unicode_literals
import sys
import os
import shutil
import re
import xlrd
import yaml
import alias
import typedef
import lseri

reload(sys)
sys.setdefaultencoding("utf8")
import codecs
def cp65001(name):
    if name.lower() == "cp65001":
        return codecs.lookup("utf8")
codecs.register(cp65001)

g_error_l = []
g_alias_d = None
g_alias_deps = None
g_struct_deps = {}
g_sheet_struct_deps = {}

fp_log = None
def fprint(msg):
    global fp_log
    if not fp_log:
        fp_log = open("log.txt", "w")
    fp_log.write(msg)
    fp_log.write(os.linesep)
    fp_log.flush()

output_list = []
def output(msg):
    output_list.append(msg)
    return

def flush_output():
    s = lseri.tolua(output_list)
    #fprint(s)
    sys.stdout.write(s)
    sys.stdout.flush()

def error(msg):
    s = lseri.tolua({"error":msg})
    sys.stdout.write(s)
    sys.stdout.flush()
    sys.exit(1)

def print_exc():
    import traceback
    traceback.print_exc()

# 基础数据类型：int, float, string
_bool_d = {"true":True,"false":False,"1":True,"0":False,"1.0":True,"0.0":False}
def _conv_bool(s):
    return _bool_d[str(s).lower()]
basictype_convert_tbl = {
        "int":int,
        "float":float,
        "bool":_conv_bool,
        "string":lambda s:str(s).encode("utf8"),
        }
# 自定义struct
g_struct_d = None

# 容器数据类型: list<T>, dict<T1, T2>
CONTAINER_RE = re.compile("^(list|dict)<(.+?)(?:,\s*(.+?))??>$")
#m = CONTAINER_RE.match(u"list<int>")
#print(m.groups())

def find_struct_deps(type_s):
    if type_s in basictype_convert_tbl:
        return None
    if type_s in g_struct_d:
        if type_s in g_struct_deps:
            return ["s", g_struct_deps[type_s]]
        else:
            return None
    m = CONTAINER_RE.match(type_s)
    sg = m.groups()
    if sg[0] == "list":
        if sg[1] in g_struct_deps:
            return ["l", g_struct_deps[sg[1]]]
    elif sg[0] == "dict":
        if sg[2] in g_struct_deps:
            return ["d", g_struct_deps[sg[2]]]
    return None

def get_basic_or_struct_cf(s):
    if s in basictype_convert_tbl:
        return basictype_convert_tbl[s]
    if s not in g_struct_d:
        return None
    cfg = g_struct_d[s]
    def cf(cont):
        if cont == "":
            return None
        l = cont.split("|")
        assert len(l)==len(cfg), cont
        ret = {}
        for idx, v in enumerate(l):
            ret[cfg[idx].keys()[0]] = basictype_convert_tbl[cfg[idx].values()[0]](v)
        return ret
    return cf

def make_convert_func(type_s):
    cf = get_basic_or_struct_cf(type_s)
    if cf:
        return cf
    m = CONTAINER_RE.match(type_s)
    sg = m.groups()
    assert len(sg) == 3, "类型解析错误"
    if sg[0] == "list":
        assert not sg[2], "list定义有误"
        typ = sg[1]
        f = get_basic_or_struct_cf(typ)
        assert f, "list元素类型定义有误:%s"%type_s
        def cf(s):
            # xls单元格会默认把数字格式转换成float
            if typ == "int" and isinstance(s, float):
                s = str(int(s))
            return [f(i) for i in s.split()]
        return cf
    elif sg[0] == "dict":
        k_f = basictype_convert_tbl[sg[1]]
        assert k_f, "dict key类型定义有误%s"%type_s
        v_f = get_basic_or_struct_cf(sg[2])
        assert v_f, "dict value类型定义有误:%s"%type_s
        def cf(s):
            d = {}
            for i in s.split():
                l = i.split(":")
                d[k_f(l[0])] = v_f(l[1])
            return d
        return cf
    raise Exception("未定义类型:%s"%type_s)

TYPE_DEFAULT_RE = re.compile("^default(?:\((.*)\))?$")
#m = TYPE_DEFAULT_RE.match("default")
#print m.group(2)
TAG_KEY_RE = re.compile("^key(?:\((.*)\))?$")

type_default_tbl = {
        "int":0,
        "float":0.0,
        "string":"",
        "bool":False,
        }
def parse_type_tag(ncol, tag_sl, type_s, conv_f):
    ret = {}
    def _key_f():
        assert ncol == 0, "key必须是第一列"
        assert type_s == "int" or type_s == "string", "类型:<%s>不能做key"%type_s
        ret["key"] = True
    def _ignore_f():
        ret["ignore"] = True
    def _raw_f():
        ret["raw"] = True
    def _key_alias_f():
        assert ncol == 1, "key_alias必须是第二列"
        ret["key_alias"] = True
    def _index_f():
        ret["index"] = True
    def _defaultnil_f():
        ret["default"] = None   
    tag_fs = {
        #"key":_key_f,
        "ignore":_ignore_f,
        "raw":_raw_f,
        "key_alias":_key_alias_f,
        "index":_index_f,
        "defaultnil": _defaultnil_f,
    }
    
    for tag_s in tag_sl:
        if tag_s in tag_fs:
            #assert tag_s in tag_fs, "标签填写错误:<%s>"%tag_s
            tag_fs[tag_s]()
            continue
        # default 处理
        m = TYPE_DEFAULT_RE.match(tag_s)
        if m:
            assert "default" not in ret, "重复设置default"
            default_val = m.group(1) 
            if not default_val and type_s in type_default_tbl:
                default_val = type_default_tbl[type_s]
            else:
                default_val = conv_f(default_val if default_val else "")
            ret["default"] = default_val
            continue

        # key 处理
        m = TAG_KEY_RE.match(tag_s)
        if m:
            assert ncol == 0, "key必须是第一列"
            assert type_s == "int" or type_s == "string", "类型:<%s>不能做key"%type_s
            d = {}
            key_attr = m.group(1)
            if key_attr:
                assert key_attr == "incr", "key的属性只能是incr"
                assert type_s == "int", "incr key只能是int类型"
                d["incr"] = True
            ret["key"] = d
            continue
        raise Exception(tag_s)
    # 容器类型list和dict默认就是空
    if get_basic_or_struct_cf(type_s) == None and "default" not in ret:
        ret["default"] = conv_f("")

    assert not ("key" in ret and "default" in ret), "key类型不能设置default"
    assert not ("key" in ret and "ignore" in ret), "key类型不能设置ignore"
    assert not ("key" in ret and "index" in ret), "key类型不能设置index"
    return ret

def open_xls(filename):
    return xlrd.open_workbook(filename)

# 返回的是下标
def _find_dup_in_list(l):
    d = {}
    for n, i in enumerate(l):
        if i in d:
            return n
        d[i] = 1
    return -1

def _num2colname(n):
    def _n2chr(i):
        return chr(65+i)
    if n < 26:
        return _n2chr(n)
    elif n < 26*27:
        return _n2chr(n/26-1) + _n2chr(n%26)
    return str(n)

EXPORT_ALL_RE = re.compile("^all(?:-\[(.*)\])?$")
def _parse_export(s):
    if not s:
        return None, None
    m = EXPORT_ALL_RE.match(s)
    if m:
        exclude = m.group(1)
        if not exclude:
            return "all", []
        else:
            return "all", [i.strip() for i in exclude.split(",")]
    else:
        return None, None


def sheet_to_dict(sheet, alias_d):
    conv_funcs = []
    tags = []
    struct_deps_l = []
    struct_deps_d = {}
    alias_deps = alias_d.get("deps", {}) if alias_d else {}
    export_type = alias_d.get("export") if alias_d else None
    alias_d = alias_d.get("alias") if alias_d else None
    try:
        # 处理第一行，类型
        end_col = None
        for n, i in enumerate(sheet.row_values(0)):
            end_col = n + 1
            # 允许类型列填空，意味该列忽略
            if n > 0 and i == "" :
                end_col = n
                break
            type_sl = i.split("#")
            conv_f = make_convert_func(type_sl[0])
            conv_funcs.append(conv_f)
            tags.append(parse_type_tag(n, type_sl[1:], type_sl[0], conv_f))
            struct_deps_l.append(find_struct_deps(type_sl[0]))
    except Exception, e:
        raise Exception("sheet:<%s>类型行%s列填写错误, 内容:<%s>, msg:%s"%(sheet.name, _num2colname(n), i, e))

    name_row = sheet.row_values(1,end_colx=end_col)
    dup_idx = _find_dup_in_list(name_row)
    if dup_idx != -1:
        raise Exception("sheet:<%s>列名重复:<%s>"%(sheet.name, name_row[dup_idx]))
    col_names = []
    if alias_d:
        export_flag, export_exmsg = _parse_export(export_type)
        export_all = export_flag == "all"
        for name in name_row:
            col_names.append(alias_d.get(name, name if export_all and name not in export_exmsg else None))
    else:
        col_names = name_row

    for n, i in enumerate(col_names):
        if i and struct_deps_l[n]:
            struct_deps_d[i] = struct_deps_l[n]

    check_tag_f = lambda x,s: True if s in x else False
    raw_flag = check_tag_f(tags[0],"raw")
    raw_keys = {}
    key_flag = check_tag_f(tags[0],"key")
    key_incr_flag = check_tag_f(tags[0]["key"], "incr") if key_flag else False
    last_key = [0,]
    key_alias_flag = check_tag_f(tags[1],"key_alias") if len(tags) > 1 else False
    ret = {} if key_flag and not raw_flag else []
    key_alias_d = {} if key_alias_flag else None
    for nrow in xrange(2, sheet.nrows):
        row = sheet.row_values(nrow, end_colx=end_col)
        row_d = {}
        try:
            # 注释行忽略
            if isinstance(row[0], unicode) and row[0].startswith("//"):
                continue
            row_key = None
            row_key_alias = None
            for ncol, value in enumerate(row):
                tag = tags[ncol]
                col_name = col_names[ncol]
                if not col_name:
                    # key和key_alias列走流程可以不导出
                    is_key = key_flag and "key" in tag
                    is_alias = key_alias_flag and "key_alias" in tag
                    if not is_key and not is_alias:
                        continue
                else:
                    if "index" in tag and col_name not in struct_deps_d:
                        if alias_d and col_name not in alias_deps:
                            raise Exception("%s填写了index但没有定义依赖"%col_name)
                cv = None
                if "ignore" in tag:
                    continue
                # 如果该格子不填，获取的是空串
                if value == "" and "default" in tag: 
                    cv = tag["default"]
                else:
                    # raw key 列可以为空
                    if not raw_flag:
                        assert value != "", "表项为空"
                        cv = conv_funcs[ncol](value)
                    else:
                        if value != "":
                            cv = conv_funcs[ncol](value)
                if ncol == 0 and "key" in tag:
                    row_key = cv
                if ncol == 1 and "key_alias" in tag:
                    row_key_alias = cv
                if col_name:
                    row_d[col_name] = cv
            def _check_key(check_d):
                # 检查key是否重复
                # raw表，key列可能是None，不用检查了
                if raw_flag and row_key == None:
                    return
                assert row_key not in check_d, "key列内容重复, 行:%s,值:%s"%(nrow+1, row_key)
                check_d[row_key] = row_d
                if key_incr_flag:
                    assert row_key == last_key[0] + 1, "incr key 不连续:%d"%row_key
                    last_key[0] = row_key
                if key_alias_flag:
                    assert row_key_alias not in key_alias_d, "key_alias列内容重复, 行:%s,值:%s"%(nrow+1, row_key_alias)
                    key_alias_d[row_key_alias] = row_key
            if isinstance(ret, dict):
                _check_key(ret)
            else:
                if raw_flag and key_flag:
                    _check_key(raw_keys)
                ret.append(row_d)
        except Exception, e:
            # print_exc()
            raise Exception("sheet:%s, cell:<行%s-列%s>, %s"%(sheet.name, nrow+1, _num2colname(ncol), e))
    return ret, struct_deps_d, key_alias_d


def get_alias_conf(fn, shname):
    if fn in g_alias_d:
        return g_alias_d[fn]
    key = alias.make_key(fn, shname)
    return g_alias_d.get(key)

def convert_xls(filename):
    try:
        wb = open_xls(filename)
        ret = {}
        ext = {}
        for sheet in wb.sheets():
            if sheet.name.startswith("_"):
                continue
            if sheet.nrows < 2:
                continue
            data, deps_d, key_alias_d = sheet_to_dict(sheet, get_alias_conf(filename, sheet.name))
            ret[sheet.name] = data
            d = {}
            if len(deps_d) > 0:
                d["deps"] = deps_d
            d["typ"] = "l" if type(data) == type([]) else "d"
            d["key_alias"] = key_alias_d
            if d["typ"] == "l" and key_alias_d:
                tmp = {}
                for k, v in key_alias_d.iteritems():
                    tmp[v] = k
                d["key_check"] = tmp
            ext[sheet.name] = d
        return ret, ext
    except Exception, e:
        # print_exc()
        error("file:%s, error: %s"%(filename, e))

def run_dir(path):
    os.chdir(path)
    files = []
    def visit(arg, dirname, names):
        for name in names:
            if name.endswith(".xls") and not name.startswith("_"):
                files.append(os.path.relpath(os.path.join(dirname, name), "."))
    os.path.walk(".", visit, None)
    for fn in files:
        fn = fn.replace(os.sep, "/")
        data, ext = convert_xls(fn)
        out = {}
        out["filename"] = fn
        out["data"] = data
        out["ext"] = ext
        #if len(deps_d) > 0:
            #out["struct_deps"] = deps_d
        output(lseri._tolua(out))
    
if __name__ == "__main__":
    fpath = sys.argv[1]
    import platform
    if platform.system() == "Windows":
        fpath = fpath.decode("gbk")
    else:
        fpath = fpath.decode("utf8")
    try:
        alias_raw, g_alias_d, g_alias_deps = \
                alias.parse(fpath, sys.argv[2])
        if len(alias_raw) > 0:
            output(lseri._tolua({"alias_fields":alias_raw}))
        if len(g_alias_deps) > 0:
            output(lseri._tolua({"alias_deps":g_alias_deps}))
        g_struct_d = typedef.parse(os.path.join(fpath, "struct.yaml"))
        g_struct_deps = typedef.parse_deps(os.path.join(sys.argv[2], "struct_deps.yaml"), g_struct_d)
        if len(g_struct_deps) > 0:
            output(lseri._tolua({"struct_deps":g_struct_deps}))
    except Exception, e:
        error(str(e))
    run_dir(fpath)
    flush_output()
