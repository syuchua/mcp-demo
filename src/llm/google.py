import httpx
import json
from typing import Dict, List, Any, Optional
from .base import LLMProvider

class GoogleProvider(LLMProvider):
    """Google Gemini API 实现"""
    
    async def initialize(self):
        """初始化 Google API 客户端"""
        self._client = httpx.AsyncClient(
            base_url=self.base_url or "https://generativelanguage.googleapis.com/v1beta",
            timeout=60.0,
            params={"key": self.api_key}
        )
    
    async def generate_completion(self, 
                                 messages: List[Dict[str, Any]], 
                                 model: str,
                                 tools: Optional[List[Dict[str, Any]]] = None, 
                                 **kwargs) -> Dict[str, Any]:
        """调用 Gemini API 生成回复"""
        # 将 OpenAI 格式转换为 Gemini 格式
        gemini_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                # Gemini 使用特殊的系统消息格式
                gemini_messages.append({
                    "role": "user",
                    "parts": [{"text": f"[SYSTEM]{msg['content']}[/SYSTEM]"}]
                })
            elif msg["role"] == "user":
                gemini_messages.append({
                    "role": "user",
                    "parts": [{"text": msg["content"]}]
                })
            elif msg["role"] == "assistant":
                gemini_messages.append({
                    "role": "model",
                    "parts": [{"text": msg["content"]}]
                })
            elif msg["role"] == "tool":
                # 工具响应添加到用户消息中
                if gemini_messages and gemini_messages[-1]["role"] == "user":
                    gemini_messages[-1]["parts"][0]["text"] += f"\n\nTool Output ({msg['name']}): {msg['content']}"
                else:
                    gemini_messages.append({
                        "role": "user",
                        "parts": [{"text": f"Tool Output ({msg['name']}): {msg['content']}"}]
                    })

        # 构建API请求
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.7),
                "maxOutputTokens": kwargs.get("max_tokens", 1000)
            }
        }
        
        # 添加工具支持（如果提供）
        if tools:
            function_declarations = []
            for tool in tools:
                if tool["type"] == "function":
                    function_declarations.append({
                        "name": tool["function"]["name"],
                        "description": tool["function"].get("description", ""),
                        "parameters": tool["function"]["parameters"]
                    })
            
            if function_declarations:
                payload["tools"] = [{"functionDeclarations": function_declarations}]
        
        # 发送请求
        response = await self._client.post(
            f"/models/{model}:generateContent",
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        
        # 将 Google 响应转换为 OpenAI 格式
        openai_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": self._extract_gemini_content(result)
                }
            }]
        }
        
        # 处理函数调用
        function_calls = self._extract_function_calls(result)
        if function_calls:
            openai_response["choices"][0]["message"]["tool_calls"] = function_calls
        
        return openai_response
    
    def _extract_gemini_content(self, response: Dict[str, Any]) -> str:
        """从 Gemini 响应中提取文本内容"""
        try:
            candidates = response.get("candidates", [])
            if not candidates:
                return ""
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return ""
                
            return parts[0].get("text", "")
        except Exception:
            return ""
    
    def _extract_function_calls(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从 Gemini 响应中提取函数调用"""
        tool_calls = []
        
        try:
            candidates = response.get("candidates", [])
            if not candidates:
                return []
                
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            for part in parts:
                function_call = part.get("functionCall")
                if function_call:
                    tool_calls.append({
                        "id": f"call_{len(tool_calls)}",
                        "type": "function",
                        "function": {
                            "name": function_call.get("name", ""),
                            "arguments": json.dumps(function_call.get("args", {}))
                        }
                    })
        except Exception:
            pass
            
        return tool_calls
    
    def format_system_message(self, content: str) -> Dict[str, Any]:
        """格式化系统消息"""
        return {
            "role": "system",
            "content": content
        }
    
    def format_user_message(self, content: str) -> Dict[str, Any]:
        """格式化用户消息"""
        return {
            "role": "user",
            "content": content
        }
    
    def format_assistant_message(self, content: str, tool_calls: Optional[List] = None) -> Dict[str, Any]:
        """格式化助手消息"""
        message = {
            "role": "assistant",
            "content": content
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message
    
    def format_tool_message(self, tool_call_id: str, tool_name: str, content: str) -> Dict[str, Any]:
        """格式化工具消息"""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content
        }
    
    def extract_text(self, completion: Dict[str, Any]) -> str:
        """从补全响应中提取文本"""
        return completion["choices"][0]["message"].get("content", "")
    
    def extract_tool_calls(self, completion: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从补全响应中提取工具调用"""
        return completion["choices"][0]["message"].get("tool_calls", [])