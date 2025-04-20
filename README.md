# mcp-demo
参考mcp官方文档糊了一个简单的实现，包含mcp-client和多个mcp-server，支持本地文件搜索、系统控制、命令执行和在线API调用。

推荐搭配oneapi/newapi使用

环境配置
  - Python3.12（本地用的这个，其他没测试过，估计3.11,3.10也问题不大）
  - uv，包管理工具，好用！

克隆仓库：
```
git clone https://github.com/syuchua/mcp-demo.git
cd mcp-demo
```

安装依赖：
```
uv pip install -e .
```

配置你的API_KEY
  - （可选）创建.env文件，添加OPENAI_API_KEY="your-api-key"
  - 直接编辑src/config/default_config.yaml

开始使用：
```
python main.py
# 直接用uv也行
uv run main.py
```


## 命令行交互

客户端启动后，可以输入查询或使用以下命令：

  - `!help` - 显示帮助信息
  - `!servers` - 列出可用的服务器
  - `!connect <server>` - 连接到指定服务器
  - `!models` - 列出可用的LLM模型
  - `!model <name>` - 切换使用的模型
  - `!debug <on/off>` - 开启/关闭调试模式
  - `!quit` 或 `!exit` - 退出程序

## 支持的服务器和工具

### 美国天气服务器 (weather)
- `get_forecast` - 获取指定坐标的天气预报
- `get_alerts` - 获取指定州的天气警报

### 高德地图服务器 (高德)
- 地理编码/逆地理编码
- 天气查询
- 路径规划（驾车/步行/骑行/公交）
- POI搜索
- 位置查询

### 本地文件搜索服务器 (everything)
- `search` - 基于Everything搜索引擎的文件查找功能
- 支持各种搜索语法，包括通配符、正则表达式和高级过滤

### 系统工具服务器 (system_tools)
- `execute_program` - 执行指定程序或应用
- `open_app` - 打开常用应用程序（QQ、微信、浏览器等）
- `send_qq_message` - 发送QQ消息
- `list_running_processes` - 列出当前运行的进程
- `kill_process` - 结束指定进程
- `create_file` - 创建并写入文件
- `read_file` - 读取文件内容
- `list_files` - 列出目录中的文件
- `delete_file` - 删除文件
- `get_working_directory` - 获取当前工作目录
- `run_python_code` - 执行Python代码并返回结果

## 示例查询

### 天气查询
查询旧金山天气预报 纽约是否有暴风雨预警

### 地图服务
查询北京明天的天气 查询杭州西湖的位置 计算从清华大学到北京大学的步行路线

### 文件查找
查找所有PDF文件 搜索最近修改的Python代码 查找名称包含"报告"的Excel文件

### 文件/应用程序操作
打开记事本 
创建一个helloworld.py文件并写入Python代码 
查看当前目录下的文件 
执行Python代码计算1到100的和
将视频D:\demo.mp4转换为MP3音频 合并两个视频文件 从视频中提取5秒的片段创建GIF

## 智能服务器选择

无需手动切换服务器，直接提问即可！系统会根据查询内容自动选择最合适的服务器处理您的请求。

## 自定义服务器

可以通过修改配置文件添加自定义服务器。

## 许可证

MIT License
