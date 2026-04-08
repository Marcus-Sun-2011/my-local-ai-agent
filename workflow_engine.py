import re
import os
import logging
from typing import Dict, List, Any, Callable
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ==========================================
# 1. 数据模型 (基于 Roadmap Phase 2)
# ==========================================
class WorkflowStep(BaseModel):
    step_id: str
    title: str
    tools: List[str] = []
    dependencies: List[str] = []
    instruction: str

class MarkdownWorkflow(BaseModel):
    title: str
    steps: List[WorkflowStep]

# ==========================================
# 1.5 解析 Markdown 工作流文件
# ==========================================
def parse_markdown_workflow(md_content: str) -> MarkdownWorkflow:
    """
    从规范的 Markdown 文本中解析出 MarkdownWorkflow 对象
    """
    # 解析工作流标题 (# 标题)
    title_match = re.search(r'^#\s+(.+)', md_content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "未命名工作流"
    
    steps = []
    # 匹配形如 "## Step 1: 获取数据" 到下一个 Step 或结尾的内容区块
    step_matches = re.finditer(r'##\s+Step\s+([^:]+):\s+(.*?)\n(.*?)(?=##\s+Step|\Z)', md_content, re.DOTALL | re.IGNORECASE)
    
    for match in step_matches:
        step_id = match.group(1).strip()
        step_title = match.group(2).strip()
        content = match.group(3)
        
        # 解析工具、依赖和指令 (兼容带有加粗 ** 的写法)
        tools_match = re.search(r'-\s+\*?\*?Tools\*?\*?:\s*(.*)', content, re.IGNORECASE)
        deps_match = re.search(r'-\s+\*?\*?Dependencies\*?\*?:\s*(.*)', content, re.IGNORECASE)
        inst_match = re.search(r'-\s+\*?\*?Instruction\*?\*?:\s*(.*)', content, re.IGNORECASE)
        
        tools = [t.strip() for t in tools_match.group(1).split(',')] if tools_match and tools_match.group(1).strip() else []
        deps = [d.strip() for d in deps_match.group(1).split(',')] if deps_match and deps_match.group(1).strip() else []
        instruction = inst_match.group(1).strip() if inst_match else ""
        
        steps.append(WorkflowStep(
            step_id=step_id, title=step_title, tools=tools, dependencies=deps, instruction=instruction
        ))
        
    return MarkdownWorkflow(title=title, steps=steps)

# ==========================================
# 1.6 从目录批量加载工作流
# ==========================================
def load_workflows_from_directory(directory: str) -> Dict[str, MarkdownWorkflow]:
    """
    扫描指定目录，加载所有 Markdown 工作流文件
    返回格式: {"filename.md": MarkdownWorkflow}
    """
    workflows = {}
    if not os.path.exists(directory):
        logging.warning(f"工作流目录 '{directory}' 不存在，跳过加载。")
        return workflows
        
    for filename in os.listdir(directory):
        if filename.endswith(".md"):
            filepath = os.path.join(directory, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                workflow = parse_markdown_workflow(content)
                workflows[filename] = workflow
                logging.info(f"📂 已加载工作流: {workflow.title} ({filename})")
    return workflows

# ==========================================
# 2. AgentToolExecutor (集成注册表模式)
# ==========================================
class AgentToolExecutor:
    """
    核心工具执行器 (对应 Roadmap Phase 1)
    负责维护工具注册表并执行具体工具逻辑
    """
    def __init__(self):
        self._registry: Dict[str, Callable] = {}

    def register_tool(self, name: str, func: Callable):
        """注册工具的方法，未来可优化为 @tool 装饰器"""
        self._registry[name] = func
        logging.info(f"🔧 工具已注册: {name}")

    def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """执行具体工具"""
        if tool_name not in self._registry:
            raise ValueError(f"未找到工具: {tool_name}")
        try:
            logging.info(f"🛠️ 执行工具 [{tool_name}] 参数: {kwargs}")
            return self._registry[tool_name](**kwargs)
        except Exception as e:
            logging.error(f"❌ 工具 [{tool_name}] 执行异常: {e}")
            raise e

# ==========================================
# 3. WorkflowExecutor (工作流引擎)
# ==========================================
class WorkflowExecutor:
    def __init__(self, tool_executor: AgentToolExecutor, llm_agent_run_method: Callable):
        """
        :param tool_executor: 注入现有的 AgentToolExecutor
        :param llm_agent_run_method: 注入你的核心 LLM Agent 调用方法
        """
        self.tool_executor = tool_executor
        self.agent_run = llm_agent_run_method
        self.context_memory: Dict[str, Any] = {}

    def execute(self, workflow: MarkdownWorkflow):
        logging.info(f"🚀 启动工作流: {workflow.title}")
        
        for step in workflow.steps:
            logging.info(f"▶️ 正在处理步骤: {step.title}")
            
            # 1. 组装上下文 Prompt
            prompt = f"指令: {step.instruction}\n"
            if step.dependencies:
                prompt += "前置依赖数据:\n"
                for dep in step.dependencies:
                    for key, val in self.context_memory.items():
                        if dep in key:
                            prompt += f"- [{key}]: {val}\n"

            # 2. 调用 LLM Agent
            # 这里假设 agent_run 返回的是一个包含决定调用什么工具及参数的结构化结果
            # 实际场景中，结合 Phase 2，这里会利用 Function Calling 返回 JSON
            llm_decision = self.agent_run(prompt=prompt, allowed_tools=step.tools)
            
            # 3. 将 LLM 的决策转交回 AgentToolExecutor 执行
            step_result = []
            for action in llm_decision.get("actions", []):
                tool_name = action["tool_name"]
                tool_args = action["tool_args"]
                
                # 调用集成的 AgentToolExecutor
                result = self.tool_executor.execute_tool(tool_name, **tool_args)
                step_result.append(result)
            
            # 4. 记录上下文，供后续依赖此步骤的流程使用
            self.context_memory[step.title] = step_result
            logging.info(f"✅ 步骤完成: {step.title} | 结果: {step_result}\n")

        logging.info("🎉 工作流全部执行完毕！")

# ==========================================
# 4. 集成测试示例
# ==========================================
if __name__ == "__main__":
    # 1. 初始化并注册工具
    tool_executor = AgentToolExecutor()
    tool_executor.register_tool("fetch_data", lambda url: {"status": 200, "data": "dummy_data"})
    tool_executor.register_tool("send_email", lambda to, content: True)

    # 2. 模拟 LLM Agent 的 ReAct 解析逻辑 (对应 Phase 2)
    def mock_agent_run(prompt: str, allowed_tools: List[str]) -> Dict:
        # 实际项目中，这里会调用 OpenAI/Anthropic，并让其输出 Function Calling JSON
        if "fetch_data" in allowed_tools:
            return {"actions": [{"tool_name": "fetch_data", "tool_args": {"url": "https://api.com"}}]}
        elif "send_email" in allowed_tools:
            return {"actions": [{"tool_name": "send_email", "tool_args": {"to": "admin@x.com", "content": "报告"}}]}
        return {"actions": []}

    # 3. 从目录加载所有工作流 (假设项目根目录下有个 workflows 文件夹)
    workflows_dir = "workflows"
    os.makedirs(workflows_dir, exist_ok=True) # 如果没有该目录，自动创建一个以供测试
    
    loaded_workflows = load_workflows_from_directory(workflows_dir)
    workflow_engine = WorkflowExecutor(tool_executor, mock_agent_run)

    # 4. 执行找到的第一个工作流 (如果有的话)
    if loaded_workflows:
        first_workflow_filename = list(loaded_workflows.keys())[0]
        workflow_engine.execute(loaded_workflows[first_workflow_filename])
    else:
        logging.info(f"在 '{workflows_dir}' 目录中没有找到工作流，请添加 .md 文件后再试。")