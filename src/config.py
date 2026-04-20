from typing import Literal

from pydantic import Field, SecretStr, AmqpDsn
from pydantic_settings import BaseSettings, JsonConfigSettingsSource, SettingsConfigDict, PydanticBaseSettingsSource


class Role(BaseSettings):
    emote: str
    type: Literal["channel", "mention"]
    description: str
    name: str

class ResolvedRole(Role):
    role_id: int

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", json_file="settings.json")

    discord_token: SecretStr = Field(alias="TOKEN")
    rabbitmq_dsn: AmqpDsn = Field(alias="RABBIT")
    telegram_token: SecretStr = Field(alias="TELEGRAM_TOKEN")

    telegram_channel: str
    discord_guild_name: str
    discord_channel_name: str
    discord_debug_channel_name: str
    discord_welcome_channel_name: str
    discord_news_channel_name: str
    discord_role_names: list[str]

    roles: list[Role]


    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return JsonConfigSettingsSource(settings_cls), dotenv_settings

settings = Settings()