from typing import TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class SKBaseModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra="allow",
    )


T = TypeVar("T", bound="BaseSettings")


class SKBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)
