import sys
import traceback
from typing import List, Dict, Any, Callable, Awaitable, Optional

from ..log import logger

class CommandHandler:
    """命令处理器类，处理交互式命令"""
    
    def __init__(self, client):
        self.client = client
        self.commands = {
            "quit": self.cmd_quit,
            "exit": self.cmd_quit,
            "help": self.cmd_help,
            "servers": self.cmd_servers,
            "connect": self.cmd_connect,
            "model": self.cmd_model,
            "models": self.cmd_models,
            "debug": self.cmd_debug
        }
    
    async def process_command(self, command: str) -> None:
        """处理命令
        
        Args:
            command: 命令字符串（不含前缀！）
        """
        parts = command.split()
        cmd = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd in self.commands:
            await self.commands[cmd](args)
        else:
            print(f"未知命令：{cmd}")
            print("输入 '!help' 查看可用命令")
    
    async def cmd_quit(self, args: List[str]) -> None:
        """退出命令"""
        print("再见！")
        await self.client.cleanup()
        sys.exit(0)
    
    async def cmd_help(self, args: List[str]) -> None:
        """帮助命令"""
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
    
    async def cmd_servers(self, args: List[str]) -> None:
        """列出可用服务器命令"""
        print(f"可用的服务器：{', '.join(self.client.servers.keys())}")
        print(f"当前服务器：{self.client.current_server}")
    
    async def cmd_connect(self, args: List[str]) -> None:
        """连接到服务器命令"""
        if not args:
            print("请指定要连接的服务器名称")
            return
            
        server_name = args[0]
        try:
            # 创建新的退出栈并关闭旧连接
            if self.client.connection is not None:
                logger.info(f"正在断开与服务器 '{self.client.current_server}' 的连接...")
                old_exit_stack = self.client.exit_stack
                self.client.connection = None
                self.client.exit_stack = self.client._create_exit_stack()
                await old_exit_stack.aclose()
            
            # 连接到新服务器
            await self.client.connect_to_server(server_name)
            print(f"已连接到服务器：{server_name}")
        except Exception as e:
            print(f"错误：{str(e)}")
            if self.client.config['system'].get('debug', False):
                traceback.print_exc()
    
    async def cmd_model(self, args: List[str]) -> None:
        """切换模型命令"""
        if not args:
            print(f"当前模型：{self.client.config['models']['selected']}")
            return
            
        model = args[0]
        if model in self.client.config['models']['available']:
            self.client.config['models']['selected'] = model
            print(f"已切换到模型：{model}")
        else:
            print(f"未知模型：{model}")
            print(f"可用的模型：{', '.join(self.client.config['models']['available'])}")
    
    async def cmd_models(self, args: List[str]) -> None:
        """列出可用模型命令"""
        print(f"可用的模型：{', '.join(self.client.config['models']['available'])}")
        print(f"当前模型：{self.client.config['models']['selected']}")
    
    async def cmd_debug(self, args: List[str]) -> None:
        """切换调试模式命令"""
        if not args:
            current = self.client.config['system'].get('debug', False)
            print(f"调试模式：{'开启' if current else '关闭'}")
            return
            
        if args[0].lower() in ('on', 'true', '1'):
            self.client.config['system']['debug'] = True
            print("已开启调试模式")
        elif args[0].lower() in ('off', 'false', '0'):
            self.client.config['system']['debug'] = False
            print("已关闭调试模式")
        else:
            print("无效的参数，请使用 'on' 或 'off'")