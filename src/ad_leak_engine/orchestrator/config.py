from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    seed: int = 2399
    db_url: str = "sqlite:///data/db/adleak.db"
    cache_dir: str = "data/cache"
    output_dir: str = "output"
    class Config:
        env_file = ".env"
