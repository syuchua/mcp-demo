import asyncio
import traceback
from typing import Optional

from .mcp_client import MCPClient
from .commands import CommandHandler
from ..log import logger

class CLI:
    """命令行界面类"""
    
    def __init__(self, client: MCPClient):
        self.client = client
        self.command_handler = CommandHandler(client)
    
    async def start(self) -> None:
        """启动 CLI 界面"""
        model = self.client.config['models']['selected']
        base_url = self.client.config['api']['base_url']
        
        logger.info("MCP 客户端已启动！")
        logger.info(f"使用模型：{model}")
        logger.info(f"API 端点：{base_url}")
        logger.info(f"当前服务器：{self.client.current_server}")
        
        print("\nMCP 客户端已启动！")
        print(f"使用模型：{model}")
        print(f"API 端点：{base_url}")
        print(f"当前服务器：{self.client.current_server}")
        print("输入你的查询，输入 '!help' 查看命令，或输入 '!quit' 退出。")
        
        await self.run_interactive_loop()
    
    async def run_interactive_loop(self) -> None:
        """运行交互式循环"""
        while True:
            try:
                query = input("\n> ").strip()
                
                # 命令处理
                if query.startswith('!'):
                    await self.command_handler.process_command(query[1:])
                    continue
                    
                if not query:
                    continue
                
                logger.info(f"用户输入: '{query}'")
                print("正在处理请求，请稍等...")
                
                try:
                    response = await self.client.process_query(query)
                    print("\n" + response)
                except Exception as e:
                    logger.error(f"处理查询时出错: {e}", exc_info=True)
                    print(f"\n错误：{str(e)}")
                    
            except KeyboardInterrupt:
                print("\n接收到中断信号，正在退出...")
                await self.client.cleanup()
                break
            except Exception as e:
                logger.error(f"交互循环出错: {e}", exc_info=True)
                print(f"\n错误：{str(e)}")

async def start_cli(config_path: Optional[str] = None) -> None:
    """启动 CLI
    
    Args:
        config_path: 配置文件路径
    """
    client = MCPClient(config_path)
    cli = CLI(client)
    
    try:
        # 连接到默认服务器
        await client.connect_to_server()
        # 启动 CLI
        await cli.start()
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        print(f"错误：{str(e)}")
        traceback.print_exc()
    finally:
        await client.cleanup()