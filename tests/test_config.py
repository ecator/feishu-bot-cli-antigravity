import pytest

from feishu_bot_cli_antigravity.config import Config


def test_config_defaults():
    config = Config()
    assert config.lark_app_id == ""
    assert config.lark_app_secret == ""
    assert config.log_level == "INFO"
    with pytest.raises(ValueError, match="请在环境变量或 .env 文件中配置"):
        config.validate()


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("LARK_APP_ID", "cli_test_id")
    monkeypatch.setenv("LARK_APP_SECRET", "test_secret")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LARK_DOMAIN", "https://open.feishu.cn")

    config = Config.from_env()
    assert config.lark_app_id == "cli_test_id"
    assert config.lark_app_secret == "test_secret"
    assert config.log_level == "DEBUG"
    assert config.lark_domain == "https://open.feishu.cn"
    # validate should pass without exception
    config.validate()


def test_load_env_file_explicit_path(tmp_path, monkeypatch):
    from feishu_bot_cli_antigravity.config import Config, load_env_file

    env_file = tmp_path / ".env"
    env_file.write_text("LARK_APP_ID=custom_id_999\nLARK_APP_SECRET=custom_sec_888\n", encoding="utf-8")

    monkeypatch.delenv("LARK_APP_ID", raising=False)
    monkeypatch.delenv("LARK_APP_SECRET", raising=False)

    assert load_env_file(env_file) is True
    config = Config.from_env()
    assert config.lark_app_id == "custom_id_999"
    assert config.lark_app_secret == "custom_sec_888"


def test_load_env_file_from_cwd(tmp_path, monkeypatch):
    from feishu_bot_cli_antigravity.config import Config, load_env_file

    env_file = tmp_path / ".env"
    env_file.write_text("LARK_APP_ID=cwd_id_111\nLARK_APP_SECRET=cwd_sec_222\n", encoding="utf-8")

    monkeypatch.delenv("LARK_APP_ID", raising=False)
    monkeypatch.delenv("LARK_APP_SECRET", raising=False)
    monkeypatch.chdir(tmp_path)

    # 未指定路径时，基于当前工作目录查找并加载
    assert load_env_file() is True
    config = Config.from_env()
    assert config.lark_app_id == "cwd_id_111"
    assert config.lark_app_secret == "cwd_sec_222"

