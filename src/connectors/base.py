# src/connectors/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack
from ..llm.base import LLMProvider
#from mcp.types import TextContent, Tool, Resource, ResourceTemplate, Prompt

class Tool:
    """表示 MCP 工具的类"""
    
    def __init__(self, name: str, description: str = "", inputSchema: Dict = {}):
        self.name = name
        self.description = description
        self.inputSchema = inputSchema

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