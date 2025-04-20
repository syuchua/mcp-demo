# src/llm/base.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class LLMProvider(ABC):
    """LLM 提供者的抽象基类"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self._client = None
        
    @abstractmethod
    async def initialize(self):
        """初始化 LLM 客户端"""
        pass
    
    @abstractmethod
    async def generate_completion(self, 
                                 messages: List[Dict[str, Any]], 
                                 model: str,
                                 tools: Optional[List[Dict[str, Any]]] = None, 
                                 **kwargs) -> Dict[str, Any]:
        """生成文本补全"""
        pass
    
    @abstractmethod
    def format_system_message(self, content: str) -> Dict[str, Any]:
        """格式化系统消息"""
        pass
    
    @abstractmethod
    def format_user_message(self, content: str) -> Dict[str, Any]:
        """格式化用户消息"""
        pass
    
    @abstractmethod
    def format_assistant_message(self, content: str, tool_calls: Optional[List] = None) -> Dict[str, Any]:
        """格式化助手消息"""
        pass
    
    @abstractmethod
    def format_tool_message(self, tool_call_id: str, tool_name: str, content: str) -> Dict[str, Any]:
        """格式化工具消息"""
        pass
    
    @abstractmethod
    def extract_text(self, completion: Dict[str, Any]) -> str:
        """从补全响应中提取文本"""
        pass
    
    @abstractmethod
    def extract_tool_calls(self, completion: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从补全响应中提取工具调用"""
        pass
    
    async def close(self):
        """关闭客户端"""
        if hasattr(self, '_client') and self._client:
            await self._client.aclose()