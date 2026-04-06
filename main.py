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

    # 3. 定义用户请求
    user_query = "请帮我审查一下 `agent_framework/memory.py` 这个代码文件，看看在并发场景下有没有潜在的隐患，或者类型提示方面有什么可以改进的。"

    # 4. 运行 Agent 流程
    print(f"\n\n🚀 用户发起请求: '{user_query}'")
    final_result = await agent.chat(user_prompt=user_query)

    print("\n\n=========================================")
    print("🎉 对话结束，最终结果:")
    print(final_result)
    print("=========================================\n")


if __name__ == "__main__":
    # 确保在异步环境运行 main 函数
    asyncio.run(main())