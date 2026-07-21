from dataclasses import dataclass
import os
from pathlib import Path


ROOT = Path(
    os.environ.get("VOICE_STUDIO_DATA_DIR", Path(__file__).resolve().parent.parent)
).expanduser().resolve()


@dataclass(frozen=True)
class Settings:
    downloads_dir: Path = ROOT / "data" / "downloads"
    outputs_dir: Path = ROOT / "data" / "outputs"
    temp_dir: Path = ROOT / "data" / "temp"
    model_name: str = "yolov8n-seg.pt"
    max_duration_seconds: int = 15 * 60
    search_limit: int = 8
    detection_confidence: float = 0.35

    def ensure_directories(self) -> None:
        for directory in (self.downloads_dir, self.outputs_dir, self.temp_dir):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
