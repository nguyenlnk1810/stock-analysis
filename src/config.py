import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # SSI API
    SSI_CONSUMER_ID: str = os.getenv("SSI_CONSUMER_ID", "")
    SSI_CONSUMER_SECRET: str = os.getenv("SSI_CONSUMER_SECRET", "")
    SSI_PRIVATE_KEY: str = os.getenv("SSI_PRIVATE_KEY", "")
    SSI_DATA_API_URL: str = os.getenv("SSI_DATA_API_URL", "https://fc-data.ssi.com.vn")
    SSI_TRADE_API_URL: str = os.getenv("SSI_TRADE_API_URL", "https://fc-tradeapi.ssi.com.vn")
    SSI_STREAM_URL: str = os.getenv("SSI_STREAM_URL", "wss://fc-datahub.ssi.com.vn")

    # LLM
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    # Symbols mặc định
    DEFAULT_SYMBOLS: list = ["VNINDEX", "VCB", "SSI", "FPT", "HPG", "MWG", "VNM", "VIC"]


config = Config()
