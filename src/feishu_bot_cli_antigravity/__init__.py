"""feishu-bot-cli-antigravity package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("feishu-bot-cli-antigravity")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"

from feishu_bot_cli_antigravity.agent import AgentSessionManager
from feishu_bot_cli_antigravity.channel import FeishuBotChannel
from feishu_bot_cli_antigravity.config import Config, get_config
from feishu_bot_cli_antigravity.utils import create_media_from_bytes, setup_logging

__all__ = [
    "AgentSessionManager",
    "Config",
    "FeishuBotChannel",
    "__version__",
    "create_media_from_bytes",
    "get_config",
    "setup_logging",
]

