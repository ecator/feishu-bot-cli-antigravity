from unittest.mock import patch

import pytest

from feishu_bot_cli_antigravity.cli import create_parser, main


def test_cli_parser_listen():
    parser = create_parser()

    # listen 无 chat_id
    args1 = parser.parse_args(["listen"])
    assert args1.command == "listen"
    assert args1.chat_id is None

    # listen 带 chat_id
    args2 = parser.parse_args(["listen", "--chat-id", "oc_12345"])
    assert args2.command == "listen"
    assert args2.chat_id == "oc_12345"

    # listen 带简写 -c
    args3 = parser.parse_args(["listen", "-c", "oc_abcde"])
    assert args3.chat_id == "oc_abcde"


def test_cli_parser_send_requires_chat_id():
    parser = create_parser()

    # send 缺少 --chat-id 必须报错退出
    with pytest.raises(SystemExit):
        parser.parse_args(["send", "-m", "hello"])

    # send 提供 --chat-id 正常解析
    args = parser.parse_args(["send", "--chat-id", "oc_12345", "-m", "hello world", "--type", "text"])
    assert args.command == "send"
    assert args.chat_id == "oc_12345"
    assert args.message == "hello world"
    assert args.message_type == "text"


def test_cli_parser_send_with_file():
    parser = create_parser()
    args = parser.parse_args(["send", "-c", "oc_123", "-f", "test.png"])
    assert args.chat_id == "oc_123"
    assert args.file_paths == ["test.png"]
    assert args.message_type == "markdown"

    # 支持同时指定多个文件
    args_multi = parser.parse_args(["send", "-c", "oc_123", "-f", "test.png", "data.csv"])
    assert args_multi.file_paths == ["test.png", "data.csv"]


def test_cli_main_validation_failure(monkeypatch):
    # 清空环境变量以触发校验错误
    monkeypatch.setenv("LARK_APP_ID", "")
    monkeypatch.setenv("LARK_APP_SECRET", "")

    ret = main(["listen"])
    assert ret == 1


@patch("feishu_bot_cli_antigravity.cli.run_send")
def test_cli_main_send_success(mock_run_send, monkeypatch):
    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "sec_test")

    ret = main(["send", "-c", "oc_target", "-m", "test message"])
    assert ret == 0
    mock_run_send.assert_called_once()


def test_cli_parser_send_stdin():
    parser = create_parser()

    # --stdin 参数
    args1 = parser.parse_args(["send", "-c", "oc_123", "--stdin"])
    assert args1.read_stdin is True
    assert args1.message is None

    # -s 参数简写
    args2 = parser.parse_args(["send", "-c", "oc_123", "-s"])
    assert args2.read_stdin is True
    assert args2.message is None

    # -m 与 --stdin 互斥，同时提供应报错退出
    with pytest.raises(SystemExit):
        parser.parse_args(["send", "-c", "oc_123", "-m", "hello", "--stdin"])


def test_resolve_send_message_from_stdin_flag(monkeypatch):
    import io

    from feishu_bot_cli_antigravity.cli import resolve_send_message

    parser = create_parser()
    args = parser.parse_args(["send", "-c", "oc_123", "--stdin"])

    markdown_input = "# Title\n\n- item 1\n- item 2"
    monkeypatch.setattr("sys.stdin", io.StringIO(markdown_input))

    msg = resolve_send_message(args)
    assert msg == markdown_input


def test_resolve_send_message_from_dash(monkeypatch):
    import io

    from feishu_bot_cli_antigravity.cli import resolve_send_message

    parser = create_parser()
    args = parser.parse_args(["send", "-c", "oc_123", "-m", "-"])

    markdown_input = "## Big Markdown Section\n\n```python\nprint(1)\n```"
    monkeypatch.setattr("sys.stdin", io.StringIO(markdown_input))

    msg = resolve_send_message(args)
    assert msg == markdown_input


def test_resolve_send_message_piped_automatic(monkeypatch):
    import io

    from feishu_bot_cli_antigravity.cli import resolve_send_message

    parser = create_parser()
    args = parser.parse_args(["send", "-c", "oc_123"])

    piped_input = "piped markdown text"
    fake_stdin = io.StringIO(piped_input)
    fake_stdin.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_stdin)

    msg = resolve_send_message(args)
    assert msg == piped_input


def test_resolve_send_message_empty_stdin_raises(monkeypatch):
    import io

    from feishu_bot_cli_antigravity.cli import resolve_send_message

    parser = create_parser()
    args = parser.parse_args(["send", "-c", "oc_123", "--stdin"])

    monkeypatch.setattr("sys.stdin", io.StringIO("   \n   "))

    with pytest.raises(ValueError, match="从标准输入读取到的内容为空"):
        resolve_send_message(args)


def test_read_stdin_content_utf8_buffer(monkeypatch):
    import io

    from feishu_bot_cli_antigravity.cli import read_stdin_content

    chinese_markdown = "# 飞书机器人分析报告\n\n- 运行正常\n- 数据准确"
    utf8_bytes = chinese_markdown.encode("utf-8")

    class MockStdinWithBuffer:
        def __init__(self, data: bytes):
            self.buffer = io.BytesIO(data)

        def read(self):
            # 模拟在 Windows 下以系统默认编码 (如 gbk) 可能会出错
            return self.buffer.read().decode("utf-8")

    monkeypatch.setattr("sys.stdin", MockStdinWithBuffer(utf8_bytes))
    result = read_stdin_content()
    assert result == chinese_markdown


def test_read_stdin_content_utf8_with_bom(monkeypatch):
    import io

    from feishu_bot_cli_antigravity.cli import read_stdin_content

    chinese_text = "### 带 BOM 的 UTF-8 标题\n\n正文内容"
    bom_utf8_bytes = b"\xef\xbb\xbf" + chinese_text.encode("utf-8")

    class MockStdinWithBuffer:
        def __init__(self, data: bytes):
            self.buffer = io.BytesIO(data)

    monkeypatch.setattr("sys.stdin", MockStdinWithBuffer(bom_utf8_bytes))
    result = read_stdin_content()
    assert result == chinese_text


@patch("feishu_bot_cli_antigravity.cli.run_send")
def test_cli_main_send_stdin_success(mock_run_send, monkeypatch):
    import io

    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "sec_test")
    monkeypatch.setattr("sys.stdin", io.StringIO("### Standard Input Markdown"))

    ret = main(["send", "-c", "oc_target", "--stdin"])
    assert ret == 0
    mock_run_send.assert_called_once()
    assert mock_run_send.call_args.kwargs["message"] == "### Standard Input Markdown"


@patch("feishu_bot_cli_antigravity.cli.run_send")
def test_cli_main_send_dash_message_success(mock_run_send, monkeypatch):
    import io

    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "sec_test")
    monkeypatch.setattr("sys.stdin", io.StringIO("Piped via -m -"))

    ret = main(["send", "-c", "oc_target", "-m", "-"])
    assert ret == 0
    mock_run_send.assert_called_once()
    assert mock_run_send.call_args.kwargs["message"] == "Piped via -m -"


@pytest.mark.asyncio
async def test_run_send_reads_dash_stdin(monkeypatch):
    import io

    from feishu_bot_cli_antigravity.cli import run_send
    from feishu_bot_cli_antigravity.config import Config

    monkeypatch.setattr("sys.stdin", io.StringIO("Content via stdin"))

    with patch("feishu_bot_cli_antigravity.cli.FeishuBotChannel") as mock_channel_cls:
        mock_channel = mock_channel_cls.return_value
        mock_channel.send_message = pytest.importorskip("unittest.mock").AsyncMock(return_value="ok")
        mock_channel.close = pytest.importorskip("unittest.mock").AsyncMock()

        config = Config(lark_app_id="app_id", lark_app_secret="sec")
        await run_send(
            chat_id="oc_test",
            message="-",
            file_paths=None,
            message_type="markdown",
            config=config,
        )

        mock_channel.send_message.assert_awaited_once_with(
            chat_id="oc_test",
            message="Content via stdin",
            file_paths=None,
            message_type="markdown",
        )

