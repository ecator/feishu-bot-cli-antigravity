from unittest.mock import AsyncMock, MagicMock

import pytest
from lark_channel import ResourceDescriptor

from feishu_bot_cli_antigravity.channel import FeishuBotChannel
from feishu_bot_cli_antigravity.config import Config


@pytest.fixture
def mock_config():
    return Config(
        lark_app_id="cli_test",
        lark_app_secret="sec_test",
        log_level="INFO",
    )


@pytest.fixture
def mock_sdk_channel():
    mock = MagicMock()
    mock.download_resource = AsyncMock(return_value=None)
    mock.add_typing_reaction = AsyncMock(return_value="reaction_123")
    mock.remove_typing_reaction = AsyncMock(return_value=True)
    mock.stream = AsyncMock(return_value=None)
    mock.send = AsyncMock(return_value=MagicMock(success=True))
    mock.stop = MagicMock()
    return mock


class MockChatResponse:
    def __init__(self, tokens=None, text_content="Hello from Agent"):
        self.tokens = tokens if tokens is not None else ["Hello", " from Agent"]
        self.text_content = text_content

    def __aiter__(self):
        self._iter = iter(list(self.tokens))
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    async def text(self):
        return self.text_content


@pytest.fixture
def mock_session_manager():
    manager = MagicMock()
    agent = MagicMock()

    agent.chat = AsyncMock(return_value=MockChatResponse())
    manager.get_or_create_agent = AsyncMock(return_value=agent)
    manager.close_all = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_on_message_ignores_bot_sender(mock_config, mock_sdk_channel, mock_session_manager):
    bot_channel = FeishuBotChannel(
        config=mock_config,
        session_manager=mock_session_manager,
        channel=mock_sdk_channel,
    )
    msg = MagicMock()
    msg.sender_is_bot = True

    await bot_channel.on_message(msg)
    mock_session_manager.get_or_create_agent.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_filter_chat_id(mock_config, mock_sdk_channel, mock_session_manager):
    bot_channel = FeishuBotChannel(
        config=mock_config,
        filter_chat_id="allowed_chat",
        session_manager=mock_session_manager,
        channel=mock_sdk_channel,
    )
    msg = MagicMock()
    msg.sender_is_bot = False
    msg.chat_id = "other_chat"

    await bot_channel.on_message(msg)
    mock_session_manager.get_or_create_agent.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_with_downloaded_file(mock_config, mock_sdk_channel, mock_session_manager):
    bot_channel = FeishuBotChannel(
        config=mock_config,
        session_manager=mock_session_manager,
        channel=mock_sdk_channel,
    )

    msg = MagicMock()
    msg.sender_is_bot = False
    msg.chat_id = "target_chat"
    msg.id = "om_msg123"
    msg.content_text = "请帮我分析代码"
    msg.sender_name = "UserA"
    msg.sender_id = "ou_123"
    msg.chat_type = "p2p"
    msg.create_time = 1710000000000

    # 模拟附件资源
    res_descriptor = ResourceDescriptor(
        type="file",
        file_key="file_key_abc",
        file_name="script.py",
    )
    msg.resources = [res_descriptor]

    # 模拟下载文件返回内存字节
    file_bytes = b"print('Hello world!')\n"
    mock_sdk_channel.download_resource.return_value = file_bytes

    await bot_channel.on_message(msg)

    # 验证 download_resource 调用参数
    mock_sdk_channel.download_resource.assert_awaited_once_with(
        file_key="file_key_abc",
        resource_type="file",
        message_id="om_msg123",
    )

    # 验证 Agent.chat 收到了包含元数据、文本与内存 Document 对象的列表
    agent = await mock_session_manager.get_or_create_agent("target_chat")
    agent.chat.assert_awaited_once()
    chat_args = agent.chat.call_args[0][0]
    assert isinstance(chat_args, list)
    assert len(chat_args) == 3
    # 第一个元素为 YAML Frontmatter 元数据
    assert chat_args[0].startswith("---\n")
    assert "from: feishu" in chat_args[0]
    assert "chat_id: target_chat" in chat_args[0]
    assert "sender_id: ou_123" in chat_args[0]
    assert "message_id: om_msg123" in chat_args[0]
    assert "chat_type: p2p" in chat_args[0]
    # 第二个元素为用户文本
    assert chat_args[1] == "请帮我分析代码"
    # 第三个元素为通过 utils.create_media_from_bytes 构建的 Document
    assert hasattr(chat_args[2], "data")
    assert chat_args[2].data == file_bytes


@pytest.mark.asyncio
async def test_on_message_text_only(mock_config, mock_sdk_channel, mock_session_manager):
    bot_channel = FeishuBotChannel(
        config=mock_config,
        session_manager=mock_session_manager,
        channel=mock_sdk_channel,
    )

    msg = MagicMock()
    msg.sender_is_bot = False
    msg.chat_id = "target_chat"
    msg.id = "om_text_only"
    msg.content_text = "你好，助手"
    msg.sender_name = "UserB"
    msg.sender_id = "ou_456"
    msg.chat_type = "group"
    msg.create_time = 1710000000000
    msg.resources = []

    await bot_channel.on_message(msg)

    agent = await mock_session_manager.get_or_create_agent("target_chat")
    agent.chat.assert_awaited_once()
    chat_args = agent.chat.call_args[0][0]
    assert isinstance(chat_args, list)
    assert len(chat_args) == 2
    assert chat_args[0].startswith("---\n")
    assert "from: feishu" in chat_args[0]
    assert "chat_type: group" in chat_args[0]
    assert chat_args[1] == "你好，助手"


@pytest.mark.asyncio
async def test_send_message_text(mock_config, mock_sdk_channel, mock_session_manager):
    bot_channel = FeishuBotChannel(
        config=mock_config,
        session_manager=mock_session_manager,
        channel=mock_sdk_channel,
    )

    await bot_channel.send_message("chat_test", message="Hello!", message_type="markdown")
    mock_sdk_channel.send.assert_awaited_once_with("chat_test", {"markdown": "Hello!"})


@pytest.mark.asyncio
async def test_send_message_single_image_with_caption(tmp_path, mock_config, mock_sdk_channel, mock_session_manager):
    img_file = tmp_path / "test.png"
    img_file.write_bytes(b"image_bytes")

    bot_channel = FeishuBotChannel(
        config=mock_config,
        session_manager=mock_session_manager,
        channel=mock_sdk_channel,
    )

    await bot_channel.send_message("chat_test", message="这是图片说明", file_paths=[str(img_file)])
    mock_sdk_channel.send.assert_awaited_once_with(
        "chat_test",
        {"image": {"source": b"image_bytes"}, "caption": "这是图片说明"},
    )


@pytest.mark.asyncio
async def test_send_message_multiple_files_and_text(tmp_path, mock_config, mock_sdk_channel, mock_session_manager):
    file1 = tmp_path / "doc.pdf"
    file1.write_bytes(b"pdf_content")
    file2 = tmp_path / "photo.jpg"
    file2.write_bytes(b"jpg_content")

    bot_channel = FeishuBotChannel(
        config=mock_config,
        session_manager=mock_session_manager,
        channel=mock_sdk_channel,
    )

    await bot_channel.send_message(
        "chat_test",
        message="这是多文件说明",
        file_paths=[str(file1), str(file2)],
    )

    # 包含 2 个文件 + 1 条文本，共 3 次发送
    assert mock_sdk_channel.send.call_count == 3
    calls = mock_sdk_channel.send.call_args_list
    assert calls[0].args == ("chat_test", {"file": {"source": b"pdf_content", "file_name": "doc.pdf"}})
    assert calls[1].args == ("chat_test", {"image": {"source": b"jpg_content"}})
    assert calls[2].args == ("chat_test", {"markdown": "这是多文件说明"})


@pytest.mark.asyncio
async def test_send_message_single_file_string(tmp_path, mock_config, mock_sdk_channel, mock_session_manager):
    file1 = tmp_path / "data.csv"
    file1.write_bytes(b"a,b,c")

    bot_channel = FeishuBotChannel(
        config=mock_config,
        session_manager=mock_session_manager,
        channel=mock_sdk_channel,
    )

    # 验证传入单个字符串路径
    await bot_channel.send_message("chat_test", file_paths=str(file1))
    mock_sdk_channel.send.assert_awaited_once_with(
        "chat_test",
        {"file": {"source": b"a,b,c", "file_name": "data.csv"}},
    )


def test_feishu_bot_channel_work_dir(tmp_path, mock_config, mock_sdk_channel):
    channel = FeishuBotChannel(
        config=mock_config,
        channel=mock_sdk_channel,
        work_dir=tmp_path,
    )
    assert channel.session_manager.work_dir == tmp_path
