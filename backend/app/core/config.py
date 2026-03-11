from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    MINERU_MODEL: str = "hybrid"
    
    # LLM Settings
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    
    # Desktop OAuth Persistence
    GOOGLE_CLIENT_SECRET_PATH: str = "client_secret.json"
    GOOGLE_TOKEN_PATH: str = "token.json"

    MOONSHOT_API_KEY: str = ""
    DASHSCOPE_API_KEY: str = ""
    
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    KIMI_MODEL: str = "moonshot-v1-8k"
    QWEN_MODEL: str = "qwen-turbo"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
