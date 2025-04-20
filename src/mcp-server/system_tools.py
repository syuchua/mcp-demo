#!/usr/bin/env python3
"""System Tools MCP Server - 执行系统程序和应用程序自动化"""

import os
import sys
import subprocess
import time
import json
import shlex
from typing import Dict, List, Any, Optional
from datetime import datetime
import shutil
import platform
from mcp.server.fastmcp import FastMCP

# 初始化 FastMCP server
mcp = FastMCP("system_tools")

# 安全策略：允许执行的应用程序白名单
ALLOWED_APPS = {
    "qq": {
        "path": r"D:\\QQ\\QQ.exe",  # 请根据实际路径调整
        "alt_paths": [
            r"C:\\Program Files\\Tencent\\QQ\\\Bin\\QQ.exe",
            r"C:\\Program Files (x86)\\Tencent\\QQ\\Bin\\QQ.exe"
        ]
    },
    "wechat": {
        "path": r"C:\\Program Files\\Tencent\\WeChat\\WeChat.exe",
        "alt_paths": [
            r"C:\\Program Files (x86)\\Tencent\\WeChat\\WeChat.exe"
        ]
    },
    "notepad": {
        "path": r"C:\\Windows\System32\\notepad.exe",
        "alt_paths": []
    },
    "calculator": {
        "path": r"C:\\Windows\System32\\calc.exe",
        "alt_paths": []
    },
    "chrome": {
        "path": r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "alt_paths": [
            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        ]
    },
    "edge": {
        "path": r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "alt_paths": []
    },
    "explorer": {
        "path": r"C:\\Windows\\explorer.exe",
        "alt_paths": []
    }
}

def find_executable(app_name: str) -> Optional[str]:
    """查找应用程序可执行文件路径"""
    if app_name in ALLOWED_APPS:
        app_info = ALLOWED_APPS[app_name]
        
        # 检查主路径
        if os.path.exists(app_info["path"]):
            return app_info["path"]
        
        # 检查备选路径
        for path in app_info["alt_paths"]:
            if os.path.exists(path):
                return path
                
    # 在 PATH 中查找
    path = shutil.which(app_name)
    if path:
        return path
        
    return None

def is_allowed_executable(path: str) -> bool:
    """检查是否是允许执行的程序"""
    # 检查是否在白名单中
    for app_info in ALLOWED_APPS.values():
        if path.lower() == app_info["path"].lower():
            return True
        if path.lower() in [alt_path.lower() for alt_path in app_info["alt_paths"]]:
            return True
    
    # 添加一些基本的安全检查
    prohibited_dirs = [
        r"C:\\Windows\\System32\\drivers",
        r"C:\\Windows\\System32\\config",
        r"C:\\Windows\\security",
        r"/boot", "/etc", "/var"  # Linux路径(以防万一)
    ]
    
    for dir_path in prohibited_dirs:
        if path.lower().startswith(dir_path.lower()):
            return False
    
    # 允许其他目录的常规应用程序
    return path.lower().endswith('.exe')

@mcp.tool()
async def execute_program(program: str, arguments: Optional[str] = None, 
                          working_directory: Optional[str] = None) -> Dict[str, Any]:
    """
    执行指定的程序或应用
    
    Args:
        program: 程序名称(例如"notepad"、"chrome")或完整路径
        arguments: 命令行参数 (可选)
        working_directory: 工作目录 (可选)
    
    Returns:
        包含执行结果的字典
    """
    try:
        # 查找可执行文件
        executable_path = find_executable(program)
        
        if not executable_path:
            executable_path = program  # 尝试使用传入的路径
        
        # 安全检查
        if not is_allowed_executable(executable_path):
            return {
                "success": False,
                "error": f"安全限制：不允许执行 '{program}'"
            }
            
        # 准备命令
        cmd = [executable_path]
        if arguments:
            # 安全地处理参数
            if platform.system() == "Windows":
                # Windows下拆分参数
                if isinstance(arguments, str):
                    cmd.extend(arguments.split())
            else:
                # Linux/Mac下使用shlex
                cmd.extend(shlex.split(arguments))
        
        # 设置工作目录
        if working_directory:
            if not os.path.exists(working_directory):
                os.makedirs(working_directory, exist_ok=True)
            cwd = working_directory
        else:
            cwd = os.getcwd()  # 使用当前目录
        
        # 执行命令 (非阻塞模式)
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            shell=False,  # 安全起见，不使用shell
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors='replace'
        )
        
        # 等待一小段时间，确保进程启动
        time.sleep(0.5)
        
        # 检查进程状态
        return_code = process.poll()
        if return_code is not None:  # 进程已结束
            stdout, stderr = process.communicate()
            if return_code != 0:
                return {
                    "success": False,
                    "return_code": return_code,
                    "error": stderr,
                    "output": stdout,
                    "working_directory": cwd
                }
            else:
                return {
                    "success": True,
                    "return_code": 0,
                    "output": stdout,
                    "working_directory": cwd
                }
        else:  # 进程还在运行
            return {
                "success": True,
                "message": f"程序 '{program}' 已启动，PID: {process.pid}",
                "working_directory": cwd
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"执行 '{program}' 时出错"
        }

@mcp.tool()
async def open_app(app_name: str) -> Dict[str, Any]:
    """
    打开常用应用程序
    
    Args:
        app_name: 应用程序名称 (如 "qq", "wechat", "notepad", "chrome" 等)
    
    Returns:
        包含打开结果的字典
    """
    return await execute_program(app_name)

@mcp.tool()
async def send_qq_message(qq_number: str, message: str) -> Dict[str, Any]:
    """
    发送QQ消息 (通过打开QQ并模拟操作)
    
    Args:
        qq_number: 目标QQ号码
        message: 要发送的消息内容
    
    Returns:
        包含操作结果的字典
    """
    try:
        # 1. 确保QQ已启动
        qq_path = find_executable("qq")
        if not qq_path:
            return {
                "success": False,
                "error": "找不到QQ程序路径"
            }
        
        # 检查QQ是否已运行
        qq_running = False
        
        try:
            # 使用tasklist检查QQ进程
            if platform.system() == "Windows":
                output = subprocess.check_output("tasklist /FI \"IMAGENAME eq QQ.exe\"", shell=True, text=True)
                qq_running = "QQ.exe" in output
        except:
            qq_running = False
        
        # 如果QQ没有运行，启动它
        if not qq_running:
            subprocess.Popen([qq_path], shell=False)
            # 等待QQ启动
            time.sleep(5)
        
        # 2. 使用QQ的URL协议启动聊天窗口
        # QQ的URL协议: tencent://message/?Menu=yes&uin=QQ号码&Service=300&sigT=45a1e5847943b64c6ff3990f8a9e644d2b31356cb0b4ac6b24663a3c8dd0f8aa12a595b1464e7f6ae49b170252
        qq_url = f"tencent://message/?Menu=yes&uin={qq_number}&Service=300"
        
        # 启动URL协议
        if platform.system() == "Windows":
            os.startfile(qq_url)
        else:
            subprocess.Popen(['xdg-open', qq_url], shell=False)
        
        # 3. 等待聊天窗口打开
        time.sleep(2)
        
        # 4. 模拟复制消息到剪贴板
        import pyperclip
        pyperclip.copy(message)
        
        # 5. 模拟按键 Ctrl+V 和 Enter
        try:
            import pyautogui
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            
            return {
                "success": True,
                "message": f"已向QQ {qq_number} 发送消息"
            }
        except ImportError:
            return {
                "success": False,
                "error": "未安装pyautogui模块，无法模拟按键操作",
                "partial_success": True,
                "message": f"已打开与 {qq_number} 的聊天窗口，请手动粘贴消息"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "发送QQ消息失败"
        }

@mcp.tool()
async def list_running_processes() -> Dict[str, Any]:
    """
    列出当前运行的进程
    
    Returns:
        包含进程列表的字典
    """
    try:
        processes = []
        
        if platform.system() == "Windows":
            output = subprocess.check_output("tasklist /FO CSV /NH", shell=True, text=True)
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                # CSV格式，但要处理引号
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    name = parts[0]
                    pid = parts[1]
                    processes.append({
                        "name": name,
                        "pid": pid
                    })
        else:
            # Linux/Mac
            output = subprocess.check_output(["ps", "aux"], text=True)
            lines = output.strip().split('\n')
            for line in lines[1:]:  # 跳过标题行
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append({
                        "user": parts[0],
                        "pid": parts[1],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "command": parts[10]
                    })
                    
        return {
            "success": True,
            "processes": processes[:100]  # 限制返回数量
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "获取进程列表失败"
        }

@mcp.tool()
async def kill_process(process_name: str) -> Dict[str, Any]:
    """
    结束指定名称的进程
    
    Args:
        process_name: 进程名称 (如 "notepad.exe")
    
    Returns:
        包含操作结果的字典
    """
    try:
        # 安全检查 - 禁止关键系统进程
        forbidden_processes = [
            "explorer.exe", "svchost.exe", "lsass.exe", "csrss.exe", 
            "winlogon.exe", "services.exe", "smss.exe", "wininit.exe"
        ]
        
        if process_name.lower() in [p.lower() for p in forbidden_processes]:
            return {
                "success": False,
                "error": f"安全限制：不允许终止系统进程 '{process_name}'"
            }
            
        if platform.system() == "Windows":
            subprocess.check_call(f"taskkill /F /IM {process_name}", shell=True)
        else:
            subprocess.check_call(["pkill", process_name])
            
        return {
            "success": True,
            "message": f"已终止进程 '{process_name}'"
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"终止进程 '{process_name}' 失败，可能是进程不存在"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"终止进程 '{process_name}' 时出错"
        }

@mcp.tool()
async def create_file(file_path: str, content: str) -> Dict[str, Any]:
    """
    创建文件并写入内容
    
    Args:
        file_path: 文件路径（绝对路径或相对路径）
        content: 要写入的文件内容
    
    Returns:
        包含操作结果的字典
    """
    try:
        # 安全检查：不允许写入系统目录
        forbidden_dirs = [
            r"C:\Windows\System32",
            r"C:\Windows\System",
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            "/etc", "/var/lib", "/bin", "/sbin"  # Linux系统目录
        ]
        
        abs_path = os.path.abspath(file_path)
        for forbidden in forbidden_dirs:
            if abs_path.lower().startswith(forbidden.lower()):
                return {
                    "success": False,
                    "error": f"安全限制：不允许写入系统目录 '{forbidden}'"
                }
        
        # 如果路径不存在，创建目录
        dir_path = os.path.dirname(abs_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        
        # 写入文件
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "message": f"文件已创建：{abs_path}",
            "absolute_path": abs_path
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"创建文件失败：{file_path}"
        }

@mcp.tool()
async def read_file(file_path: str, max_size: int = 1024*1024) -> Dict[str, Any]:
    """
    读取文件内容
    
    Args:
        file_path: 文件路径
        max_size: 最大读取字节数（默认1MB）
    
    Returns:
        包含文件内容的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在：{file_path}"
            }
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size > max_size:
            return {
                "success": False,
                "error": f"文件过大：{file_size} 字节（限制：{max_size} 字节）"
            }
        
        # 尝试不同编码读取文件
        encodings = ['utf-8', 'gbk', 'latin1']
        content = None
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            # 如果所有文本编码都失败，可能是二进制文件
            return {
                "success": False,
                "error": "无法读取文件，可能是二进制文件"
            }
        
        return {
            "success": True,
            "content": content,
            "size": file_size,
            "path": os.path.abspath(file_path)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"读取文件失败：{file_path}"
        }

@mcp.tool()
async def list_files(directory: str = ".", pattern: str = "*") -> Dict[str, Any]:
    """
    列出目录中的文件
    
    Args:
        directory: 目录路径（默认为当前目录）
        pattern: 文件匹配模式（如 *.py, *.txt）
    
    Returns:
        包含文件列表的字典
    """
    try:
        import glob
        import time
        from datetime import datetime
        
        # 确保目录存在
        if not os.path.exists(directory):
            return {
                "success": False,
                "error": f"目录不存在：{directory}"
            }
        
        # 获取绝对路径
        abs_dir = os.path.abspath(directory)
        
        # 查找文件
        file_pattern = os.path.join(abs_dir, pattern)
        files = glob.glob(file_pattern)
        
        # 收集文件信息
        file_info = []
        for file_path in files:
            try:
                stat = os.stat(file_path)
                file_info.append({
                    "name": os.path.basename(file_path),
                    "path": file_path,
                    "size": stat.st_size,
                    "is_dir": os.path.isdir(file_path),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
            except:
                # 跳过无法访问的文件
                pass
        
        return {
            "success": True,
            "directory": abs_dir,
            "pattern": pattern,
            "files": file_info,
            "count": len(file_info)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"列出文件失败：{directory}"
        }

@mcp.tool()
async def delete_file(file_path: str) -> Dict[str, Any]:
    """
    删除文件
    
    Args:
        file_path: 要删除的文件路径
    
    Returns:
        包含操作结果的字典
    """
    try:
        # 安全检查：不允许删除系统目录中的文件
        forbidden_dirs = [
            r"C:\Windows", 
            r"C:\Program Files", 
            r"C:\Program Files (x86)",
            "/etc", "/var/lib", "/bin", "/sbin"
        ]
        
        abs_path = os.path.abspath(file_path)
        for forbidden in forbidden_dirs:
            if abs_path.lower().startswith(forbidden.lower()):
                return {
                    "success": False,
                    "error": f"安全限制：不允许删除系统目录中的文件 '{forbidden}'"
                }
        
        # 检查文件是否存在
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"文件不存在：{abs_path}"
            }
        
        # 删除文件
        if os.path.isdir(abs_path):
            os.rmdir(abs_path)  # 只删除空目录
            return {
                "success": True,
                "message": f"目录已删除：{abs_path}"
            }
        else:
            os.remove(abs_path)
            return {
                "success": True,
                "message": f"文件已删除：{abs_path}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"删除文件失败：{file_path}"
        }

@mcp.tool()
async def get_working_directory() -> Dict[str, Any]:
    """
    获取当前工作目录
    
    Returns:
        包含当前工作目录的字典
    """
    try:
        cwd = os.getcwd()
        return {
            "success": True,
            "working_directory": cwd,
            "files_count": len(os.listdir(cwd))
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def run_python_code(code: str) -> Dict[str, Any]:
    """
    执行Python代码并返回结果
    
    Args:
        code: 要执行的Python代码
    
    Returns:
        包含执行结果的字典
    """
    try:
        import tempfile
        import sys
        from io import StringIO
        
        # 安全检查：不允许一些危险操作
        forbidden_modules = [
            "subprocess", "os.system", "shutil.rmtree", "sys.exit"
        ]
        
        for module in forbidden_modules:
            if module in code:
                return {
                    "success": False,
                    "error": f"安全限制：不允许使用 '{module}'"
                }
        
        # 捕获标准输出和错误
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout = StringIO()
        stderr = StringIO()
        sys.stdout = stdout
        sys.stderr = stderr
        
        result = None
        try:
            # 使用临时命名空间执行代码
            namespace = {}
            exec(code, namespace)
            result = namespace.get('result', None)
        finally:
            # 恢复标准输出和错误
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        return {
            "success": True,
            "output": stdout.getvalue(),
            "errors": stderr.getvalue(),
            "result": str(result) if result is not None else None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "执行Python代码失败"
        }

if __name__ == "__main__":
    # 运行 MCP 服务器
    mcp.run(transport='stdio')