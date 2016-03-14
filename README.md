# xls-converter
convert xls or csv to lua/json file with check and custom rule
# 填写格式
**以下所有的格式在example目录下的xls文件中都可以找到例子**

excel第一行是类型行，填写规则是类型#标签1#标签2#标签n...
<br>第二行是列名,	填写人方便识别的列名
<br>第三行开始是数据行
<br>除第一二行外，任意行的首个单元格中的内容如果以“//”开头，则该行为注释行，不参与导表。
<br>所有的表名或者页名，只要名字以"_"开头，会被忽略掉，不参与导表。

# 类型
## 基本类型
- int 整数
- float 浮点数
- string 字符串
## 容器类型
- list<T> 数组类型
<br>各元素用空格隔开，例如list<int> 填写: 1 2 3
- dict<T,T> 字典类型
<br>key与value用":"隔开，各项用空格隔开，例如：key:value key2:value2

<br>*T是基本类型或者复合类型，但是dict的key不能为复合类型*

## 复合类型
比如坐标,包含x,y,z,可以定义一个单独的类型Point,在**struct.yaml**(导表excel目录下)里面,定义为

	Point:
	 x: float
	 y: float
	 z: float
    
定义完之后,可以在需要填写类型的地方直接填写Point,也可以用作list或者dict的值,比如list<Point>,dict<int, Point>
<br>*注意dict的key不能是复合类型,**dict<复合类型, 其他>是不支持的*

复合类型填表时候用竖线隔开每个值,例如 1.1|2.2|3.3，在list和dict中填写遵从list和dict的规范。

# 标签

- key：只能用在第一列，表示该列所填内容作为本条目的索引，不得重复，只支持int和string做key。例：int#key
- key_alias: 给key起的别名，只能在第二列，不得重复，只支持string类型，该列填写的别名，可以用作其他表的索引
- default：可以不填，有默认值，并且可以指定。例：int#default 或 int#default(3)
- ignore： 本列会被忽略，一般用于描述说明字段。
- index: 表示本列内容是索引了其他表的key或者key_alias，定义后程序员一定要做依赖检查，否则无法程序中无法使用
- raw: 只能用在第一列，表示整个表原样导出，导出后的的列按照别名定义输出，同时填写的单元按照表头定义类型输出，没填写的一律不输出，在lua脚本中获取为nil。这个标签的目的是为了应对一些复杂的表（例如树形结构的填写方式），将工作完全交给导表脚本，简化设计。

# 导表程序
导表的主程序是main.lua，使用py进行表的预处理，在lua中检查依赖，处理，输出最后的文件。<br>
启动main.lua的时候，向它传入必要的各种路径信息，参考example。<br>
主配置文件格式如下：

	export = {
	    {"物品测试.xls", "all", nil, "item_test", {}},
	    {"多页测试.xls", "Sheet1", nil, "page_test1", {merge="page_test"}},
	    {"多页测试.xls", "Sheet2", nil, "page_test2", {merge="page_test"}},
	    {"测试树形.xls", "Sheet1", "example.lua", "tree_test", {}},
	    {"测试树形.xls", "Sheet2", nil, "tindex_test", {}},
	}

每行的定义：{表，页，导表程序，输出文件名，附加信息}<br>
页可以是s1, [s1,s2], "all", 分别代表一页, 部分页，全部页<br>
导表程序可以是nil，则按照默认规则输出。<br>
附加信息项定义如下：

- merge=name， 最终输出时将多个名字放入到name的table下，统一输出名字为name的文件。比如上面的例子中，最终会输出：

	
		page_test = {
			page_test1 = {...},
			page_test2 = {...},
		}

# 导表脚本
导表脚本中可以定义两个global函数：<br>

	function convert(sheet, global, ext)
	function post_convert(save, global)

convert负责第一遍顺序处理，它必须return一个table，作为save的数据，参数如下：


- sheet是本次调用处理的表内容
- global中传递了一些全局信息
	- save，已经添加到save中的数据。
	- alias2key, excel中定义的key_alias和key的索引表，方便查询。
	- raw，所有的原始表信息。
- ext本次调用的一些附加信息，比如sheet所在的原始文件名，页名。

return的数据，会以配置表中的存盘名字保存在global.save中，如果不return，则为空。<br>
注意，convert的处理对象是文件中的页，多个页配置了同个导表程序会依次产生调用，并且最终的结果会自动合并（根据文件是table还是array）。

post_convert负责第二次处理，此时，所有的表按照config的配置已经处理过了，此时的save参数代表了合并后的所有存盘名字下的数据集合，global含义如上。返回的table作为最终存盘数据。<br>
此时可以对最终的存盘结果做调整，甚至可以向global.save中删除添加表项。

# 别名和依赖定义
格式：
	
	cfg_name:
		.sheets: 
			file_name: sheet_name
		.deps:
			alias_name: deps_cfg_name
		编号: id
		原名: alias_name
		
范例：

	page_test:
	    .sheets:
	        多页测试.xls: Sheet2
	    .deps:
	        item: item_test
	        item_list: item_test
	        item_dict:
	            key: item_test
	            value: item_test
	    物品集合: itemset
	    测试索引: id
	    物品: item
	    物品列表: item_list
	    物品字典: item_dict
	    数目: num


采用yaml格式，并且要明确以yaml作为文件后缀名。整个alias目录下的所有yaml都会被读取。<br>
每个配置有个名字cfg\_name, 这个名字最好要跟主配置文件里的存盘名字一致，这样才能用来做依赖检查。<br>
每个配置中要有个.sheets的key，存放该配置应用于哪些sheet。<br>
别名的定义就是key:value的键值对。<br>
.sheets的value是一个列表，每个元素是一个字典，例如，文件1：[ 表1，表2 ], 当文件中所有的表都应用时，可以这样指定，文件:all。<br>
.deps定义了表中字段的依赖关系，alias\_name: deps\_cfg\_name, 其中deps\_cfg\_name就是对应依赖表的config.lua中的导出存盘名字。<br>
检查依赖的流程如下：

1. xls文件的每个页经过py读取，进行别名转换，输出给main.lua脚本
1. lua中进行预处理，把所有savename（存盘名字）相同的表的key和key_alias的字段进行合并，并保存在savename对应的table中，即key_check。
1. 根据config配置的savename查询别名定义里是否同名的配置项，如果有则看别名定义里是否有改别名的deps配置，如果有，则根据配置依赖的deps\_cfg\_name在key_check的table中查询该字段的value是否存在。
1. 里面有个隐藏的规则是，如果字段为字符串，则首先将该字段转换成对应的key的值。
2. 注意！！！别名的配置项名字只有在本别名定义中有deps字段时才需要与config中的导出名字一致，这样框架才能根据名字找到需要检查的字段。而依赖项（deps\_cfg\_name)的字段，就是config里的导出名字。

# 复合类型的定义和依赖
格式：
	
	Example:
	    - id: int， item
	    - num: int
	    - rate: float
复合类型的字段类型一定是基础类型，如果某字段有依赖的话，用逗号隔开输入依赖项的名字。
