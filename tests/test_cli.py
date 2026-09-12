import logging
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


@patch("feishu_bot_cli_antigravity.cli.run_listen")
def test_cli_main_validation_failure(mock_run_listen, monkeypatch, tmp_path):
    # 清空环境变量并在空临时目录下运行以触发校验错误（避免受当前仓库 .env 影响）
    monkeypatch.setenv("LARK_APP_ID", "")
    monkeypatch.setenv("LARK_APP_SECRET", "")
    monkeypatch.chdir(tmp_path)

    ret = main(["listen"])
    assert ret == 1
    mock_run_listen.assert_not_called()


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


def test_cli_parser_work_dir():
    parser = create_parser()

    # 根 parser 级别支持 --work-dir (放在子命令前)
    args1 = parser.parse_args(["--work-dir", "/custom/path", "listen"])
    assert args1.work_dir == "/custom/path"

    # 根 parser 级别支持简写 -w (放在子命令前)
    args2 = parser.parse_args(["-w", "/custom/path2", "listen"])
    assert args2.work_dir == "/custom/path2"

    # send 子命令配合全局 --work-dir
    args3 = parser.parse_args(["--work-dir", "/custom/path3", "send", "-c", "oc_123", "-m", "hi"])
    assert args3.work_dir == "/custom/path3"
    assert args3.chat_id == "oc_123"
    assert args3.message == "hi"

    # send 子命令配合全局 -w
    args4 = parser.parse_args(["-w", "/custom/path4", "send", "-c", "oc_123", "-m", "hi"])
    assert args4.work_dir == "/custom/path4"

    # 子命令后传参应报错 (已移至根 parser)
    with pytest.raises(SystemExit):
        parser.parse_args(["listen", "--work-dir", "/custom/path"])

    with pytest.raises(SystemExit):
        parser.parse_args(["send", "-c", "oc_123", "-m", "hi", "-w", "/custom/path"])


@patch("feishu_bot_cli_antigravity.cli.run_listen")
def test_cli_main_listen_with_work_dir(mock_run_listen, tmp_path, monkeypatch):
    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "sec_test")

    ret = main(["--work-dir", str(tmp_path), "listen"])
    assert ret == 0
    mock_run_listen.assert_called_once()
    assert mock_run_listen.call_args.kwargs["work_dir"] == str(tmp_path)


@patch("feishu_bot_cli_antigravity.cli.run_listen")
def test_cli_main_listen_with_nonexistent_work_dir(mock_run_listen, tmp_path, monkeypatch):
    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "sec_test")

    nonexistent = str(tmp_path / "does_not_exist")
    ret = main(["--work-dir", nonexistent, "listen"])
    assert ret == 1
    mock_run_listen.assert_not_called()


@patch("feishu_bot_cli_antigravity.cli.run_listen")
def test_cli_main_listen_loads_env_from_work_dir(mock_run_listen, tmp_path, monkeypatch):
    # 模拟外部环境变量未设置，凭据仅存在于 work_dir 下的 .env 中
    monkeypatch.delenv("LARK_APP_ID", raising=False)
    monkeypatch.delenv("LARK_APP_SECRET", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "LARK_APP_ID=from_workdir_id\nLARK_APP_SECRET=from_workdir_secret\n",
        encoding="utf-8",
    )

    ret = main(["--work-dir", str(tmp_path), "listen"])
    assert ret == 0
    mock_run_listen.assert_called_once()
    passed_config = mock_run_listen.call_args.args[1]
    assert passed_config.lark_app_id == "from_workdir_id"
    assert passed_config.lark_app_secret == "from_workdir_secret"


@patch("feishu_bot_cli_antigravity.cli.run_send")
def test_cli_main_send_loads_env_from_work_dir(mock_run_send, tmp_path, monkeypatch):
    # 模拟外部环境变量未设置，凭据仅存在于 work_dir 下的 .env 中
    monkeypatch.delenv("LARK_APP_ID", raising=False)
    monkeypatch.delenv("LARK_APP_SECRET", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "LARK_APP_ID=from_send_workdir_id\nLARK_APP_SECRET=from_send_workdir_secret\n",
        encoding="utf-8",
    )

    ret = main(["-w", str(tmp_path), "send", "-c", "oc_test_send", "-m", "hello"])
    assert ret == 0
    mock_run_send.assert_called_once()
    passed_config = mock_run_send.call_args.kwargs["config"]
    assert passed_config.lark_app_id == "from_send_workdir_id"
    assert passed_config.lark_app_secret == "from_send_workdir_secret"


@patch("feishu_bot_cli_antigravity.cli.run_send")
def test_cli_main_send_with_nonexistent_work_dir(mock_run_send, tmp_path, monkeypatch):
    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "sec_test")

    nonexistent = str(tmp_path / "does_not_exist")
    ret = main(["--work-dir", nonexistent, "send", "-c", "oc_test", "-m", "hi"])
    assert ret == 1
    mock_run_send.assert_not_called()


def test_cli_parser_version():
    parser = create_parser()

    args1 = parser.parse_args(["version"])
    assert args1.command == "version"
    assert args1.short is False

    args2 = parser.parse_args(["version", "-s"])
    assert args2.command == "version"
    assert args2.short is True

    args3 = parser.parse_args(["version", "--short"])
    assert args3.command == "version"
    assert args3.short is True


def test_cli_main_version_subcommand(capsys):
    from feishu_bot_cli_antigravity import __version__

    ret = main(["version"])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"feishu-bot-cli-antigravity {__version__}"


def test_cli_main_version_short_flags(capsys):
    from feishu_bot_cli_antigravity import __version__

    ret1 = main(["version", "-s"])
    assert ret1 == 0
    captured1 = capsys.readouterr()
    assert captured1.out.strip() == __version__

    ret2 = main(["version", "--short"])
    assert ret2 == 0
    captured2 = capsys.readouterr()
    assert captured2.out.strip() == __version__


def test_cli_main_version_without_env_credentials(monkeypatch, tmp_path, capsys):
    from feishu_bot_cli_antigravity import __version__

    # 模拟未配置任何环境变量或凭据，version 命令依然可以正常执行
    monkeypatch.delenv("LARK_APP_ID", raising=False)
    monkeypatch.delenv("LARK_APP_SECRET", raising=False)
    monkeypatch.chdir(tmp_path)

    ret = main(["version"])
    assert ret == 0
    captured = capsys.readouterr()
    assert f"feishu-bot-cli-antigravity {__version__}" in captured.out


@patch("feishu_bot_cli_antigravity.cli.run_listen")
def test_cli_main_startup_prints_version_on_listen(mock_run_listen, monkeypatch, caplog):
    from feishu_bot_cli_antigravity import __version__

    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "sec_test")

    with caplog.at_level(logging.INFO):
        ret = main(["listen"])
    assert ret == 0
    assert f"版本<{__version__}>开始运行" in caplog.text


@patch("feishu_bot_cli_antigravity.cli.run_send")
def test_cli_main_startup_prints_version_on_send(mock_run_send, monkeypatch, caplog):
    from feishu_bot_cli_antigravity import __version__

    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "sec_test")

    with caplog.at_level(logging.INFO):
        ret = main(["send", "-c", "oc_target", "-m", "test"])
    assert ret == 0
    assert f"版本<{__version__}>开始运行" in caplog.text








