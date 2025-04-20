import asyncio
import os
import json
from typing import Dict, Any, List
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from .base import ServerConnection, Tool
from ..log import logger

class CommandConnection(ServerConnection):
    """通过命令启动 MCP 服务器并连接"""
    
    def __init__(self, config: Dict[str, Any], exit_stack: AsyncExitStack):
        super().__init__(config, exit_stack)
        self.command = config.get("command")
        self.args = config.get("args", [])
        self.cwd = config.get("cwd", ".")
        self.env = config.get("env", {})
        self.session = None
    
    async def connect(self) -> ClientSession:
        """连接到服务器"""
        if not self.command:
            raise ValueError("配置中缺少命令")

        # 解析工作目录
        if not os.path.isabs(self.cwd):
            self.cwd = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                self.cwd
            )
        
        logger.info(f"正在工作目录 '{self.cwd}' 中启动命令 '{self.command}'")
        
        # 创建完整的环境变量
        full_env = os.environ.copy()
        if self.env:
            full_env.update(self.env)
        
        # 使用 stdio_client 创建连接
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=full_env,
            cwd=self.cwd
        )
        
        try:
            # 使用 MCP 库的 stdio_client 创建连接
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
            
            # 初始化会话
            await self.session.initialize()
            return self.session
        except Exception as e:
            logger.error(f"连接到命令服务器时出错: {e}")
            raise
    
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