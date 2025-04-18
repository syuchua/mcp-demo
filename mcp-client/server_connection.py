import os
import asyncio
import logging
import httpx
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List, NamedTuple
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp-client")

# 自定义工具类型
class Tool(NamedTuple):
    """自定义 Tool 类型"""
    name: str
    description: str = ""
    inputSchema: Dict = {}

class ServerConnection(ABC):
    """MCP 服务器连接的抽象基类"""
    
    def __init__(self, config: Dict[str, Any], exit_stack: AsyncExitStack):
        self.config = config
        self.exit_stack = exit_stack
        self.session = None
        
    @abstractmethod
    async def connect(self) -> Any:
        """连接到 MCP 服务器并返回客户端会话"""
        pass
    
    @abstractmethod
    async def list_tools(self) -> List[Tool]:
        """获取可用的工具列表"""
        pass
    
    @abstractmethod
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """调用工具"""
        pass

class StdioConnection(ServerConnection):
    """通过标准输入/输出连接到本地 MCP 服务器脚本"""
    
    def __init__(self, config: Dict[str, Any], exit_stack: AsyncExitStack):
        super().__init__(config, exit_stack)
        self.stdio = None
        self.write = None
        
    async def connect(self) -> ClientSession:
        """连接到本地 MCP 服务器脚本"""
        script_path = self.config["script"]
        
        # 解析脚本路径（如果是相对路径）
        if not os.path.isabs(script_path):
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                self.config.get("directory", "mcp-server"),
                script_path
            )
        
        # 确保脚本存在
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"找不到服务器脚本: {script_path}")
        
        # 根据文件扩展名确定命令
        is_python = script_path.endswith('.py')
        is_js = script_path.endswith('.js')
        
        if not (is_python or is_js):
            raise ValueError("服务器脚本必须是 .py 或 .js 文件")
        
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[script_path],
            env=None
        )
        
        logger.info(f"正在启动本地脚本 '{script_path}'")
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        return self.session
    
    async def list_tools(self) -> List[Tool]:
        """获取可用的工具列表"""
        if not self.session:
            raise RuntimeError("未连接到服务器")
            
        response = await self.session.list_tools()
        # 将 MCP 返回的工具转换为我们的自定义 Tool 类型
        return [Tool(
            name=tool.name,
            description=tool.description,
            inputSchema=tool.inputSchema
        ) for tool in response.tools]
    
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """调用工具"""
        if not self.session:
            raise RuntimeError("未连接到服务器")
            
        result = await self.session.call_tool(tool_name, args)
        return result

class SSEConnection(ServerConnection):
    """通过 HTTP/SSE 连接到远程 MCP 服务器"""
    
    def __init__(self, config: Dict[str, Any], exit_stack: AsyncExitStack):
        super().__init__(config, exit_stack)
        self.url = config["url"]
        self.api_key = config.get("api_key", "")
        self.sse_session = None
        self.write_func = None  # 添加写入函数
        self.tools_cache = None
    
    async def connect(self) -> Any:
        """连接到远程 MCP 服务器"""
        logger.info(f"正在连接到 SSE 服务器 '{self.url}'")
        
        # 修正: sse_client 返回 (session, write_function) 元组
        sse_transport = await self.exit_stack.enter_async_context(sse_client(self.url))
        self.sse_session, self.write_func = sse_transport
        
        # 使用 ClientSession 包装基础传输
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.sse_session, self.write_func))
        
        # 初始化会话
        await self.session.initialize()
        
        # 尝试获取工具列表
        try:
            tools_response = await self.session.list_tools()
            self.tools_cache = tools_response.tools
            logger.info(f"获取到高德工具列表，共 {len(self.tools_cache)} 个工具")
        except Exception as e:
            logger.warning(f"无法获取工具列表，使用预定义工具: {e}")
            self.tools_cache = self._get_default_tools()
        
        return self.session
    
    async def list_tools(self) -> List[Tool]:
        """获取可用的工具列表"""
        if not self.session:
            raise RuntimeError("未连接到服务器")
            
        if self.tools_cache is None:
            try:
                tools_response = await self.session.list_tools()
                self.tools_cache = tools_response.tools
            except Exception as e:
                logger.warning(f"获取工具列表失败: {e}")
                self.tools_cache = self._get_default_tools()
        
        # 将工具转换为我们的 Tool 类型
        return [Tool(
            name=tool.name,
            description=tool.description,
            inputSchema=tool.inputSchema
        ) for tool in self.tools_cache]
    
    def _get_default_tools(self):
        """返回高德默认工具列表"""
        from mcp import Tool as MCPTool
        
        default_tools = [
            MCPTool(
                name="geocode", 
                description="地理编码服务，将地址转换为经纬度坐标",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "需要转换的地址"
                        },
                        "city": {
                            "type": "string",
                            "description": "查询城市"
                        }
                    },
                    "required": ["address"]
                }
            ),
            MCPTool(
                name="weather", 
                description="天气查询服务，获取指定城市天气信息",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称或城市adcode"
                        }
                    },
                    "required": ["city"]
                }
            ),
            # 更多工具可以根据需要添加
        ]
        
        return default_tools
    
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """调用工具"""
        if not self.session:
            raise RuntimeError("未连接到服务器")
            
        try:
            # 现在使用 self.session 而不是 self.sse_session
            result = await self.session.call_tool(tool_name, args)
            return result
        except Exception as e:
            logger.error(f"SSE 工具调用失败: {e}")
            return {"error": f"工具调用失败: {str(e)}"}

class CommandConnection(ServerConnection):
    """通过本地命令启动 MCP 服务器"""
    
    def __init__(self, config: Dict[str, Any], exit_stack: AsyncExitStack):
        super().__init__(config, exit_stack)
        self.command = config["command"]
        self.working_dir = config.get("working_dir", ".")
        self.process = None
        self.stdio_connection = None
        
    async def connect(self) -> Any:
        """启动命令并连接到 MCP 服务器"""
        # 解析工作目录（如果是相对路径）
        if not os.path.isabs(self.working_dir):
            self.working_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                self.working_dir
            )
        
        # 确保工作目录存在
        if not os.path.exists(self.working_dir):
            raise FileNotFoundError(f"找不到工作目录: {self.working_dir}")
        
        # 解析命令
        cmd_parts = self.command.split()
        if cmd_parts[0] == "uvx":
            # uvicorn 运行器
            cmd_parts[0] = "uvicorn"
            cmd_parts.append("--reload")
        elif cmd_parts[0] == "npx":
            # Node.js 包运行器
            pass  # 默认命令即可
            
        logger.info(f"正在工作目录 '{self.working_dir}' 中启动命令 '{self.command}'")
        
        # 启动进程
        self.process = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.working_dir
        )
        
        # 注册进程清理
        self.exit_stack.push_callback(self._cleanup_process)
        
        # 等待服务器启动
        await asyncio.sleep(2)
        
        # 创建一个 SSE 连接以通信
        # 这里简化处理，假设命令启动的是一个 HTTP 服务
        # 实际应用中，这应该根据具体命令和配置判断
        sse_config = {
            "url": "http://localhost:8000",  # 假设命令在本地 8000 端口启动
            "api_key": ""
        }
        self.stdio_connection = SSEConnection(sse_config, self.exit_stack)
        return await self.stdio_connection.connect()
    
    def _cleanup_process(self):
        """清理进程资源"""
        if self.process and self.process.returncode is None:
            self.process.terminate()
            
    async def list_tools(self) -> List[Tool]:
        """获取可用的工具列表"""
        if not self.stdio_connection:
            raise RuntimeError("未连接到服务器")
            
        return await self.stdio_connection.list_tools()
    
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """调用工具"""
        if not self.stdio_connection:
            raise RuntimeError("未连接到服务器")
            
        return await self.stdio_connection.call_tool(tool_name, args)


def create_server_connection(server_config: Dict[str, Any], exit_stack: AsyncExitStack) -> ServerConnection:
    """创建服务器连接对象"""
    server_type = server_config.get("type", "stdio")
    
    if server_type == "stdio":
        return StdioConnection(server_config, exit_stack)
    elif server_type == "sse":
        return SSEConnection(server_config, exit_stack)
    elif server_type == "command":
        return CommandConnection(server_config, exit_stack)
    else:
        raise ValueError(f"不支持的服务器类型: {server_type}")