import os
import yaml
from typing import Dict, Any
from pathlib import Path

def get_default_config_path():
    """获取默认配置路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

def load_config(config_path: str = None) -> Dict[str, Any]:
    """从 YAML 文件加载配置

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    # 如果没有提供配置路径，使用默认路径
    if config_path is None:
        config_path = get_default_config_path()
        
    # 如果配置文件不存在，创建默认配置
    if not os.path.exists(config_path):
        create_default_config(config_path)
        
    # 加载配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        
    # 从环境变量加载 API 密钥
    if 'OPENAI_API_KEY' in os.environ:
        config['api']['openai_api_key'] = os.environ['OPENAI_API_KEY']
    
    return config

def create_default_config(config_path: str) -> None:
    """创建默认配置文件

    Args:
        config_path: 配置文件路径
    """
    default_config = {
        'api': {
            'openai_api_key': os.environ.get('OPENAI_API_KEY', ''),
            'base_url': 'https://api.yuchu.me/v1'
        },
        'models': {
            'available': ['gpt-4o', 'gpt-4-turbo', 'claude-3-5-sonnet'],
            'selected': 'gpt-4o'
        },
        'system': {
            'message': '你是一个基于 MCP 框架的 AI 助手，可以使用多种工具帮助用户完成任务。',
            'debug': False,
            'timeout': 60.0
        },
        'servers': {
            'directory': '../mcp-server',
            'default': 'weather'
        }
    }
    
    # 创建目录（如果不存在）
    os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
    
    # 写入配置文件
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
    
    print(f"已创建默认配置文件：{config_path}")