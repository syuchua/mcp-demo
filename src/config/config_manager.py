import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

class ConfigManager:
    """配置管理类"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config: Dict[str, Any] = {}
        self.config_path = config_path
    
    def get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        return os.path.join(os.path.dirname(__file__), "default_config.yaml")
    
    def load(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """加载配置文件
        
        Args:
            config_path: 配置文件路径，如果为 None 则使用默认路径
            
        Returns:
            配置字典
        """
        # 使用指定的配置路径或默认路径
        path = config_path or self.config_path or self.get_default_config_path()
        
        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(path):
            self.create_default_config(path)
            
        # 加载配置
        with open(path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        # 从环境变量加载敏感信息
        self._load_from_env()
        
        return self.config
    
    def _load_from_env(self) -> None:
        """从环境变量加载配置值"""
        # API 密钥
        if 'OPENAI_API_KEY' in os.environ and 'api' in self.config:
            self.config['api']['openai_api_key'] = os.environ['OPENAI_API_KEY']
            
        if 'ANTHROPIC_API_KEY' in os.environ and 'api' in self.config:
            self.config['api']['anthropic_api_key'] = os.environ['ANTHROPIC_API_KEY']
            
        if 'GOOGLE_API_KEY' in os.environ and 'api' in self.config:
            self.config['api']['google_api_key'] = os.environ['GOOGLE_API_KEY']
    
    def create_default_config(self, config_path: str) -> None:
        """创建默认配置文件
        
        Args:
            config_path: 配置文件路径
        """
        default_config = {
            'api': {
                'openai_api_key': os.environ.get('OPENAI_API_KEY', ''),
                'anthropic_api_key': os.environ.get('ANTHROPIC_API_KEY', ''),
                'google_api_key': os.environ.get('GOOGLE_API_KEY', ''),
                'base_url': 'https://api.openai.com/v1'
            },
            'models': {
                'available': ['gpt-4o', 'gpt-4-turbo', 'claude-3-5-sonnet', 'gemini-pro'],
                'selected': 'gpt-4o'
            },
            'system': {
                'message': 'You are an AI assistant that can use various tools to help users complete tasks.',
                'debug': False,
                'timeout': 60.0,
                'auto_server_selection': True,
                'preload_servers': ['weather']
            },
            'servers': {
                'directory': '../mcp-server',
                'default': 'weather',
                'instances': [
                    {
                        'name': 'weather',
                        'type': 'stdio',
                        'script': 'weather.py',
                        'description': 'Weather forecast service'
                    },
                    {
                        'name': '高德',
                        'type': 'sse',
                        'url': 'https://mcp.amap.com/sse?key=YOUR_AMAP_KEY',
                        'description': 'Gaode Maps service'
                    }
                ]
            }
        }
        
        # 创建目录（如果不存在）
        os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
        
        # 写入配置文件
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)