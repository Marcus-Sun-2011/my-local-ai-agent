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
            # --- LLM 调用占位符：构建 System Prompt 和 Message History ---
            system_prompt = (
                "你是一个资深的顶级代码审查员 (Code Reviewer)。你的任务是严格检查用户提供的代码或文件，"
                "寻找潜在的 Bug、安全漏洞、性能瓶颈以及代码风格规范(PEP 8等)问题，并提供优化建议。"
                "你可以使用 `read_file` 工具读取目标文件内容，或使用 `run_shell` 执行静态扫描(如 pylint)。"
                "请遵循 ReAct 模式：思考 -> 行动 -> 观察。\n"
                "如果需要调用工具，请严格按照以下 JSON 格式输出（必须放在 ```json 和 ``` 之间）：\n"
                "```json\n"
                "{\n"
                "  \"action\": \"工具名称 (如 read_file)\",\n"
                "  \"kwargs\": {\"file_path\": \"要读取的文件路径\"}\n"
                "}\n"
                "```\n"
                "如果你已经获得了足够的信息，请直接输出最终的代码审查报告。"
            )

            # 2. 调用 LLM，让它进行推理并决定下一步 (Thinking & Acting)
            print("\n[Agent] 🧠 正在构建 Prompt 并与 LLM 通信...")
            
            # TODO: 在实际项目中，这里需要复杂的 Pydantic Tool Calling 或 Function Calling 逻辑来从模型获取工具调用指令。
            # 为了框架展示，我们模拟一次成功调用：

            response_content = await self._llm_call(system_prompt, session_id)

            # 3. 尝试从模型响应中提取 JSON 工具调用指令
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            
            if json_match:
                try:
                    action_data = json.loads(json_match.group(1))
                    tool_name = action_data.get("action")
                    kwargs = action_data.get("kwargs", action_data.get("args", {})) # 兼容模型使用 args 字段
                    
                    # 容错：如果模型使用了 path 而不是 file_path
                    if "path" in kwargs and "file_path" not in kwargs:
                        kwargs["file_path"] = kwargs.pop("path")

                    # 4. 执行工具 (Observation)
                    observation = self.tool_executor.invoke(tool_name, **kwargs)
                    print(f"\n[Agent] 🟢 工具 '{tool_name}' 观察结果已接收。")
                    
                    # 5. 将 Observation 添加回内存，并再次调用 LLM 进行最终总结
                    self.memory_manager.add_message(session_id, "tool", observation)
                    final_response = await self._llm_call(system_prompt + "\n请根据观察到的工具结果，给出详细的代码审查报告。", session_id)
                except Exception as e:
                    print(f"\n[Agent] 🔴 工具执行出错: {e}")
                    final_response = f"尝试执行工具时出错: {e}\n模型原始回复: {response_content}"
            else:
                # 直接文本回复或已包含结论
                print("\n[Agent] 💬 模型直接生成了回复。")
                final_response = response_content

        except Exception as e:
            final_response = f"🛑 发生致命错误：{e}"
            
        # 6. 将最终响应添加回内存并返回给用户
        self.memory_manager.add_message(session_id, "assistant", final_response)
        return final_response

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