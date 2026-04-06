import time
from typing import List, Dict, Any

# 使用 Pydantic 在生产环境中定义更严格的结构，这里简化为字典。
ConversationMessage = Dict[str, str]

class MemoryManager:
    """
    负责管理和存储对话历史记录（内存）。
    支持会话隔离和上下文摘要。
    """

    def __init__(self):
        # {session_id: [message1, message2, ...]}
        self.sessions: Dict[str, List[ConversationMessage]] = {}

    def start_new_session(self) -> str:
        """开始一个新的会话，返回唯一的 Session ID。"""
        session_id = f"session_{int(time.time() * 1000)}"
        self.sessions[session_id] = []
        return session_id

    def add_message(self, session_id: str, role: str, content: str):
        """向指定会话中添加一条消息。
        Role 可以是 'user', 'assistant' (AI), 或 'tool' (系统/工具返回)。
        """
        if session_id not in self.sessions:
            raise ValueError(f"不存在的会话ID: {session_id}")
            
        message = {"role": role, "content": content}
        self.sessions[session_id].append(message)

    def get_context(self, session_id: str) -> List[ConversationMessage]:
        """获取当前会话的所有消息，作为 LLM 的上下文。"""
        if session_id not in self.sessions:
            return []
        # 返回副本，防止外部修改导致数据污染
        return list(self.sessions[session_id])

    def summarize_context(self, session_id: str) -> str | None:
        """
        TODO: 占位函数。在实际应用中，这里会调用 LLM (如 OpenAI/Anthropic)
        将当前上下文总结成一个精简的字符串，以防止超出模型的 Token 上限。
        """
        if not self.sessions[session_id]:
            return None
            
        # 假设我们已经有了一个外部LLM调用函数来做摘要
        print(f"[Memory] --- WARNING: Context summarization needed for session {session_id} ---")
        return f"【已摘要】这是会话 {session_id} 的精简上下文摘要，用于延续对话。"