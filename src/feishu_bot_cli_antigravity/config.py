"""配置管理模块。"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv(override=True)


@dataclass
class Config:
    """机器人与服务配置项。"""

    lark_app_id: str = ""
    lark_app_secret: str = ""
    lark_domain: str | None = None
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量读取配置。"""
        return cls(
            lark_app_id=os.getenv("LARK_APP_ID", "").strip(),
            lark_app_secret=os.getenv("LARK_APP_SECRET", "").strip(),
            lark_domain=os.getenv("LARK_DOMAIN"),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip(),
        )

    def validate(self) -> None:
        """校验关键凭据是否已配置。"""
        if not self.lark_app_id or not self.lark_app_secret:
            raise ValueError(
                "请在环境变量或 .env 文件中配置 LARK_APP_ID 与 LARK_APP_SECRET"
            )


def get_config() -> Config:
    """获取配置实例。"""
    return Config.from_env()
