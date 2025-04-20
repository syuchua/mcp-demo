# src/llm/anthropic.py
import httpx
import json
from typing import Dict, List, Any, Optional
from .base import LLMProvider

class AnthropicProvider(LLMProvider):
    """Anthropic Claude API 实现"""
    
    async def initialize(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url or "https://api.anthropic.com/v1",
            timeout=60.0,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
        )
    
    async def generate_completion(self, 
                                 messages: List[Dict[str, Any]], 
                                 model: str,
                                 tools: Optional[List[Dict[str, Any]]] = None, 
                                 **kwargs) -> Dict[str, Any]:
        # 将 OpenAI 格式消息转换为 Claude 格式
        claude_messages = []
        system_content = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "user":
                claude_messages.append({
                    "role": "user",
                    "content": msg["content"]
                })
            elif msg["role"] == "assistant":
                claude_messages.append({
                    "role": "assistant",
                    "content": msg["content"]
                })
            elif msg["role"] == "tool":
                # 将工具响应附加到最后一条用户消息
                if claude_messages and claude_messages[-1]["role"] == "user":
                    claude_messages[-1]["content"] += f"\n\nTool Response ({msg['name']}): {msg['content']}"
                else:
                    claude_messages.append({
                        "role": "user",
                        "content": f"Tool Response ({msg['name']}): {msg['content']}"
                    })
        
        payload = {
            "model": model,
            "messages": claude_messages,
            "max_tokens": kwargs.get("max_tokens", 1000)
        }
        
        if system_content:
            payload["system"] = system_content
        
        if tools:
            # 将OpenAI工具格式转换为Claude工具格式
            claude_tools = []
            for tool in tools:
                if tool["type"] == "function":
                    claude_tools.append({
                        "name": tool["function"]["name"],
                        "description": tool["function"].get("description", ""),
                        "input_schema": tool["function"]["parameters"]
                    })
            
            if claude_tools:
                payload["tools"] = claude_tools
        
        response = await self._client.post(
            "/messages",
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        
        # 将Claude响应转换回OpenAI格式
        openai_format = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": result.get("content", [{"text": ""}])[0].get("text", "")
                }
            }]
        }
        
        # 处理工具调用
        if "tool_use" in result:
            tool_calls = []
            for i, tool_use in enumerate(result.get("tool_use", [])):
                tool_calls.append({
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": tool_use["name"],
                        "arguments": json.dumps(tool_use["input"])
                    }
                })
            
            if tool_calls:
                openai_format["choices"][0]["message"]["tool_calls"] = tool_calls
        
        return openai_format
    
    # 其他方法实现...
    def format_system_message(self, content: str) -> Dict[str, Any]:
        return {
            "role": "system",
            "content": content
        }
    
    def format_user_message(self, content: str) -> Dict[str, Any]:
        return {
            "role": "user",
            "content": content
        }
    
    def format_assistant_message(self, content: str, tool_calls: Optional[List] = None) -> Dict[str, Any]:
        message = {
            "role": "assistant",
            "content": content
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message
    
    def format_tool_message(self, tool_call_id: str, tool_name: str, content: str) -> Dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content
        }
    
    def extract_text(self, completion: Dict[str, Any]) -> str:
        return completion["choices"][0]["message"].get("content", "")
    
    def extract_tool_calls(self, completion: Dict[str, Any]) -> List[Dict[str, Any]]:
        return completion["choices"][0]["message"].get("tool_calls", [])