import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the gateway directory (parent of this file's package)
_env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_file, override=False)  # override=False: shell env takes precedence


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    def __init__(self) -> None:
        # API auth: comma-separated keys. If empty, auth is open.
        self.api_keys = _split_csv(os.getenv("API_KEYS", ""))

        # Where uploads, job outputs and the job db live.
        self.data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
        self.upload_dir = self.data_dir / "uploads"
        self.jobs_dir = self.data_dir / "jobs"
        self.db_path = self.data_dir / "jobs.db"

        self.max_upload_bytes = int(
            os.getenv("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024))
        )

        # LLM translation backend (OpenAI-compatible gateway).
        self.translation_api_key = os.getenv("TRANSLATION_API_KEY", "")
        self.translation_model = os.getenv(
            "TRANSLATION_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507-FP8"
        )
        # base url for the OpenAI SDK (no trailing /chat/completions)
        self.translation_base_url = os.getenv(
            "TRANSLATION_BASE_URL", "http://103.1.236.109:4000/v1"
        )

        # Vision/OCR model on the same gateway, used to add a high-quality text
        # layer to scanned pages. Empty -> fall back to local Tesseract.
        self.ocr_model = os.getenv("OCR_MODEL", "deepseek-ai/DeepSeek-OCR-2")

        self.custom_system_prompt = os.getenv(
            "CUSTOM_SYSTEM_PROMPT",
            "/no_think You are a professional, authentic machine translation engine.",
        )
        self.default_lang_in = os.getenv("DEFAULT_LANG_IN", "en")
        self.default_lang_out = os.getenv("DEFAULT_LANG_OUT", "vi")
        self.qps = int(os.getenv("QPS", "4"))

        # How to launch the babeldoc runner subprocess. For local dev this uses
        # the BabelDOC checkout's venv; in Docker it is just "python".
        self.babeldoc_run_cmd = os.getenv(
            "BABELDOC_RUN_CMD",
            "uv run --directory /Users/builder2/BabelDOC python",
        ).split()

        self.cors_origins = _split_csv(os.getenv("CORS_ORIGINS", "*")) or ["*"]

        # --- RetainPDF: scanned-PDF route ---
        # Scanned PDFs translate poorly through babeldoc (it re-typesets from
        # text geometry). When a document is mostly scanned we route it to the
        # RetainPDF stack (OCR-first + Typst rendering) instead.
        self.retain_enabled = os.getenv("RETAIN_ENABLED", "1") not in {"0", "false", "False", ""}
        self.retain_base_url = os.getenv(
            "RETAIN_BASE_URL", "http://host.docker.internal:41000"
        )
        self.retain_api_key = os.getenv("RETAIN_API_KEY", "")
        self.retain_ocr_provider = os.getenv("RETAIN_OCR_PROVIDER", "paddle")
        self.retain_paddle_token = os.getenv("RETAIN_PADDLE_TOKEN", "")
        self.retain_mineru_token = os.getenv("RETAIN_MINERU_TOKEN", "")
        # Fraction of pages without a text layer above which we treat the whole
        # document as scanned and hand it to RetainPDF.
        self.scanned_route_threshold = float(os.getenv("SCANNED_ROUTE_THRESHOLD", "0.5"))

    def ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
