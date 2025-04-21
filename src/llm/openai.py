# src/llm/openai.py
import httpx
import json
from typing import Dict, List, Any, Optional
from .base import LLMProvider
from ..log import logger

class OpenAIProvider(LLMProvider):
    """OpenAI API 实现"""
    
    async def initialize(self):
        """初始化 OpenAI 客户端"""
        self._client = httpx.AsyncClient(
            base_url=self.base_url or "https://api.openai.com/v1",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )
        
        # 尝试检测正在使用的 API 类型
        try:
            response = await self._client.get("/models")
            
            if response.status_code == 200:
                models = response.json().get("data", [])
                model_ids = [model.get("id") for model in models]
                
                # 记录可用模型
                from ..log import logger
                logger.info(f"API 端点返回的模型数量: {len(models)}")
                # if len(models) > 0:
                #     logger.info(f"示例模型: {', '.join(model_ids[:5])}")
                    
                # 尝试推断 API 类型
                if any("claude" in model_id.lower() for model_id in model_ids):
                    logger.info("检测到 Claude 模型，但使用 OpenAI 兼容接口")
                elif any("gemini" in model_id.lower() for model_id in model_ids):
                    logger.info("检测到 Gemini 模型，但使用 OpenAI 兼容接口")
        except Exception as e:
            # 忽略错误，这只是一个信息性检测
            from ..log import logger
            logger.debug(f"API 类型检测失败: {e}")
    
    async def generate_completion(self, 
                                 messages: List[Dict[str, Any]], 
                                 model: str,
                                 tools: Optional[List[Dict[str, Any]]] = None, 
                                 **kwargs) -> Dict[str, Any]:
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 1000)
        }
        
        if tools:
            # 检查并修正工具定义格式
            fixed_tools = []
            for tool in tools:
                fixed_tool = tool.copy()
                if "function" in fixed_tool:
                    # 确保 parameters 是一个有效的 JSON Schema
                    if "parameters" in fixed_tool["function"]:
                        params = fixed_tool["function"]["parameters"]
                        if not isinstance(params, dict):
                            logger.warning(f"工具 '{fixed_tool['function'].get('name', 'unknown')}' 的参数不是有效的字典")
                            params = {}
                        
                        if "type" not in params:
                            logger.info(f"添加默认类型到工具 '{fixed_tool['function'].get('name', 'unknown')}' 的参数")
                            params = {
                                "type": "object",
                                "properties": params.copy(),
                                "required": []
                            }
                            fixed_tool["function"]["parameters"] = params
                fixed_tools.append(fixed_tool)
            
            payload["tools"] = fixed_tools
            payload["tool_choice"] = "auto"
        
        # 记录请求详情 (消息内容和工具太长，截断显示)
        log_payload = payload.copy()
        if "messages" in log_payload:
            log_payload["messages"] = f"[{len(messages)} messages]"
        if "tools" in log_payload:
            for i, tool in enumerate(log_payload["tools"]):
                if i < 3:  # 只显示前3个工具
                    logger.debug(f"工具 {i+1}: {json.dumps(tool, ensure_ascii=False)}")
                else:
                    logger.debug(f"还有 {len(log_payload['tools']) - 3} 个工具未显示")
            log_payload["tools"] = f"[{len(log_payload['tools'])} tools]"
        
        logger.debug(f"OpenAI API 请求: {json.dumps(log_payload, ensure_ascii=False)}")
        
        try:
            # 记录完整的原始请求
            if tools:
                logger.debug("完整工具定义:")
                logger.debug(json.dumps(payload["tools"], ensure_ascii=False, indent=2))
            
            response = await self._client.post(
                "/chat/completions",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            logger.debug(f"OpenAI API 响应状态码: {response.status_code}")
            return result
        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            logger.error(f"请求 URL: {self.base_url}/chat/completions")
            logger.error(f"请求头: {self._client.headers}")
            
            # 增加详细的错误信息记录
            if hasattr(e, 'response') and getattr(e, 'response', None) is not None:
                try:
                    err_text = e.response.text
                    logger.error(f"错误响应原文: {err_text}")
                    
                    err_json = e.response.json()
                    logger.error(f"错误详情: {json.dumps(err_json, ensure_ascii=False, indent=2)}")
                except:
                    pass
                
                # 记录完整的错误请求体
                try:
                    # 完整记录请求体，特别关注工具定义
                    if tools:
                        for i, tool in enumerate(tools):
                            logger.error(f"工具 {i+1} 定义: {json.dumps(tool, ensure_ascii=False)}")
                            
                            # 特别检查参数部分
                            if "function" in tool and "parameters" in tool["function"]:
                                params = tool["function"]["parameters"]
                                logger.error(f"工具 {i+1} 参数: {json.dumps(params, ensure_ascii=False)}")
                except:
                    pass
            
            raise
    
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
