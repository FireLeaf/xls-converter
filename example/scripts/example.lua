
-- 范例
-- convert按照config文件指定的顺序调用
-- sheet是原始表数据
-- global中是一些全局数据，很少用到
-- pre是多张表公用一个导表程序时，上一次convert返回的，注意要自己手动合并
-- ext是一些扩展信息，例如表名
function convert(sheet, global, pre, ext)
    print("---------------------")
    print(ext)
    for k, v in pairs(global.raw) do
        print(k, v)
    end
    for k, v in pairs(global.save) do
        print(k, v)
    end
    return sheet
end

-- 所有的convert都结束了后，才执行post_convert，post的执行次序也按照config文件指定
-- save是之前convert后的存盘数据，这里可以进一步处理
-- global同上
function  post_convert(save, global)
    print(...)
    -- body
end
    