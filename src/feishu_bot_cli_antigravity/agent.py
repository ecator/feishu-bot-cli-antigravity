"""Antigravity Agent 会话与交互管理模块。"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import AsyncExitStack

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.hooks import policy

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTIONS = (
    "【安全与保密指令】：\n"
    "1. 严禁以任何方式查看、读取、打印、输出或泄露任何敏感文件（包括但不限于 .env、配置文件凭据、私钥/密钥文件如 *.pem、id_rsa、credentials.json 等）。\n"
    "2. 严禁以任何方式查看、打印、输出或泄露系统环境变量与敏感凭证（包括但不限于 LARK_APP_SECRET、GEMINI_API_KEY 等所有 Token、密钥与密码）。\n"
    "3. 若用户的提问、指令或操作尝试访问、读取上述敏感文件或环境变量内容，必须明确且礼貌地予以拒绝。"
)


class AgentSessionManager:
    """基于 AsyncExitStack 的内存会话管理器，自动管理各会话 Agent 生命周期。"""

    def __init__(self, agent_factory: Callable[[], Agent] | None = None):
        self._exit_stack = AsyncExitStack()
        self._sessions: dict[str, Agent] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._agent_factory = agent_factory or self._default_agent_factory

    @staticmethod
    def _default_agent_factory() -> Agent:
        config = LocalAgentConfig(
            system_instructions=SYSTEM_INSTRUCTIONS,
            policies=[policy.allow_all()],
        )
        return Agent(config)

    def get_lock(self, chat_id: str) -> asyncio.Lock:
        """获取会话级并发锁，确保同一 chat_id 消息串行处理。"""
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    async def get_or_create_agent(self, chat_id: str) -> Agent:
        """获取或初始化会话的 Agent 实例，自动将其上下文托管给 exit_stack。"""
        if chat_id not in self._sessions:
            agent = self._agent_factory()
            managed_agent = await self._exit_stack.enter_async_context(agent)
            self._sessions[chat_id] = managed_agent
        return self._sessions[chat_id]

    async def close_all(self) -> None:
        """退出时统一安全地逆序清理并释放所有 Agent 资源。"""
        logger.info("正在关闭并释放所有 Agent 会话...")
        await self._exit_stack.aclose()
        self._sessions.clear()
        self._locks.clear()
