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
