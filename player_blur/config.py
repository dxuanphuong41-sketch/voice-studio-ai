from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


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
