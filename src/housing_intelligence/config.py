"""Shared pipeline settings loaded from environment variables and the local .env."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Database connection settings and GDAL command locations for the pipeline."""

    ogrinfo_executable: str = "ogrinfo"
    ogr2ogr_executable: str = "ogr2ogr"
    gdal_proj_data: str | None = None

    database_host: str = Field(validation_alias="POSTGRES_HOST", default="localhost")

    database_port: int = Field(
        validation_alias="POSTGRES_HOST_PORT", default=5433, ge=1, le=65535
    )

    database_name: str = Field(
        validation_alias="POSTGRES_DB", default="housing_intelligence"
    )

    database_user: str = Field(validation_alias="POSTGRES_USER", default="housing_app")

    database_password: SecretStr = Field(validation_alias="POSTGRES_PASSWORD")

    gdal_inspect_timeout_seconds: int = Field(default=120, gt=0)
    gdal_load_timeout_seconds: int = Field(default=3600, gt=0)
    database_statement_timeout_seconds: int = Field(default=1800, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


# Construct Settings at an entry point.
# every database client derives its connection from these same components.
