--[[
格式：
{表，页，导表程序，输出文件名，附加信息}
页可以是s1, [s1,s2], "*", 分别代表一页, 部分页，全部页
--]]
export = {
    {"物品测试.xls", "*", nil, "item_test", {}},
    {"多页测试.xls", "Sheet1", nil, "page_test1", {merge="page_test"}},
    {"多页测试.xls", "Sheet2", nil, "page_test2", {merge="page_test"}},
    {"测试树形.xls", "Sheet1", nil, "tree_test", {}},
    {"测试树形.xls", "Sheet2", nil, "tindex_test", {}},
    --{"范例.xls", "页面1", "example.lua", "example", {}},
}

-- save_suffix = ".lua"
--to_json_list = { "weapon_types", "role", "hit_effects", "barrier","profession","monster","fly_items","pet","common_battle","hit_effects"}
