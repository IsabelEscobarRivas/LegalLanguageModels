from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    AWS_ACCESS_KEY: str
    AWS_SECRET_ACCESS_KEY: str
    S3_BUCKET_NAME: str
    OPENAI_API_KEY: Optional[str] = None  # Add this line
    class Config:
        env_file = ".env"

settings = Settings()