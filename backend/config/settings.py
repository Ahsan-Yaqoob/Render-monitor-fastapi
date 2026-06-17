import os
import sys
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    @staticmethod
    def _clean(value):
        """Strip whitespace and stray surrounding quotes (common when pasting into a dashboard)."""
        if value is None:
            return None
        return value.strip().strip('"').strip("'").strip()

    def __init__(self):
        self.RENDER_API_KEY = self._clean(os.getenv('RENDER_API_KEY'))
        # NOTE: 'RENDER_SERVICE_ID' is a RESERVED built-in var on Render — the platform
        # auto-injects it set to the *current* service's own id, which would shadow any
        # custom value. We use MONITOR_SERVICE_ID instead (the id of the service we watch),
        # falling back to RENDER_SERVICE_ID only for local dev where there's no collision.
        self.MONITOR_SERVICE_ID = self._clean(os.getenv('MONITOR_SERVICE_ID') or os.getenv('RENDER_SERVICE_ID'))
        self.AI_BACKEND_URL    = self._clean(os.getenv('AI_BACKEND_URL') or '').rstrip('/')
        self.EMAIL_SENDER = self._clean(os.getenv('EMAIL_SENDER'))
        self.EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')  # app passwords may contain spaces — don't strip
        self.EMAIL_RECEIVER = self._clean(os.getenv('EMAIL_RECEIVER'))
        self.FASTAPI_PORT = int(os.getenv('FASTAPI_PORT', 8000))
        self.FASTAPI_HOST = os.getenv('FASTAPI_HOST', '0.0.0.0')
        self.DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

        self.CHECK_INTERVAL_MINUTES = 1
        self.CSV_FILE_PATH = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'backend', 'data', 'logs.csv'
        )

        self.RENDER_API_URL = 'https://api.render.com/v1'
        self.SMTP_SERVER = 'smtp.gmail.com'
        self.SMTP_PORT = 587

        self._validate_env()

    def _validate_env(self):
        """Validate required environment variables."""
        required_vars = {
            'RENDER_API_KEY': self.RENDER_API_KEY,
            'MONITOR_SERVICE_ID': self.MONITOR_SERVICE_ID,
            'EMAIL_SENDER': self.EMAIL_SENDER,
            'EMAIL_PASSWORD': self.EMAIL_PASSWORD,
            'EMAIL_RECEIVER': self.EMAIL_RECEIVER,
        }

        missing_vars = [var for var, value in required_vars.items() if not value]

        if missing_vars:
            print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
            print("Please check your .env file and ensure all required variables are set.")
            sys.exit(1)

        print("[OK] Configuration loaded successfully")


settings = Settings()
