import os
import json
import asyncio
import aiohttp
import re
from .tools import AgentToolExecutor
from .memory import MemoryManager

class AIAgentCore:
    """
    核心代理逻辑，负责接收用户输入、决策 (思考)、调用工具和响应。
    这是一个基于 ReAct/Chain-of-Thought 的框架结构。
    """
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API Key 不能为空")
        
        # 保存 API Key 和直接调用的 URL
        self.api_key = api_key
        #self.api_url = "https://api.openai.com/v1/chat/completions"
        self.api_url = "http://192.168.31.203:1234/v1/chat/completions"
        
        
        # 初始化工具和内存系统
        self.tool_executor = AgentToolExecutor()
        self.memory_manager = MemoryManager()

    async def chat(self, user_prompt: str, session_id: str | None = None):
        """
        与用户进行对话的核心方法。包含思考-行动-观察循环 (Think-Act-Observe)。
        """
        if session_id is None:
            session_id = self.memory_manager.start_new_session()
            print(f"✅ 启动新会话，ID: {session_id}")
        
        # 1. 添加用户输入到内存
        self.memory_manager.add_message(session_id, "user", user_prompt)

        try:
            # 动态生成工具描述，不再硬编码
            available_tools = list(self.tool_executor.tools.keys())
            tools_desc = f"可用工具: {', '.join(available_tools)}\n(注意：run_shell 需要 'command' 参数；search_files 需要 'pattern' 参数；read_file 需要 'file_path' 参数)"

            system_prompt = (
                "你是一个强大的全能本地 AI 助手。你的任务是通过思考并调用工具来帮用户解决各种复杂问题。\n"
                "请遵循 ReAct 模式：思考 -> 行动 -> 观察。\n"
                f"{tools_desc}\n"
                "如果需要调用工具，请严格按照以下 JSON 格式输出（必须放在 ```json 和 ``` 之间）：\n"
                "```json\n"
                "{\n"
                "  \"action\": \"工具名称\",\n"
                "  \"kwargs\": {\"参数名\": \"参数值\"}\n"
                "}\n"
                "```\n"
                "如果你已经获得了足够的信息，或者不需要调用工具就能回答，请直接向用户输出最终的解答内容（不要包含 JSON 工具调用块）。"
            )

            # 2. ReAct 循环 (限制最大迭代次数防止死循环)
            max_iterations = 10
            for i in range(max_iterations):
                print(f"\n[Agent] 🧠 正在思考并与 LLM 通信 (第 {i+1} 轮)...")
                
                # 获取 LLM 响应
                response_content = await self._llm_call(system_prompt, session_id)
                
                # 记录助手的思考过程 (关键：这让模型在下一轮知道自己刚刚思考过什么)
                self.memory_manager.add_message(session_id, "assistant", response_content)

                # 3. 尝试从模型响应中提取 JSON 工具调用指令
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL)
                
                if json_match:
                    try:
                        # 提取并打印大模型的思考过程 (解释它为什么要调用这个工具)
                        thought_process = response_content[:json_match.start()].strip()
                        if thought_process:
                            print(f"\n[Agent 思考过程]:\n{thought_process}")

                        action_data = json.loads(json_match.group(1))
                        tool_name = action_data.get("action")
                        kwargs = action_data.get("kwargs", action_data.get("args", {})) 
                        
                        if "path" in kwargs and "file_path" not in kwargs:
                            kwargs["file_path"] = kwargs.pop("path")

                        # 4. 拦截并请求用户授权
                        print(f"\n⚠️ [安全拦截] Agent 申请调用工具: '{tool_name}'")
                        print(f"   执行参数: {json.dumps(kwargs, ensure_ascii=False)}")
                        user_approval = input("   是否允许执行？(Y/n): ").strip().lower()
                        
                        if user_approval in ['', 'y', 'yes']:
                            # 用户同意，执行工具
                            observation = self.tool_executor.invoke(tool_name, **kwargs)
                            self.memory_manager.add_message(session_id, "tool", observation)
                        else:
                            # 用户拒绝，将结果返回给大模型让其重新决策
                            print("   🚫 已拒绝执行该工具。")
                            observation = "【系统提示：用户拒绝了该工具的执行申请。请调整你的策略，或者直接向用户回复。】"
                            self.memory_manager.add_message(session_id, "tool", observation)
                    except Exception as e:
                        error_msg = f"工具解析或执行出错: {e}"
                        print(f"\n[Agent] 🔴 {error_msg}")
                        self.memory_manager.add_message(session_id, "tool", error_msg)
                    # 继续下一轮循环 (模型会收到包含 tool 结果的历史记录并继续思考)
                else:
                    # 如果没有调用工具，说明模型已经给出了最终答案，直接退出循环
                    print("\n[Agent] 💬 任务完成，正在回复用户。")
                    return response_content

            # 如果超出循环次数还没结束
            timeout_msg = "🛑 达到最大思考轮数，任务已被迫终止。"
            self.memory_manager.add_message(session_id, "assistant", timeout_msg)
            return timeout_msg

        except Exception as e:
            error_msg = f"🛑 发生致命错误：{e}"
            self.memory_manager.add_message(session_id, "assistant", error_msg)
            return error_msg

    async def _llm_call(self, system_prompt: str, session_id: str) -> str:
        """内部方法，通过直接发起 HTTP 请求处理与 LLM 的通信。"""
        print("...等待LLM响应...")
        
        # 组装请求的消息列表：系统提示词 + 历史上下文
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.memory_manager.get_context(session_id))
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-3.5-turbo",  # 可根据需要更改模型版本
            "messages": messages
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"HTTP Error {response.status}: {error_text}")
                
                response_data = await response.json()
                return response_data["choices"][0]["message"]["content"]