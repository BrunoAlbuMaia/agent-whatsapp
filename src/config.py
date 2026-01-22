# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = 'Agent'
    API_V1_STR: str = '/api/v1'
    DATABASE_URL: str = 'postgresql+asyncpg://user:password@localhost:5432/nome_banco'
    OPENAI_API_KEY: str = 'apikeydochat'
    OPENAI_MODEL:str = 'gpt-5-nano'
    BASE_URL_EVOLUTION:str = ''
    REDIS_URL:str = ''
    API_KEY_EVOLUITON:str = ''
    WEBHOOK_SECRET: str = 'coloquequaldesejar'

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()