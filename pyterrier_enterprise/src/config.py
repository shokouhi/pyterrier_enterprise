import os
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

@dataclass
class Settings:
    doc_dir: str = os.getenv("DOC_DIR", r"Z:\wccontainer\doc_urls")
    wiki_dir: str = os.getenv("WIKI_DIR", r"Z:\wccontainer\wiki_urls")
    index_dir: str = os.getenv("INDEX_DIR", r"Z:\wccontainer\terrier_index")
    max_bytes_per_file: int = int(os.getenv("MAX_BYTES_PER_FILE", "10485760"))  # 10MB default; 0 means no limit
    cors_allow_origins: list[str] | None = None

    def __post_init__(self):
        origins = os.getenv("CORS_ALLOW_ORIGINS", "")
        self.cors_allow_origins = [o.strip() for o in origins.split(",") if o.strip()]
        # Normalize paths
        self.doc_dir = str(Path(self.doc_dir))
        self.wiki_dir = str(Path(self.wiki_dir))
        self.index_dir = str(Path(self.index_dir))

settings = Settings()
