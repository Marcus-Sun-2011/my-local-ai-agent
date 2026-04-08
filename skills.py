import inspect
from typing import Callable, Dict, Any, List
from pydantic import BaseModel, create_model

class SkillRegistry:
    """
    核心工具注册表 (Tool Registry Pattern)
    用于统一管理 Agent 的所有可用 Skills。
    """
    def __init__(self):
        self._skills: Dict[str, Dict[str, Any]] = {}

    def tool(self, name: str = None, description: str = None):
        """
        工具注册装饰器 (@tool)
        自动解析函数签名并生成对应的 Pydantic Schema，供 LLM Function Calling 使用。
        """
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_desc = description or func.__doc__ or "No description provided."
            
            # 解析函数签名以动态生成 Pydantic Model (Schema-Driven Tooling)
            sig = inspect.signature(func)
            fields = {}
            for param_name, param in sig.parameters.items():
                # 默认将未标注类型的参数视为字符串
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
                fields[param_name] = (param_type, ...)
            
            # 动态生成 Pydantic Schema
            schema_model = create_model(f"{tool_name}_Schema", **fields)
            
            self._skills[tool_name] = {
                "callable": func,
                "description": tool_desc,
                "schema": schema_model.schema()
            }
            return func
        return decorator

    def get_all_tools_for_llm(self) -> List[Dict[str, Any]]:
        """获取所有工具的 Schema 定义，用于传递给 LLM"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": info["description"],
                    "parameters": info["schema"]
                }
            } 
            for tool_name, info in self._skills.items()
        ]

    def execute(self, name: str, **kwargs) -> Any:
        """执行指定的 Skill"""
        if name not in self._skills:
            raise ValueError(f"Skill '{name}' is not registered.")
        return self._skills[name]["callable"](**kwargs)

# 实例化全局注册表
agent_skills = SkillRegistry()

# ==========================================
# 使用示例 (可以提取到单独的文件如 weather_tool.py)
# ==========================================
@agent_skills.tool(description="查询指定城市的当前天气情况。")
def get_weather(location: str) -> str:
    # 实际应用中可以调用天气 API
    return f"{location} 的天气是晴朗，气温 25°C。"