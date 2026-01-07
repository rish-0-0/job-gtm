import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://jobgtm:jobgtm_password@localhost:5432/jobgtm"
)

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8001"))

# Temporal configuration
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "job-gtm-queue")

# Text-to-SQL LLM Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Text-to-SQL Settings
NL_QUERY_CACHE_TTL = int(os.getenv("NL_QUERY_CACHE_TTL", "3600"))  # 1 hour
NL_QUERY_SIMILARITY_THRESHOLD = float(os.getenv("NL_QUERY_SIMILARITY_THRESHOLD", "0.85"))
