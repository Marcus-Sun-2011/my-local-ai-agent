import os
from dotenv import load_dotenv
import asyncio

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

    # 3. 启动交互式对话循环
    print("\n✅ Agent 初始化成功！现在你可以开始与它对话了。")
    print("💡 提示：输入 'exit', 'quit', 'q' 或 按 Ctrl+C/Ctrl+D 退出程序。\n")
    
    # 创建一个持久的 session_id
    session_id = agent.memory_manager.start_new_session()
    
    while True:
        try:
            user_query = input("\n🧑 用户: ").strip()
            if user_query.lower() in ['exit', 'quit', 'q', 'bye']:
                print("👋 再见！")
                break
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