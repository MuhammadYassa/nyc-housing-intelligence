from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ogrinfo_executable: str = "ogrinfo"
    ogr2ogr_executable: str = "ogr2ogr"

    database_host: str = "localhost"

    database_port: int = Field(validation_alias="POSTGRES_HOST_PORT", default=5433)

    database_name: str = Field(
        validation_alias="POSTGRES_DB", default="housing_intelligence"
    )

    database_user: str = Field(validation_alias="POSTGRES_USER", default="housing_app")

    database_password: SecretStr = Field(validation_alias="POSTGRES_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # type: ignore
