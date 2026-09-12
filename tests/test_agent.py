import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from feishu_bot_cli_antigravity.agent import AgentSessionManager


def test_agent_session_manager_locks():
    manager = AgentSessionManager()
    lock1 = manager.get_lock("chat_1")
    lock2 = manager.get_lock("chat_1")
    lock3 = manager.get_lock("chat_2")

    assert isinstance(lock1, asyncio.Lock)
    assert lock1 is lock2
    assert lock1 is not lock3


@pytest.mark.asyncio
async def test_agent_session_manager_lifecycle():
    mock_agent = MagicMock()
    mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
    mock_agent.__aexit__ = AsyncMock(return_value=None)

    agent_factory = MagicMock(return_value=mock_agent)
    manager = AgentSessionManager(agent_factory=agent_factory)

    # First access creates agent
    agent1 = await manager.get_or_create_agent("chat_1")
    assert agent1 is mock_agent
    assert agent_factory.call_count == 1
    mock_agent.__aenter__.assert_awaited_once()

    # Second access returns cached agent
    agent2 = await manager.get_or_create_agent("chat_1")
    assert agent2 is mock_agent
    assert agent_factory.call_count == 1

    # Close all
    await manager.close_all()
    mock_agent.__aexit__.assert_awaited_once()
    assert len(manager._sessions) == 0
    assert len(manager._locks) == 0


def test_default_agent_factory():
    agent = AgentSessionManager._default_agent_factory()
    assert agent._config.system_instructions is not None
    assert "敏感文件" in agent._config.system_instructions
    assert "环境变量" in agent._config.system_instructions
    assert any(p.name == "allow_all" for p in agent._config.policies)
