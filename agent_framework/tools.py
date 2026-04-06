import subprocess
from typing import List, Dict, Any, Callable
from pydantic import BaseModel

class ToolExecutionError(Exception):
    """自定义工具执行错误"""
    pass


class AgentToolExecutor:
    """
    负责管理和执行所有可用的工具。
    这是一个封装层，它将 LLM 的指令转换为实际的本地系统调用。
    """

    def __init__(self):
        # 注册本地定义的工具函数
        self.tools: Dict[str, Callable] = {
            "run_shell": self._run_shell_tool,
            "search_files": self._search_files_tool,
            "read_file": self._read_file_tool
        }

    def invoke(self, tool_name: str, **kwargs) -> str:
        """
        根据工具名称和参数，执行对应的工具函数。
        所有工具的返回结果最终都会被格式化成字符串传回给 Agent Core。
        """
        if tool_name not in self.tools:
            raise ToolExecutionError(f"未知的工具名: {tool_name}")

        try:
            print(f"\n[Tool] -> 正在调用工具: {tool_name}...")
            result = self.tools[tool_name](**kwargs)
            return f"【工具执行成功：{tool_name}】\n{result}"
        except Exception as e:
            # 捕获任何工具内部的异常，并将其报告给 Agent
            return f"【工具执行失败：{tool_name}】\n错误信息: {e}"


    def _run_shell_tool(self, command: str) -> str:
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


    def _search_files_tool(self, pattern: str) -> str:
        """
        模拟进行文件搜索的工具（例如使用 grep 或 ls）。
        这里简化为查找匹配模式的文件列表。
        """
        print(f"[Tool] 正在搜索包含 '{pattern}' 的文件...")
        # 实际应用中，这里会调用 os.walk + glob/subprocess 来实现深度搜索
        if "context" in pattern:
            return "\nREADME.md\nagent_framework/core.py" # 模拟找到关键文件
        else:
            return f"\n在当前项目结构中未明确找到匹配模式 '{pattern}' 的文件。"

    def _read_file_tool(self, file_path: str) -> str:
        """
        读取指定文件内容的工具，用于代码审查或内容分析。
        """
        print(f"[Tool] 正在读取代码文件: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise ToolExecutionError(f"读取文件 {file_path} 失败: {e}")