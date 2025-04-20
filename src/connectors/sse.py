#src/connectors/sse.py
from .base import ServerConnection, Tool
from typing import Dict, Any, List
import os
from contextlib import AsyncExitStack
from mcp import StdioServerParameters, ClientSession
from mcp.client.sse import sse_client
from ..log import logger

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