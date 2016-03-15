local lua_path = os.getenv("LUA_PATH")
if lua_path then
    package.path = string.format("%s;%s", package.path, lua_path)
end
local lua_cpath = os.getenv("LUA_CPATH")
if lua_cpath then
    package.cpath = string.format("%s;%s", package.cpath, lua_cpath)
end

local DataDump = require "dumper"
local sformat = string.format

local cfg_fn, doc_dir, alias_dir, script_dir, outdir = ...
local cfg_env = {}
local cfg_f = loadfile(cfg_fn, "t", cfg_env)
cfg_f()
local export_cfg = cfg_env.export
local global = {raw = {}, save = {}}
local copy = {}
local exts = {}
local save= global.save
local alias_deps = {}
local struct_deps = {}
local alias_fields = {}
local sheet_struct_deps = {}
local save_check_struct_deps = {}
local cfg_exts = {}

function tprint(t)
    local s = DataDump(t)
    print(s:sub(8, #s))
end

local function info(...)
    print(...)
end

function error(msg)
    info("ERROR: "..msg)
    os.exit(1)
end

assert = function(cond, msg)
    if not cond then
        error(msg)
    end
    return cond
end

local function _get_or_create_key(d, key)
    local ret = d[key]
    if not ret then
        ret = {}
        d[key] = ret
    end
    return ret
end

local function _merge_hash(d1, d2, msg)
    msg = msg or "重复的key"
    for k, v in pairs(d2) do
        assert(d1[k] == nil, sformat("%s:<%s>", msg, v))
        d1[k] = v
    end
end

local function _merge_array(l1, l2)
    for _, v in ipairs(l2) do
        table.insert(l1, v)
    end
end

-- py convert
info("*****************python convert******************")
local root_path = os.getenv("BIN_ROOT") or "./exporter"
local fp = io.popen(sformat("python %s/xlsparse.py %s %s", root_path, doc_dir, alias_dir))
while true do
    local data = fp:read("*l")
    if not data then
        break
    end
    local f = load("return "..data, "=(load)", "t")
    local ok, ret = pcall(f)
    if not ok or not ret then
        info(ok, ret, data)
        error("py convert error")
    end
    if ret.error then
        error(ret.error)
    end
    local fn = ret.filename
    if fn then
        global.raw[fn] = ret.data
        copy[fn] = f().data
        exts[fn] = ret.ext
        sheet_struct_deps[fn] = ret.struct_deps
    else
        if ret.alias_deps then
            alias_deps = ret.alias_deps
        end
        if ret.struct_deps then
            struct_deps = ret.struct_deps
        end
        if ret.alias_fields then
            for name, cfg in pairs(ret.alias_fields) do
                local d = {}
                for field, alias in pairs(cfg) do
                    d[alias] = field
                end
                alias_fields[name] = d
            end
        end
    end
end
fp:close()

-- lua prepare
info("*****************lua prepare******************")
local key_alias = {}
local cfg_keys = {}

local save_name_d = {}
local merge_name_d = {}
for cfg_idx, entry in ipairs(export_cfg) do
    local fn = entry[1]
    local snames = entry[2]
    local script = entry[3]
    local save_name = entry[4]
    info("lua prepare: "..save_name)
    assert(merge_name_d[save_name] == nil,
             "输出名字重复:"..save_name)
    save_name_d[save_name] = true
    local ext_d = entry[5]
    if next(ext_d) then
        cfg_exts[save_name] = ext_d
        local merge_name = ext_d.merge
        if merge_name then
            assert(save_name_d[merge_name] == nil, "merge name 重复") 
            merge_name_d[merge_name] = true
        end
    end

    if type(snames) == "string" then
        if snames == "*" then
            snames = {}
            for k, v in pairs(global.raw[fn]) do
                table.insert(snames, k)
            end
        else
            snames = {snames}
        end
    elseif snames == nil then
        error("sheet名称配置不能为nil")
        snames = {2015}
    end
    entry[2] = snames

    for _, i in ipairs(snames) do
        -- info(sformat("lua prepare: %s-%s", fn, i))
        local sheet = copy[fn]
        assert(sheet, "文件不存在！"..fn)
        local ext = exts[fn]
        if i ~= 2015 then
            sheet = sheet[i]
            assert(sheet, sformat("file:<%s> has no sheet:<%s>", fn, i))
            ext = ext[i]
            if ext.deps then
                save_check_struct_deps[save_name] = ext.deps
            end
            if ext.key_alias then
                local kd = _get_or_create_key(key_alias, save_name)
                _merge_hash(kd, ext.key_alias, "重复的key_alias")
            end
            if ext.typ == "d" then
                local ckd = _get_or_create_key(cfg_keys, save_name)
                for k, v in pairs(sheet) do
                    assert(not ckd[k], sformat("重复的key:<%s>", k))
                    ckd[k] = k
                end
            end
            if ext.key_check then
                local ckd = _get_or_create_key(cfg_keys, save_name)
                _merge_hash(ckd, ext.key_check, "重复的key")
            end
        else
            -- 整个文件导出不处理ext
            assert(not pre, "whole workbook export save name dup!")
        end
    end
end

global.alias2key = key_alias

-- check and convert depends
local check = cfg_keys
local convert = key_alias

local log_alias = nil
local log_idx = nil
local log_field = nil
local raw_assert = assert
assert = function(v, msg)
    local field = log_alias and log_alias[log_field] or log_field
    return raw_assert(v, ("check depends error, idx:<%s>, field:<%s> %s"):format(log_idx, field, msg))
end

local function _conv(check, convert, i, msg)
    if type(i) == "number" then
        if i == 0 then
            return 0
        end
        assert(check[i], msg)
        return i
    elseif type(i) == "string" then
		if i == "" then
            return ""
        end
        -- 兼容旧的写法
        if not convert then
            return assert(check[i], msg)
        end
        return assert(convert[i], msg)
    end
    error(msg)
end

local function _make_check_f(deps)
    -- 简单类型或者列表类型
    if type(deps) ~= "table" then
        local src = check[deps]
        local dst = convert[deps]
        return function(ckd)
            if type(ckd) == "table" then
                local ret = {}
                for n, i in ipairs(ckd) do
                    i = _conv(src, dst, i, sformat("list pos:<%d> value:<%s>", n, i))
                    table.insert(ret, i)
                end
                return ret
            else
                local tmp = _conv(src, dst, ckd, "simple error: "..(ckd or "nil")..type(ckd))
                return tmp
            end
        end
    -- 字典类型
    elseif deps.key or deps.value then
        local k_src, k_dst, v_src, v_dst
        if deps.key then
            k_src = check[deps.key]
            k_dst = convert[deps.key]
        end
        if deps.value then
            v_src = check[deps.value]
            v_dst = convert[deps.value]
        end
        return function(ckd)
            local ret = {}
            for k, v in pairs(ckd) do
                if k_src then
                    k = _conv(k_src, k_dst, k, "key error: "..k)
                end
                if v_src then
                    v = _conv(v_src, v_dst, v, "value error: "..v)
                end
                ret[k] = v
            end
            return ret
        end
    -- 指定列表位置
    else
        local check_d = {}
        for i, v in pairs(deps) do
            check_d[i] = {check[v], convert[v]}
        end
        return function(ckd)
            local ret = {}
            for i, v in ipairs(ckd) do
                local cd = check_d[i]
                if d then
                    v = _conv(cd[1], cd[2], v, ("list pos:<%d> value:<%s>"):format(i, v))
                end
                table.insert(ret, v)
            end
            return ret
        end
    end
end

local check_conf = {}
for name, cfg in pairs(alias_deps) do
    local d = {}
    for field, deps in pairs(cfg) do
        d[field] = _make_check_f(deps)
    end
    check_conf[name] = d
end

local function _check_struct_value_deps(value, cfg)
    for k, v in pairs(cfg) do
        local src = check[v]
        local dst = convert[v]
        value[k] = _conv(src, dst, value[k], "struct error: "..value[k])
    end
end

local function _check_alias_deps(sheet, check_fs)
    for idx, entry in pairs(sheet) do
        log_idx = idx
        for field, check_f in pairs(check_fs) do
            log_field = field
            if entry[field] then
                entry[field] = check_f(entry[field])
            end
        end
    end
end

local function _check_struct_deps(sheet, deps_cfg)
    for idx, entry in pairs(sheet) do
        log_idx = idx
        for field, field_cfg in pairs(deps_cfg) do
            log_field = field
            local value = entry[field]
            local flag, cfg = field_cfg[1], field_cfg[2]
            if flag == "s" then
                _check_struct_value_deps(value, cfg)
            elseif flag == "l" then
                for _, v in ipairs(value) do
                    _check_struct_value_deps(v, cfg)
                end
            elseif flag == "d" then
                for _, v in pairs(value) do
                    _check_struct_value_deps(v, cfg)
                end
            end
        end
    end
end

info("*****************check and convert depends******************")
for _, v in ipairs(export_cfg) do
    local save_name = v[4]
    local check_fs = check_conf[save_name]
    local struct_check_fs = save_check_struct_deps[save_name]
    log_alias = alias_fields[save_name]
    local fn = v[1]
    local snames = v[2]
    if #snames == 1 and snames[1] == 2015 then
        snames = {}
    end
    for _, sn in ipairs(snames) do
        local sheet = copy[fn][sn]
        info(("check depends, file:<%s>, sheet:<%s>"):format(fn, sn))
        if check_fs then
            _check_alias_deps(sheet, check_fs)
        end
        if struct_check_fs then
            _check_struct_deps(sheet, struct_check_fs)
        end
    end
end

assert = raw_assert

-- lua convert
info("*****************lua convert******************")
local last_save_type = {}
local post_convert_funcs = {}
local post_convert_names = {}
for cfg_idx, entry in ipairs(export_cfg) do
    local fn = entry[1]
    local snames = entry[2]
    local script = entry[3]
    local save_name = entry[4]

    if #snames == 1 and snames[1] == 2015 then
        snames = {}
    end
    local mod = setmetatable({}, {__index = _ENV})
    local convert_f = nil
    if script ~= nil then
        local f, msg = loadfile(sformat("%s/%s", script_dir, script), "t", mod)
        assert(f, sformat("load script error, cfg idx:<%d>, script:<%s>\n%s", cfg_idx, script, msg))
        local success, msg = xpcall(f, debug.traceback)  
        assert(success, sformat("run script error, cfg idx:<%d>, script:<%s>\n%s", cfg_idx, script, msg))
        --convert_f = assert(mod.convert, sformat("no convert func, cfg idx:<%d>, script:<%s>", cfg_idx, script))
        convert_f = mod.convert
    end
    for _, i in ipairs(snames) do
        info(sformat("lua convert: %s-%s", fn, i))
        local pre = save[save_name]
        local sheet = copy[fn]
        assert(sheet, "文件不存在！"..fn)
        local ext = exts[fn]
        if i ~= 2015 then
            sheet = sheet[i]
            assert(sheet, sformat("file:<%s> has no sheet:<%s>", fn, i))
            ext = ext[i]
        else
            assert(not pre, "whole workbook export save name dup!")
        end
        local t
        if convert_f then
            ext_data = {
                filename = fn,
                sheetname = i,
            }
            t = convert_f(sheet, global, ext_data)
        else
            t = sheet
        end
        if pre then
            assert(last_save_type[save_name] == ext.typ, "多表页类型不匹配")
            if ext.typ == "d" then
                _merge_hash(pre, t)
            elseif ext.typ == "l" then
                _merge_array(pre, t)
            end
        else
            save[save_name] = t
            last_save_type[save_name] = ext.typ
        end
    end
    if mod.post_convert then
        local last_script = post_convert_names[save_name]
        if not last_script then
            post_convert_names[save_name] = script
            table.insert(post_convert_funcs, {mod.post_convert, save_name})
        else
            assert(last_script == script, "不同脚本的post_convert方法对应了同个导出名字")
        end
    end
end

-- post convert
if #post_convert_funcs > 0 then
    info("*****************lua post convert******************")
end
for _, v in ipairs(post_convert_funcs) do
    info("lua post convert: ", v[2])
    save[v[2]] = v[1](save[v[2]], global)
end

-- ext process
local merge = {}
local no_save = {}
for k, v in pairs(cfg_exts) do
    if v.merge then
        local d = _get_or_create_key(merge, v.merge)
        table.insert(d, k)
    end 
    if v.no_save then
        table.insert(no_save, k)
    end
end
for _, i in ipairs(no_save) do
    save[i] = nil
end
for k, v in pairs(merge) do
    for _, i in ipairs(v) do
        local d = _get_or_create_key(save, k)
        d[i] = save[i]
        save[i] = nil
    end
end

if not outdir then
    info("check success!")
    os.exit(0)
end
-- tprint(save)

info("*****************save lua file******************")
local suffix = cfg_env.save_suffix or ""
for k, v in pairs(save) do
    local s = DataDump(v)
    --local fp = io.open(sformat("%s/%s", cfg_env.output_dir, k), "w")
    local fp = io.open(sformat("%s/%s%s", outdir, k, suffix), "w")
    fp:write(s)
    fp:close()
    info("save file: "..k)
end

local to_json_list = cfg_env.to_json_list
if to_json_list and #to_json_list > 0 then
    info("*****************save json file******************")
    local Json = require "json"
    for _, i in ipairs(to_json_list) do
        local fp = io.open(sformat("%s_json/%s.json", outdir, i), "w")
        local s = Json.encode(save[i])
        fp:write(s)
        fp:close()
    end
end
info("xls convert success!")
