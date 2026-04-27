import os
from dotenv import load_dotenv

load_dotenv()


OPENAI_ENDPOINT = os.getenv("AOAI_ENDPOINT", "")
OPENAI_API_KEY = os.getenv("AOAI_API_KEY", "")
OPENAI_MODEL = os.getenv("AOAI_DEPLOY_GPT4O_MINI", "gpt-4.1-mini")
OPENAI_API_VERSION = os.getenv("AOAI_API_VERSION", "2024-02-15-preview")
APP_ENV = os.getenv("APP_ENV", "local")

