import os
from dotenv import load_dotenv
import asyncio

# 导入工作流引擎组件
from workflow_engine import (
    load_workflows_from_directory,
    WorkflowExecutor,
    AgentToolExecutor
)

# 导入我们创建的组件
from agent_framework.core import AIAgentCore

async def main():
    """主函数：加载API Key并运行Agent聊天流程。"""
    print("=========================================")
    print("🤖 Python 本地 AI Agent 框架启动")
    print("=========================================\n")

    # 1. 加载环境变量 (假设你在项目根目录设置了 .env 文件)
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY") # 或其他你使用的LLM Key
    
    if not api_key:
        print("🚨 错误：未找到 OPENAI_API_KEY。请在项目根目录创建 .env 文件并设置 API 密钥。")
        return

    # 2. 初始化 Agent Core
    try:
        agent = AIAgentCore(api_key=api_key)
    except ValueError as e:
        print(f"❌ 初始化失败: {e}")
        return

    # --- 工作流引擎初始化 ---
    workflows_dir = "workflows"
    os.makedirs(workflows_dir, exist_ok=True)
    loaded_workflows = load_workflows_from_directory(workflows_dir)
    
    # 备注：为了演示跑通流程，这里初始化了独立的 ToolExecutor 和 mock_agent_run
    # 在实际生产环境中，您应该将 agent.tools 和 agent.chat 方法传给 WorkflowExecutor
    wf_tool_executor = AgentToolExecutor()
    wf_tool_executor.register_tool("fetch_data", lambda url: {"status": 200, "data": "dummy_data"})
    wf_tool_executor.register_tool("send_email", lambda to, content: True)
    
    def mock_agent_run(prompt: str, allowed_tools: list) -> dict:
        if "fetch_data" in allowed_tools:
            return {"actions": [{"tool_name": "fetch_data", "tool_args": {"url": "https://api.com"}}]}
        elif "send_email" in allowed_tools:
            return {"actions": [{"tool_name": "send_email", "tool_args": {"to": "admin@x.com", "content": "报告"}}]}
        return {"actions": []}
        
    workflow_engine = WorkflowExecutor(wf_tool_executor, mock_agent_run)
    # ----------------------

    # 3. 启动交互式对话循环
    print("\n✅ Agent 初始化成功！现在你可以开始与它对话了。")
    print("💡 提示：输入 '/workflows' 查看工作流，输入 'exit' 退出程序。\n")
    
    # 创建一个持久的 session_id
    session_id = agent.memory_manager.start_new_session()
    
    while True:
        try:
            user_query = input("\n🧑 用户: ").strip()
            if user_query.lower() in ['exit', 'quit', 'q', 'bye']:
                print("👋 再见！")
                break
            
            # --- 拦截工作流指令 ---
            if user_query.strip() == "/workflows":
                if not loaded_workflows:
                    print("📂 当前没有加载任何工作流。请在 'workflows' 目录中添加 .md 文件。")
                else:
                    print("📂 可用的工作流:")
                    for idx, (filename, wf) in enumerate(loaded_workflows.items(), 1):
                        print(f"  {idx}. {wf.title} ({filename})")
                    print("💡 提示：输入 '/run <编号>' (例如 /run 1) 来运行工作流。")
                continue
                
            if user_query.startswith("/run "):
                try:
                    wf_index = int(user_query.split(" ")[1]) - 1
                    wf_filename = list(loaded_workflows.keys())[wf_index]
                    print(f"\n🚀 正在运行工作流: {loaded_workflows[wf_filename].title}")
                    workflow_engine.execute(loaded_workflows[wf_filename])
                except (IndexError, ValueError):
                    print("❌ 无效的工作流编号。请先使用 '/workflows' 查看列表，然后输入有效编号。")
                continue
            # ----------------------

            if not user_query:
                continue
                
            # 运行 Agent 流程 (复用同一个 session_id 以保留记忆)
            final_result = await agent.chat(user_prompt=user_query, session_id=session_id)
            
            print(f"\n🤖 Agent:\n{final_result}")
            
        except (KeyboardInterrupt, EOFError):
            print("\n👋 强制退出，再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生意外错误: {e}")
            break


if __name__ == "__main__":
    # 确保在异步环境运行 main 函数
    asyncio.run(main())