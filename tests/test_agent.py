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


def test_load_mcp_config_file_not_found(tmp_path):
    from feishu_bot_cli_antigravity.agent import load_mcp_config

    # 未指定路径
    assert load_mcp_config() == []

    # 指定不存在的文件路径
    servers = load_mcp_config(tmp_path / ".agents" / "mcp_config.json")
    assert servers == []

    # 显式传递 None
    assert load_mcp_config(None) == []


def test_load_mcp_config_stdio_server(tmp_path):
    import json

    from google.antigravity.types import McpStdioServer

    from feishu_bot_cli_antigravity.agent import load_mcp_config

    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = agents_dir / "mcp_config.json"

    data = {
        "mcpServers": {
            "fetch": {
                "command": "uvx",
                "args": ["mcp-server-fetch"],
                "env": {"DEBUG": "1"},
                "timeout_seconds": 60,
                "enabled_tools": ["fetch_url"],
            }
        }
    }
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    servers = load_mcp_config(cfg_file)
    assert len(servers) == 1
    server = servers[0]
    assert isinstance(server, McpStdioServer)
    assert server.name == "fetch"
    assert server.command == "uvx"
    assert server.args == ["mcp-server-fetch"]
    assert server.env == {"DEBUG": "1"}
    assert server.timeout_seconds == 60
    assert server.enabled_tools == ["fetch_url"]


def test_load_mcp_config_http_server(tmp_path):
    import json

    from google.antigravity.types import McpStreamableHttpServer

    from feishu_bot_cli_antigravity.agent import load_mcp_config

    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = agents_dir / "mcp_config.json"

    data = {
        "mcpServers": {
            "remote_api": {
                "serverUrl": "https://api.example.com/sse",
                "headers": {"Authorization": "Bearer token123"},
                "timeout": 45.0,
                "sse_read_timeout": 600.0,
                "terminate_on_close": False,
                "disabled_tools": ["admin_delete"],
            }
        }
    }
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    servers = load_mcp_config(cfg_file)
    assert len(servers) == 1
    server = servers[0]
    assert isinstance(server, McpStreamableHttpServer)
    assert server.name == "remote_api"
    assert server.url == "https://api.example.com/sse"
    assert server.headers == {"Authorization": "Bearer token123"}
    assert server.timeout == 45.0
    assert server.sse_read_timeout == 600.0
    assert server.terminate_on_close is False
    assert server.disabled_tools == ["admin_delete"]


def test_load_mcp_config_env_expansion(tmp_path, monkeypatch):
    import json

    from google.antigravity.types import McpStdioServer

    from feishu_bot_cli_antigravity.agent import load_mcp_config

    monkeypatch.setenv("TEST_BIN", "python3")
    monkeypatch.setenv("TEST_KEY", "secret_value_xyz")

    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = agents_dir / "mcp_config.json"

    data = {
        "mcpServers": {
            "custom": {
                "command": "${TEST_BIN}",
                "args": ["-m", "${TEST_KEY}"],
                "env": {"API_TOKEN": "${TEST_KEY}"},
            }
        }
    }
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    servers = load_mcp_config(cfg_file)
    assert len(servers) == 1
    server = servers[0]
    assert isinstance(server, McpStdioServer)
    assert server.command == "python3"
    assert server.args == ["-m", "secret_value_xyz"]
    assert server.env == {"API_TOKEN": "secret_value_xyz"}


def test_load_mcp_config_alternative_structures(tmp_path):
    import json

    from feishu_bot_cli_antigravity.agent import load_mcp_config

    # 1. 扁平字典结构（无 mcpServers 外层）
    cfg_flat = tmp_path / "flat.json"
    cfg_flat.write_text(
        json.dumps({"flat_tool": {"command": "echo", "args": ["hello"]}}),
        encoding="utf-8",
    )
    servers1 = load_mcp_config(cfg_flat)
    assert len(servers1) == 1
    assert servers1[0].name == "flat_tool"

    # 2. 列表结构
    cfg_list = tmp_path / "list.json"
    cfg_list.write_text(
        json.dumps([{"name": "list_tool", "command": "echo", "args": ["world"]}]),
        encoding="utf-8",
    )
    servers2 = load_mcp_config(cfg_list)
    assert len(servers2) == 1
    assert servers2[0].name == "list_tool"


def test_load_mcp_config_sanitization_and_skipping(tmp_path):
    import json

    from feishu_bot_cli_antigravity.agent import load_mcp_config

    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = agents_dir / "mcp_config.json"

    data = {
        "mcpServers": {
            # 名称包含特殊字符（点和空格），应自动规范化为下划线
            "invalid.server name": {
                "command": "python",
            },
            # 缺失 command 且缺失 url，应跳过
            "bad_server": {
                "something_else": 123,
            },
            # 非字典对象，应跳过
            "not_a_dict": "invalid",
        }
    }
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    servers = load_mcp_config(cfg_file)
    assert len(servers) == 1
    assert servers[0].name == "invalid_server_name"


def test_load_mcp_config_invalid_json(tmp_path):
    from feishu_bot_cli_antigravity.agent import load_mcp_config

    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = agents_dir / "mcp_config.json"
    cfg_file.write_text("{corrupted_json: true", encoding="utf-8")

    with pytest.raises(ValueError, match="读取或解析 MCP 配置文件失败"):
        load_mcp_config(cfg_file)


def test_load_mcp_config_invalid_root_type(tmp_path):
    from feishu_bot_cli_antigravity.agent import load_mcp_config

    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = agents_dir / "mcp_config.json"
    cfg_file.write_text('"just a string"', encoding="utf-8")

    servers = load_mcp_config(cfg_file)
    assert servers == []


def test_agent_session_manager_with_work_dir_mcp(tmp_path):
    import json

    from feishu_bot_cli_antigravity.agent import AgentSessionManager

    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = agents_dir / "mcp_config.json"

    data = {
        "mcpServers": {
            "test_tool": {
                "command": "python",
                "args": ["-V"],
            }
        }
    }
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    manager = AgentSessionManager(work_dir=tmp_path)
    assert manager.work_dir == tmp_path

    # 验证 AgentSessionManager 委托给 _default_agent_factory 自动构造包含 MCP 服务与 workspaces 的 Agent
    agent = manager._agent_factory()
    assert len(agent._config.mcp_servers) == 1
    assert agent._config.mcp_servers[0].name == "test_tool"
    assert agent._config.workspaces == [str(tmp_path.resolve())]


def test_agent_session_manager_work_dir_controls_workspaces(tmp_path):
    from feishu_bot_cli_antigravity.agent import AgentSessionManager

    manager = AgentSessionManager(work_dir=tmp_path)
    agent = manager._agent_factory()

    # 验证 LocalAgentConfig 的 workspaces 正确设置为传入的 work_dir
    assert agent._config.workspaces == [str(tmp_path.resolve())]


def test_default_agent_factory_with_work_dir_only(tmp_path):
    import json

    from feishu_bot_cli_antigravity.agent import AgentSessionManager

    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = agents_dir / "mcp_config.json"
    cfg_file.write_text(
        json.dumps({"mcpServers": {"direct_tool": {"command": "echo"}}}),
        encoding="utf-8",
    )

    # 验证 _default_agent_factory 仅需 work_dir 参数，内部自动加载 mcp 配置
    agent = AgentSessionManager._default_agent_factory(work_dir=tmp_path)
    assert len(agent._config.mcp_servers) == 1
    assert agent._config.mcp_servers[0].name == "direct_tool"
    assert agent._config.workspaces == [str(tmp_path.resolve())]


def test_agent_session_manager_init_logging(tmp_path, caplog):
    import logging

    from feishu_bot_cli_antigravity.agent import AgentSessionManager

    with caplog.at_level(logging.INFO):
        _ = AgentSessionManager(work_dir=tmp_path)

    assert "初始化 Agent 会话管理器" in caplog.text
    assert "未检测到 MCP 配置文件" in caplog.text


def test_default_agent_factory_custom_models(tmp_path):
    from google.antigravity import types

    from feishu_bot_cli_antigravity.agent import AgentSessionManager

    agent = AgentSessionManager._default_agent_factory(
        work_dir=tmp_path,
        model="gemini-custom-text",
        image_model="custom-image-model",
    )

    model_map = {m.types[0]: m.name for m in agent._config.models}
    assert model_map[types.ModelType.TEXT] == "gemini-custom-text"
    assert model_map[types.ModelType.IMAGE] == "custom-image-model"
    assert agent._config.model == "gemini-custom-text"


def test_default_agent_factory_default_models(tmp_path):
    from google.antigravity import types

    from feishu_bot_cli_antigravity.agent import AgentSessionManager

    agent = AgentSessionManager._default_agent_factory(work_dir=tmp_path)
    assert agent._config.model is None
    # 默认回退到 SDK 内置文本和生图模型
    model_map = {m.types[0]: m.name for m in agent._config.models}
    assert model_map[types.ModelType.TEXT] == "gemini-3.8-flash"
    assert model_map[types.ModelType.IMAGE] == "gemini-3.1-flash-lite-image"


def test_agent_session_manager_model_parameters(tmp_path, caplog):
    import logging

    from feishu_bot_cli_antigravity.agent import AgentSessionManager

    with caplog.at_level(logging.INFO):
        manager = AgentSessionManager(
            work_dir=tmp_path,
            model="my-text-model",
            image_model="my-image-model",
        )

    assert "配置主模型: my-text-model" in caplog.text
    assert "配置生图模型: my-image-model" in caplog.text
    assert manager.model == "my-text-model"
    assert manager.image_model == "my-image-model"

    agent = manager._agent_factory()
    assert agent._config.model == "my-text-model"



