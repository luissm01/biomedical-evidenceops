from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GenerationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EVIDENCEOPS_",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    llm_provider: Literal["gemini", "deepseek"] = "gemini"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = Field(default="gemini-3.6-flash", min_length=1)
    gemini_max_output_tokens: int = Field(default=2048, gt=0)
    gemini_timeout_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)

    deepseek_api_key: SecretStr | None = None
    deepseek_model: str = Field(default="deepseek-flash", min_length=1)
    deepseek_max_output_tokens: int = Field(default=2048, gt=0)
    deepseek_timeout_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)

    @property
    def selected_model(self) -> str:
        return self.gemini_model if self.llm_provider == "gemini" else self.deepseek_model

    @property
    def selected_max_output_tokens(self) -> int:
        return (self.gemini_max_output_tokens if self.llm_provider == "gemini"
                else self.deepseek_max_output_tokens)

    @property
    def selected_timeout_seconds(self) -> float:
        return (self.gemini_timeout_seconds if self.llm_provider == "gemini"
                else self.deepseek_timeout_seconds)

    @field_validator("gemini_model", "deepseek_model", mode="before")
    @classmethod
    def strip_model(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("gemini_api_key", "deepseek_api_key")
    @classmethod
    def normalize_empty_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        return value


class Settings(GenerationSettings):
    database_url: PostgresDsn
    trace_console: bool = False

    @field_validator("database_url")
    @classmethod
    def require_psycopg_driver(cls, database_url: PostgresDsn) -> PostgresDsn:
        if database_url.scheme != "postgresql+psycopg":
            raise ValueError("database URL must use the postgresql+psycopg scheme")
        return database_url
