from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    MINERU_MODEL: str = "hybrid"
    MINERU_REPO_PATH: str = r"D:\github\MinerU"
    MINERU_DEVICE_MODE: str = ""
    MINERU_API_HOST: str = "127.0.0.1"
    MINERU_API_PORT: int = 18000
    MINERU_API_TIMEOUT_SECONDS: int = 1800
    MINERU_API_BACKEND: str = "pipeline"
    MINERU_API_PARSE_METHOD: str = "auto"
    MINERU_API_AUTO_START: bool = True
    MINERU_PARSE_LANG: str = "ch"
    MINERU_PROCESSING_WINDOW_SIZE: int = 64
    MINERU_FORMULA_ENABLE: bool = True
    MINERU_TABLE_ENABLE: bool = True
    MINERU_DRAW_LAYOUT_BBOX: bool = False
    MINERU_DRAW_SPAN_BBOX: bool = False
    MINERU_DUMP_MD: bool = False
    MINERU_DUMP_CONTENT_LIST: bool = False
    MINERU_DUMP_MODEL_OUTPUT: bool = False
    MINERU_DUMP_ORIG_PDF: bool = False
    
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
