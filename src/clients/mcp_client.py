"""
MCP 客户端核心类
提供与 MCP 服务器通信和 LLM 交互的功能
"""
import json
import re
import os
from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack

import httpx
from dotenv import load_dotenv

from ..config.config_manager import ConfigManager
from ..servers.discovery import find_server_instances
from ..connectors import create_server_connection, ServerConnection
from ..log import logger
from ..llm.factory import LLMFactory

# 加载环境变量
load_dotenv()

class MCPClient:
    """MCP 客户端核心类，提供与 MCP 服务器的通信和 LLM 交互功能"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化 MCP 客户端
        
        Args:
            config_path: 配置文件路径，如果为 None 则使用默认路径
        """
        # 加载配置
        config_manager = ConfigManager()
        self.config = config_manager.load(config_path)
        
        # 初始化会话和客户端对象
        self.connection: Optional[ServerConnection] = None
        self.exit_stack = self._create_exit_stack()
        self.http_client = httpx.AsyncClient(timeout=self.config['system'].get('timeout', 60.0))
        
        # 加载 API 密钥
        self._setup_api_keys()
        
        # 发现可用服务器
        self.servers = find_server_instances(self.config)
        self.current_server = None
        
        # 初始化 LLM 提供者
        self.llm_provider = None
    
    def _setup_api_keys(self) -> None:
        """设置 API 密钥"""
        logger.info("正在设置 API 密钥")
        
        # 优先使用环境变量中的 API 密钥
        if 'OPENAI_API_KEY' in os.environ and not self.config['api'].get('openai_api_key'):
            logger.info("从环境变量加载 OpenAI API 密钥")
            self.config['api']['openai_api_key'] = os.environ['OPENAI_API_KEY']
        
        if 'ANTHROPIC_API_KEY' in os.environ and not self.config['api'].get('anthropic_api_key'):
            self.config['api']['anthropic_api_key'] = os.environ['ANTHROPIC_API_KEY']
            
        if 'GOOGLE_API_KEY' in os.environ and not self.config['api'].get('google_api_key'):
            self.config['api']['google_api_key'] = os.environ['GOOGLE_API_KEY']
    
    def _create_exit_stack(self) -> AsyncExitStack:
        """创建异步退出栈"""
        return AsyncExitStack()
    
    async def _get_llm_provider_for_model(self, model_name: Optional[str] = None) -> Any:
        """获取指定模型的 LLM 提供者"""
        if model_name is None:
            model_name = self.config['models']['selected']
        
        # 直接使用 API 密钥和基础 URL
        api_key = self.config['api']['openai_api_key']
        base_url = self.config['api']['base_url']
        
        # 让 LLMFactory 基于模型名和 base_url 智能选择提供者
        logger.info(f"初始化 LLM 提供者: {model_name}, API 端点: {base_url}")
        try:
            provider = LLMFactory.get_provider_for_model(model_name, api_key, base_url)
            await provider.initialize()
            return provider
        except Exception as e:
            logger.error(f"初始化 LLM 提供者失败: {e}")
            raise
    
    async def connect_to_server(self, server_name: Optional[str] = None) -> List:
        """连接到指定的 MCP 服务器
        
        Args:
            server_name: 服务器名称，如果为 None 则使用默认服务器
            
        Returns:
            可用工具列表
        """
        # 如果没有指定服务器，使用默认服务器
        if server_name is None:
            server_name = self.config['servers'].get('default', next(iter(self.servers.keys()), None))
            if server_name is None:
                raise ValueError("未指定默认服务器且未找到可用服务器")
            
        # 检查服务器是否存在
        if server_name not in self.servers:
            available = ", ".join(self.servers.keys())
            raise ValueError(f"服务器 '{server_name}' 不存在。可用的服务器：{available}")
            
        server_config = self.servers[server_name]
        self.current_server = server_name
        
        logger.info(f"正在连接到服务器 '{server_name}'")
        
        # 创建服务器连接
        self.connection = create_server_connection(server_config, self.exit_stack)
        await self.connection.connect()

        # 列出可用的工具
        tools = await self.connection.list_tools()
        logger.info(f"已连接到服务器 '{server_name}'，可用工具：{[tool.name for tool in tools]}")
        
        return tools
    
    async def suggest_server_for_query(self, query: str) -> Optional[str]:
        """
        根据查询内容建议服务器
        
        Args:
            query: 用户查询
        
        Returns:
            建议的服务器名称
        """
        # 保持简单，只返回第一个可用服务器或当前服务器
        return self.current_server or next(iter(self.servers.keys()), None)
    
    def _simplify_schema_for_gemini(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """简化 JSON Schema 以适配 Gemini API
        
        Args:
            schema: 原始 JSON Schema
            
        Returns:
            简化后的 Schema
        """
        if not isinstance(schema, dict):
            return schema
            
        result = {}
        
        # 复制基本字段
        for key, value in schema.items():
            # 跳过 Gemini 不支持的字段
            if key in ["$defs", "$ref", "default"]:
                continue
                
            # 递归处理嵌套字典
            if isinstance(value, dict):
                result[key] = self._simplify_schema_for_gemini(value)
            # 递归处理列表
            elif isinstance(value, list):
                result[key] = [
                    self._simplify_schema_for_gemini(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
                
        return result
    
    def _prepare_tools_for_model(self, tools: List[Dict[str, Any]], model: str) -> List[Dict[str, Any]]:
        """根据模型类型准备工具定义
        
        Args:
            tools: 原始工具定义列表
            model: 模型名称
            
        Returns:
            处理后的工具定义列表
        """
        # 检查是否是 Gemini 模型
        is_gemini = "gemini" in model.lower()
        
        if not is_gemini:
            return tools
            
        # 为 Gemini 简化工具定义
        simplified_tools = []
        for tool in tools:
            simplified_tool = tool.copy()
            
            if "function" in simplified_tool:
                # 复制基本属性
                function_def = simplified_tool["function"].copy()
                
                # 简化参数 schema
                if "parameters" in function_def:
                    function_def["parameters"] = self._simplify_schema_for_gemini(function_def["parameters"])
                    
                simplified_tool["function"] = function_def
                
            simplified_tools.append(simplified_tool)
            
        return simplified_tools
    
    async def process_query(self, query: str, model: Optional[str] = None) -> str:
        """处理用户查询"""
        # 如果未指定模型，使用配置的默认模型
        if model is None:
            model = self.config['models']['selected']
        
        try:
            logger.info(f"正在处理查询: '{query}'")
            
            # 如果未连接到服务器，连接到默认服务器
            if self.connection is None:
                await self.connect_to_server()
            
            # 获取 LLM 提供者
            llm_provider = await self._get_llm_provider_for_model(model)
            logger.info(f"已初始化 LLM 提供者: {model}")
            
            # 第一步：让 LLM 决定使用哪个服务器
            # 构建包含服务器信息的消息
            server_info = "\n\n可用服务器: " + ", ".join(self.servers.keys())
            server_info += f"\n当前服务器: {self.current_server}"
            
            messages = [
                llm_provider.format_system_message(self.config['system']['message'] + server_info),
                llm_provider.format_user_message(query)
            ]
            
            # 第一次 LLM API 调用，让模型决定使用哪个服务器
            logger.info("进行第一次 LLM API 调用，决定使用哪个服务器")
            completion = await llm_provider.generate_completion(
                messages=messages,
                model=model
            )
            
            # 从 LLM 响应中提取服务器选择
            content = llm_provider.extract_text(completion)
            
            # 解析内容中的服务器选择指令 (!use_server:服务器名称)
            server_name = None
            import re
            server_match = re.search(r'!use_server:([^\s]+)', content)
            if server_match:
                server_name = server_match.group(1)
                # 从内容中移除指令
                content = re.sub(r'!use_server:[^\s]+\s*', '', content)
                logger.info(f"LLM 选择使用服务器: {server_name}")
            else:
                # 如果没有明确指令，使用建议的服务器
                server_name = await self.suggest_server_for_query(query)
                logger.info(f"没有明确服务器选择，使用默认服务器: {server_name}")

            # 确保是有效的服务器
            if server_name not in self.servers:
                server_name = self.current_server or next(iter(self.servers.keys()))
                logger.info(f"指定的服务器无效，使用: {server_name}")
            
            # 如果需要切换服务器
            if self.current_server != server_name:
                logger.info(f"切换到服务器: {server_name}")
                await self.connect_to_server(server_name)
            
            # 第二步：使用选定的服务器和工具执行查询
            # 获取当前服务器的工具
            tools = await self.connection.list_tools()
            # 创建工具名到输入模式的映射，用于后续参数验证
            tool_schema_map = {tool.name: tool.inputSchema for tool in tools}
            
            # 准备工具定义
            available_tools = []
            for tool in tools:
                # 确保schema是有效的JSON Schema
                schema = tool.inputSchema
                if not isinstance(schema, dict):
                    schema = {}
                
                # 确保schema符合OpenAI要求
                if "type" not in schema:
                    schema = {
                        "type": "object",
                        "properties": schema,
                        "required": []
                    }
                
                available_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": schema
                    }
                })
            
            # 为特定模型处理工具定义
            available_tools = self._prepare_tools_for_model(available_tools, model)
            
            # 创建新的消息列表，不包括服务器选择指令
            query_messages = [
                llm_provider.format_system_message(self.config['system']['message']),
                llm_provider.format_user_message(query)
            ]
            
            # 第二次 LLM API 调用，实际执行查询
            logger.info(f"进行第二次 LLM API 调用，使用服务器 '{server_name}' 的工具")
            completion = await llm_provider.generate_completion(
                messages=query_messages,
                model=model,
                tools=available_tools
            )
            
            # 处理响应和工具调用
            final_text = []
            content = llm_provider.extract_text(completion)
            
            if content:
                logger.info("获取到初始回复内容")
                final_text.append(content)
            
            # 处理工具调用
            tool_calls = llm_provider.extract_tool_calls(completion)
            if tool_calls:
                logger.info(f"LLM 请求调用工具: {[tc['function']['name'] for tc in tool_calls]}")
                
                # 添加助手消息
                query_messages.append(llm_provider.format_assistant_message(content, tool_calls))
                
                # 处理每个工具调用
                for tool_call in tool_calls:
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])
                    
                    logger.info(f"正在调用工具: {function_name}, 参数: {function_args}")
                    
                    # 调用工具并获取结果
                    try:
                        result = await self.connection.call_tool(function_name, function_args)
                        logger.info(f"工具调用成功: {function_name}")
                    except Exception as e:
                        logger.error(f"工具调用失败: {function_name}, 错误: {e}")
                        result = {"error": str(e)}
                    
                    # 将结果转换为可用的字符串
                    if hasattr(result, 'content'):
                        tool_result_content = str(result.content)
                    elif isinstance(result, dict) and "content" in result:
                        tool_result_content = str(result["content"])
                    else:
                        tool_result_content = str(result)
                    
                    # 记录调试信息
                    if self.config['system'].get('debug', False):
                        logger.debug(f"工具返回结果：{tool_result_content[:100]}...")
                    
                    # 将工具结果添加到消息
                    query_messages.append(llm_provider.format_tool_message(
                        tool_call["id"], 
                        function_name, 
                        tool_result_content
                    ))
                
                logger.info("正在获取 LLM 最终响应...")
                # 获取 LLM 的最终响应
                try:
                    completion = await llm_provider.generate_completion(
                        messages=query_messages,
                        model=model
                    )
                    logger.info("最终 LLM API 调用成功")
                    final_text.append(llm_provider.extract_text(completion))
                except Exception as e:
                    logger.error(f"最终 LLM API 调用失败: {e}")
                    return "\n".join(filter(None, final_text)) + f"\n\n处理查询时出错: {str(e)}"
            
            # 返回结果
            result = "\n".join(filter(None, final_text))
            logger.info("查询处理完成，返回结果")
            return result
        except Exception as e:
            logger.error(f"处理查询时出现未捕获的错误: {e}", exc_info=True)
            return f"处理查询时出现错误: {str(e)}"
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 关闭连接
            if hasattr(self, 'connection') and self.connection:
                logger.info("正在关闭服务器连接...")
                self.connection = None
            
            # 关闭 HTTP 客户端
            if hasattr(self, 'http_client') and self.http_client:
                logger.info("正在关闭 HTTP 客户端...")
                await self.http_client.aclose()
            
            # 关闭退出栈
            if hasattr(self, 'exit_stack') and self.exit_stack:
                logger.info("正在清理资源...")
                await self.exit_stack.aclose()
                
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")