# mcp-demo
参考mcp官方文档糊了一个简单的实现，包含mcp-client和两个mcp-server，支持本地文件、命令和在线server(http/sse)调用

目前只适配了openai格式1，推荐搭配oneapi/newapi使用

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
  - 直接编辑mcp-client/config.yaml

开始使用：
```
python mcp-client/mcp_client.py
# 直接用uv也行
uv run mcp-client/mcp_client.py
```

命令行交互
客户端启动后，可以输入查询或使用以下命令：

  - !help - 显示帮助信息
  - !servers - 列出可用的服务器
  - !connect <server> - 连接到指定服务器
  - !models - 列出可用的 LLM 模型
  - !model <name> - 切换使用的模型
  - !debug <on/off> - 开启/关闭调试模式
  - !quit 或 !exit - 退出程序
示例查询
连接到美国天气服务：
```
!connect weather
查询旧金山天气预报
```

连接到高德地图服务：
```
!connect 高德
查询北京明天的天气
查询杭州西湖的位置
计算从清华大学到北京大学的步行路线
```

或者你也可以不用`!connect`命令切换，直接跟llm对话就行，支持让llm自己决定用哪个服务器的

支持的服务器和工具
内置服务器
    Weather Server

      get_forecast - 获取指定坐标的天气预报
      get_alerts - 获取指定州的天气警报

高德地图服务

    地理编码/逆地理编码
    天气查询
    路径规划（驾车/步行/骑行/公交）
    POI 搜索
    位置查询

自定义服务器

可以通过 MCP 框架创建自定义服务器并集成到客户端中。
