#src/connectors/stdio.py
from .base import ServerConnection, Tool
from typing import Dict, Any, List, Optional
import os
from contextlib import AsyncExitStack
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client
from ..log import logger

class StdioConnection(ServerConnection):
    """通过标准输入/输出连接到本地 MCP 服务器脚本或命令"""
    
    def __init__(self, config: Dict[str, Any], exit_stack: AsyncExitStack):
        super().__init__(config, exit_stack)
        self.stdio = None
        self.write = None
        
    async def connect(self) -> ClientSession:
        """连接到本地 MCP 服务器脚本或命令"""
        # 检查是脚本模式还是命令模式
        if "script" in self.config:
            # 脚本模式：运行 Python 或 JS 文件
            return await self._connect_script()
        elif "command" in self.config:
            # 命令模式：直接执行命令行命令
            return await self._connect_command()
        else:
            raise ValueError("配置必须包含 'script' 或 'command' 字段")
    
    async def _connect_script(self) -> ClientSession:
        """连接到本地脚本"""
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
            env=self._prepare_env()
        )
        
        logger.info(f"正在启动本地脚本 '{script_path}'")
        
        return await self._establish_connection(server_params)

    async def _connect_command(self) -> ClientSession:
        """连接到命令行命令"""
        command = self.config["command"]
        args = self.config.get("args", [])
        cwd = self.config.get("cwd")
        
        # 将工作目录解析为绝对路径
        if cwd and not os.path.isabs(cwd):
            cwd = os.path.join(os.path.dirname(os.path.dirname(__file__)), cwd)
        
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=self._prepare_env(),
            cwd=cwd
        )
        
        logger.info(f"正在执行命令 '{command}' 参数: {args}")
        
        return await self._establish_connection(server_params)
        
    async def _establish_connection(self, server_params: StdioServerParameters) -> ClientSession:
        """建立与子进程的连接"""
        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
            
            await self.session.initialize()
            return self.session
        except Exception as e:
            logger.error(f"建立连接时出错: {e}")
            if isinstance(e, OSError) and e.errno == 2:  # 文件不存在
                logger.error(f"命令不存在或不在PATH中: {server_params.command}")
            raise
    
    def _prepare_env(self) -> Optional[Dict[str, str]]:
        """准备环境变量"""
        env = None
        if "env" in self.config:
            # 基于当前环境变量创建新环境
            env = os.environ.copy()
            # 合并配置中的环境变量
            env.update(self.config["env"])
        return env
    
    async def list_tools(self) -> List[Tool]:
        """获取可用的工具列表"""
        if not self.session:
            raise RuntimeError("未连接到服务器")
            
        response = await self.session.list_tools()
        
        # 将 MCP 返回的工具转换为我们的自定义 Tool 类型
        tools = []
        for tool in response.tools:
            # 检查描述长度并截断
            description = tool.description
            if len(description) > 1000:  # 留些余量，避免边界情况
                logger.warning(f"工具 '{tool.name}' 描述过长 ({len(description)} 字符)，已截断至 1000 字符")
                description = description[:997] + "..."
            
            # 确保 inputSchema 是有效的 JSON Schema
            schema = tool.inputSchema
            if not isinstance(schema, dict):
                schema = {}
            
            # 确保 schema 有 type 字段
            if "type" not in schema:
                schema = {
                    "type": "object", 
                    "properties": schema,
                    "required": []
                }
            
            tools.append(Tool(
                name=tool.name,
                description=description,
                inputSchema=schema
            ))
        
        return tools
    
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """调用工具"""
        if not self.session:
            raise RuntimeError("未连接到服务器")
            
        result = await self.session.call_tool(tool_name, args)
        return result