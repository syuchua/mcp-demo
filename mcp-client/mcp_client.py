# mcp-client/mcp_client.py

import asyncio
import httpx
import json
import os
import sys
import logging
from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack

from dotenv import load_dotenv

# 导入我们的自定义模块
from config import load_config
from server_discovery import find_server_instances
from server_connection import create_server_connection, ServerConnection

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp-client")

load_dotenv()  # 从 .env 加载环境变量

class MCPClient:
    def __init__(self, config_path: str = None):
        # 加载配置
        self.config = load_config(config_path)
        
        # 初始化会话和客户端对象
        self.connection: Optional[ServerConnection] = None
        self.exit_stack = AsyncExitStack()
        self.http_client = httpx.AsyncClient(timeout=self.config['system'].get('timeout', 60.0))
        self.api_key = self.config['api']['openai_api_key']
        
        # 发现可用服务器
        self.servers = find_server_instances(self.config)
        self.current_server = None
        
    async def connect_to_server(self, server_name: str = None):
        """
        连接到指定的 MCP 服务器
        
        Args:
            server_name: 服务器名称，如果为 None 则使用默认服务器
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
        
    async def call_llm_api(self, 
                           messages: List[Dict[str, Any]], 
                           model: str = None,
                           tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        通用 LLM API 调用函数
        
        Args:
            messages: 消息历史
            model: 模型名称，如果为 None 则使用配置的默认模型
            tools: 可用工具列表
        
        Returns:
            LLM API 的响应
        """
        # 如果没有指定模型，使用配置的默认模型
        if model is None:
            model = self.config['models']['selected']
            
        base_url = self.config['api']['base_url']
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 1000
        }
        
        # 添加系统消息
        if self.config['system'].get('message'):
            system_message = {"role": "system", "content": self.config['system']['message']}
            # 确保系统消息在消息列表的开头
            if not (messages and messages[0]['role'] == 'system'):
                messages.insert(0, system_message)
        
        if tools:
            payload["tools"] = tools
        
        try:
            response = await self.http_client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"API 请求错误：{e}")
            raise

    async def suggest_server_for_query(self, query: str) -> Optional[str]:
        """
        根据查询内容建议服务器
        
        Args:
            query: 用户查询
        
        Returns:
            建议的服务器名称
        """
        # 示例实现：根据查询内容返回一个建议的服务器名称
        # 实际实现可以根据业务逻辑进行调整
        return next(iter(self.servers.keys()), None)

    async def process_query(self, query: str, model: str = None) -> str:
        """处理用户查询"""
        
        # 首先检查是否需要根据查询内容预选择服务器
        server_suggestion = await self.suggest_server_for_query(query)
        
        # 构建包含服务器建议的消息
        messages = [
            {
                "role": "system",
                "content": f"{self.config['system']['message']}\n\n当前可用服务器: {', '.join(self.servers.keys())}"
            },
            {
                "role": "user",
                "content": query
            }
        ]
        
        # 初始 LLM API 调用，让模型决定使用哪个服务器
        llm_response = await self.call_llm_api(
            messages=messages,
            model=model
        )

        # 从 LLM 响应中提取服务器选择
        assistant_message = llm_response["choices"][0]["message"]
        content = assistant_message.get("content", "")
        
        # 解析内容中的服务器选择指令 (!use_server:服务器名称)
        server_name = None
        import re
        server_match = re.search(r'!use_server:([^\s]+)', content)
        if server_match:
            server_name = server_match.group(1)
            # 从内容中移除指令
            content = re.sub(r'!use_server:[^\s]+\s*', '', content)
        else:
            # 如果没有明确指令，使用建议的服务器
            server_name = server_suggestion
        
        # 确保是有效的服务器
        if server_name not in self.servers:
            server_name = self.current_server or next(iter(self.servers.keys()))
        
        # 如果需要切换服务器
        if self.current_server != server_name:
            await self.connect_to_server(server_name)
        
        # 获取当前服务器的工具并继续处理
        tools = await self.connection.list_tools()
        available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in tools]

        # 初始 LLM API 调用
        llm_response = await self.call_llm_api(
            messages=messages,
            model=model,
            tools=available_tools
        )

        # 处理响应和工具调用
        final_text = []
        
        assistant_message = llm_response["choices"][0]["message"]
        content = assistant_message.get("content", "")
        if content:
            final_text.append(content)
        
        # 处理工具调用
        tool_calls = assistant_message.get("tool_calls", [])
        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls
            })
            
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                function_args = json.loads(tool_call["function"]["arguments"])
                
                # 调用工具并获取结果
                result = await self.connection.call_tool(function_name, function_args)
                
                # 将 result 转换为可用的字符串
                if hasattr(result, 'content'):
                    tool_result_content = str(result.content)
                elif isinstance(result, dict) and "content" in result:
                    tool_result_content = str(result["content"])
                else:
                    tool_result_content = str(result)
                
                # 只在调试模式下显示工具调用信息
                if self.config['system'].get('debug', False):
                    logger.debug(f"调用工具：{function_name}")
                    logger.debug(f"参数：{json.dumps(function_args, ensure_ascii=False)}")
                    logger.debug(f"结果：{tool_result_content}")
                
                # 将工具结果添加到消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": function_name,
                    "content": tool_result_content
                })
            
            # 获取 LLM 的下一个响应
            llm_response = await self.call_llm_api(
                messages=messages,
                model=model,
                tools=available_tools
            )
            
            assistant_response = llm_response["choices"][0]["message"].get("content", "")
            if assistant_response:
                final_text.append(assistant_response)

        return "\n".join(filter(None, final_text))
    
    async def chat_loop(self):
        """运行交互式聊天循环"""
        model = self.config['models']['selected']
        base_url = self.config['api']['base_url']
        
        logger.info("MCP 客户端已启动！")
        logger.info(f"使用模型：{model}")
        logger.info(f"API 端点：{base_url}")
        logger.info(f"当前服务器：{self.current_server}")
        print("\nMCP 客户端已启动！")
        print(f"使用模型：{model}")
        print(f"API 端点：{base_url}")
        print(f"当前服务器：{self.current_server}")
        print("输入你的查询，输入 '!help' 查看命令，或输入 '!quit' 退出。")

        while True:
            try:
                query = input("\n> ").strip()

                # 命令处理
                if query.startswith('!'):
                    await self.process_command(query[1:])
                    continue
                    
                if not query:
                    continue

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                logger.error(f"错误：{str(e)}")
                print(f"\n错误：{str(e)}")
                if self.config['system'].get('debug', False):
                    import traceback
                    traceback.print_exc()

    async def process_command(self, command: str) -> None:
        """
        处理特殊命令
        
        Args:
            command: 命令字符串（不含前缀！）
        """
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd == 'quit' or cmd == 'exit':
            print("再见！")
            await self.cleanup()
            sys.exit(0)
            
        elif cmd == 'help':
            print("""
可用命令:
  !quit, !exit       - 退出程序
  !help              - 显示此帮助信息
  !servers           - 列出可用的服务器
  !connect <server>  - 连接到指定的服务器
  !model <model>     - 切换使用的模型
  !models            - 列出可用的模型
  !debug <on/off>    - 开启/关闭调试模式
""")
            
        elif cmd == 'servers':
            print(f"可用的服务器：{', '.join(self.servers.keys())}")
            print(f"当前服务器：{self.current_server}")
            
        elif cmd == 'connect':
            if not args:
                print("请指定要连接的服务器名称")
                return
                
            server_name = args[0]
            try:
                # 创建新的退出栈并关闭旧连接
                if self.connection is not None:
                    logger.info(f"正在断开与服务器 '{self.current_server}' 的连接...")
                    old_exit_stack = self.exit_stack
                    self.connection = None
                    self.exit_stack = AsyncExitStack()
                    await old_exit_stack.aclose()
                
                # 连接到新服务器
                await self.connect_to_server(server_name)
                print(f"已连接到服务器：{server_name}")
            except Exception as e:
                print(f"错误：{str(e)}")
                if self.config['system'].get('debug', False):
                    import traceback
                    traceback.print_exc()
                
        elif cmd == 'model':
            if not args:
                print(f"当前模型：{self.config['models']['selected']}")
                return
                
            model = args[0]
            if model in self.config['models']['available']:
                self.config['models']['selected'] = model
                print(f"已切换到模型：{model}")
            else:
                print(f"未知模型：{model}")
                print(f"可用的模型：{', '.join(self.config['models']['available'])}")
                
        elif cmd == 'models':
            print(f"可用的模型：{', '.join(self.config['models']['available'])}")
            print(f"当前模型：{self.config['models']['selected']}")
            
        elif cmd == 'debug':
            if not args:
                current = self.config['system'].get('debug', False)
                print(f"调试模式：{'开启' if current else '关闭'}")
                return
                
            if args[0].lower() in ('on', 'true', '1'):
                self.config['system']['debug'] = True
                print("已开启调试模式")
            elif args[0].lower() in ('off', 'false', '0'):
                self.config['system']['debug'] = False
                print("已关闭调试模式")
            else:
                print("无效的参数，请使用 'on' 或 'off'")
                
        else:
            print(f"未知命令：{cmd}")
            print("输入 '!help' 查看可用命令")

    async def cleanup(self):
        """清理资源"""
        try:
            # 先关闭连接
            if hasattr(self, 'connection') and self.connection:
                logger.info("正在关闭服务器连接...")
                # 在这里不主动关闭 connection，让 exit_stack 处理
                self.connection = None
            
            # 关闭 HTTP 客户端
            if hasattr(self, 'http_client') and self.http_client:
                logger.info("正在关闭 HTTP 客户端...")
                await self.http_client.aclose()
            
            # 最后关闭退出栈，它会负责清理所有资源
            if hasattr(self, 'exit_stack') and self.exit_stack:
                logger.info("正在清理资源...")
                await self.exit_stack.aclose()
                
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")

async def main():
    # 创建客户端并运行
    client = MCPClient()
    
    try:
        # 连接到默认服务器
        await client.connect_to_server()
        # 启动聊天循环
        await client.chat_loop()
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        print(f"错误：{str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())