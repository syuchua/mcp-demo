import os
from typing import Dict, List, Any
import pathlib

def find_server_instances(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """从配置中获取服务器实例
    
    Args:
        config: 配置字典
        
    Returns:
        服务器实例字典，键为服务器名称，值为服务器配置
    """
    servers = {}
    
    # 检查配置中是否有预定义的服务器实例
    if "servers" in config and "instances" in config["servers"]:
        for instance in config["servers"]["instances"]:
            servers[instance["name"]] = instance
    
    # 如果没有预定义实例或实例为空，尝试从目录查找
    if not servers:
        file_servers = find_server_files(config["servers"].get("directory", "../mcp-server"))
        for name, path in file_servers.items():
            servers[name] = {
                "name": name,
                "type": "stdio",
                "script": path,
                "description": f"从文件发现的服务器: {name}"
            }
    
    return servers

def find_server_files(directory: str) -> Dict[str, str]:
    """在指定目录中查找所有可用的 MCP 服务器脚本文件
    
    Args:
        directory: 服务器脚本所在的目录
        
    Returns:
        字典，键为服务器名称，值为脚本路径
    """
    servers = {}
    
    # 解决相对路径问题
    if not os.path.isabs(directory):
        # 相对于 mcp-server 目录
        directory = os.path.join(os.path.dirname(__file__), '..', 'mcp-server', directory)
    
    # 确保目录存在
    if not os.path.exists(directory):
        print(f"警告：目录 '{directory}' 不存在")
        return {}
    
    # 遍历目录中的所有文件
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        
        # 检查是否是 Python 文件
        if filename.endswith('.py') and os.path.isfile(filepath):
            # 使用文件名（不带扩展名）作为服务器名称
            server_name = os.path.splitext(filename)[0]
            servers[server_name] = filepath
            
        # 检查是否是 JavaScript 文件
        elif filename.endswith('.js') and os.path.isfile(filepath):
            server_name = os.path.splitext(filename)[0]
            servers[server_name] = filepath
    
    return servers

def validate_server(server_path: str) -> bool:
    """验证文件是否是有效的 MCP 服务器脚本
    
    Args:
        server_path: 服务器脚本的路径
        
    Returns:
        是否是有效的 MCP 服务器
    """
    # 简单检查文件是否包含 FastMCP 或相关关键字
    if not os.path.exists(server_path):
        return False
        
    try:
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 检查是否包含 FastMCP 或 MCP 关键字
        if 'FastMCP' in content or '.mcp' in content or 'MCP(' in content:
            return True
    except Exception:
        pass
    
    return False