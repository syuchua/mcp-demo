from typing import Dict, Any
from contextlib import AsyncExitStack

from .base import ServerConnection
from .stdio import StdioConnection
from .sse import SSEConnection
from .command import CommandConnection

def create_server_connection(server_config: Dict[str, Any], exit_stack: AsyncExitStack) -> ServerConnection:
    """创建服务器连接对象
    
    Args:
        server_config: 服务器配置
        exit_stack: 异步退出栈
        
    Returns:
        ServerConnection 实例
    """
    server_type = server_config.get("type", "stdio")
    
    if server_type == "stdio":
        return StdioConnection(server_config, exit_stack)
    elif server_type == "sse":
        return SSEConnection(server_config, exit_stack)
    elif server_type == "command":
        return CommandConnection(server_config, exit_stack)
    else:
        raise ValueError(f"不支持的服务器类型: {server_type}")