import subprocess
import json
import os
from typing import List, Dict, Any, Callable, Type
from pydantic import BaseModel, Field, ValidationError

class ToolExecutionError(Exception):
    """自定义工具执行错误"""
    pass


# ==========================================
# 1. 工具注册表与装饰器
# ==========================================
class ToolInfo:
    """保存工具的元数据及参数模式"""
    def __init__(self, name: str, description: str, func: Callable, args_schema: Type[BaseModel]):
        self.name = name
        self.description = description
        self.func = func
        self.args_schema = args_schema

    def get_schema_dict(self) -> Dict[str, Any]:
        """生成供 LLM 识别的标准 JSON Schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_schema.model_json_schema()
        }

TOOL_REGISTRY: Dict[str, ToolInfo] = {}

def tool(name: str, description: str, args_schema: Type[BaseModel]):
    """
    工具注册装饰器，将独立函数注册到全局可用工具库中
    使用示例: @tool(name="run_shell", description="...", args_schema=RunShellArgs)
    """
    def decorator(func: Callable):
        TOOL_REGISTRY[name] = ToolInfo(name, description, func, args_schema)
        return func
    return decorator


# ==========================================
# 2. 具体工具实现 (独立函数解耦)
# ==========================================
class RunShellArgs(BaseModel):
    command: str = Field(..., description="需要执行的操作系统 Shell 命令。请务必根据当前操作系统（Windows用cmd/powershell，Mac/Linux用bash）使用正确的语法。")

@tool(name="run_shell", description="执行本地系统 Shell 命令", args_schema=RunShellArgs)
def run_shell_tool(command: str) -> str:
    """
    模拟运行Shell命令的工具。
    注意：在生产环境中，应限制或沙箱化这个功能！
    """
    print(f"[Tool] 正在执行系统命令: {command}")
    try:
        # 使用 subprocess 来安全地执行 shell 命令
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=30 # 设置超时，防止无限等待
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise ToolExecutionError(f"命令执行失败 (返回码 {e.returncode}): \n{e.stderr}")
    except subprocess.TimeoutExpired:
        raise ToolExecutionError("命令执行超时，已终止。")

class ListDirArgs(BaseModel):
    directory: str = Field(default=".", description="需要列出内容的目录路径。默认为当前目录 '.'")

@tool(name="list_dir", description="跨平台查看指定目录下的文件和文件夹列表", args_schema=ListDirArgs)
def list_dir_tool(directory: str) -> str:
    """
    这是一个跨平台的目录查看工具，不依赖于具体的 shell 命令 (如 ls 或 dir)。
    """
    print(f"[Tool] 正在读取目录: {directory}")
    try:
        items = os.listdir(directory)
        # 格式化输出，方便模型阅读
        return f"目录 '{directory}' 下的内容:\n" + "\n".join(f"- {item}" for item in items)
    except Exception as e:
        raise ToolExecutionError(f"无法读取目录 '{directory}': {e}")

class SearchFilesArgs(BaseModel):
    pattern: str = Field(..., description="要搜索的文件名匹配模式或关键字")

@tool(name="search_files", description="在当前项目目录中搜索匹配的文件", args_schema=SearchFilesArgs)
def search_files_tool(pattern: str) -> str:
    """
    模拟进行文件搜索的工具（例如使用 grep 或 ls）。
    这里简化为查找匹配模式的文件列表。
    """
    print(f"[Tool] 正在搜索包含 '{pattern}' 的文件...")
    if "context" in pattern:
        return "\nREADME.md\nagent_framework/core.py" # 模拟找到关键文件
    else:
        return f"\n在当前项目结构中未明确找到匹配模式 '{pattern}' 的文件。"

class ReadFileArgs(BaseModel):
    file_path: str = Field(..., description="需要读取的文件的绝对或相对路径")

@tool(name="read_file", description="读取并返回指定文件的文本内容", args_schema=ReadFileArgs)
def read_file_tool(file_path: str) -> str:
    """
    读取指定文件内容的工具，用于代码审查或内容分析。
    """
    print(f"[Tool] 正在读取代码文件: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        raise ToolExecutionError(f"读取文件 {file_path} 失败: {e}")


# ==========================================
# 3. 核心工具执行器
# ==========================================
class AgentToolExecutor:
    """
    负责管理和执行所有可用的工具。
    这是一个封装层，它将 LLM 的指令转换为实际的本地系统调用。
    """

    def __init__(self):
        # 动态加载所有通过 @tool 注册的工具
        self.tools: Dict[str, ToolInfo] = TOOL_REGISTRY.copy()

    def invoke(self, tool_name: str, **kwargs) -> str:
        """
        根据工具名称和参数，执行对应的工具函数。
        所有工具的返回结果最终都会被格式化成字符串传回给 Agent Core。
        """
        if tool_name not in self.tools:
            raise ToolExecutionError(f"未知的工具名: {tool_name}")

        try:
            print(f"\n[Tool] -> 正在调用工具: {tool_name}...")
            
            tool_info = self.tools[tool_name]
            
            # 1. 使用 Pydantic BaseModel 进行严谨的参数实例化和校验
            try:
                validated_args = tool_info.args_schema(**kwargs)
            except ValidationError as ve:
                # 专门捕获 Pydantic 校验错误，将结构化的错误信息反馈给 LLM 让其纠正
                error_msg = f"【工具参数校验失败：{tool_name}】\n传入参数不符合 Schema 规范，请根据错误信息修正:\n{ve}"
                return error_msg
                
            # 2. 将校验后绝对安全的参数解包传入原函数
            result = tool_info.func(**validated_args.model_dump())
            return f"【工具执行成功：{tool_name}】\n{result}"
        except Exception as e:
            # 捕获任何工具内部的异常，并将其报告给 Agent
            return f"【工具执行失败：{tool_name}】\n错误信息: {e}"

    def get_all_tools_schema(self) -> str:
        """
        返回所有注册工具的 JSON Schema 描述字符串，用于动态组装 LLM Prompt
        """
        schemas = [tool_info.get_schema_dict() for tool_info in self.tools.values()]
        return json.dumps(schemas, ensure_ascii=False, indent=2)