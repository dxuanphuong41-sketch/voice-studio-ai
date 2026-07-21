import argparse
import base64
import os
import sys
import wave
from typing import Any
from pathlib import Path


DEFAULT_MODEL = "gemini-3.1-flash-tts-preview"
DEFAULT_VOICE = "Kore"
DEFAULT_RATE = 24000


def write_wave(path: Path, pcm: bytes, channels: int = 1, rate: int = DEFAULT_RATE, sample_width: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(rate)
        wav_file.writeframes(pcm)


def read_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Bạn cần truyền --text, --input-file, hoặc pipe nội dung vào stdin.")


def build_prompt(text: str, style: str | None) -> str:
    text = text.strip()
    if not text:
        raise SystemExit("Nội dung TTS đang trống.")
    if style:
        return (
            "Synthesize speech from the transcript below. "
            "Use the director notes only as performance guidance; do not read the notes aloud.\n\n"
            "### DIRECTOR NOTES\n"
            f"{style.strip()}\n\n"
            "### TRANSCRIPT\n"
            f"{text}"
        )
    return (
        "Synthesize speech from the transcript below. Do not add extra words.\n\n"
        "### TRANSCRIPT\n"
        f"{text}"
    )


def extract_audio_data(interaction: Any) -> bytes:
    output_audio = getattr(interaction, "output_audio", None)
    data = getattr(output_audio, "data", None)
    if data:
        return base64.b64decode(data) if isinstance(data, str) else bytes(data)

    for output in getattr(interaction, "outputs", []) or []:
        audio = getattr(output, "audio", None) or getattr(output, "output_audio", None)
        data = getattr(audio, "data", None)
        if data:
            return base64.b64decode(data) if isinstance(data, str) else bytes(data)

    text = getattr(interaction, "output_text", None)
    if text:
        raise RuntimeError(f"Gemini trả về text thay vì audio: {text[:500]}")

    raise RuntimeError("Gemini không trả về audio. Hãy thử đổi voice/model hoặc rút ngắn nội dung.")


def generate_tts(
    text: str,
    output_path: str | Path,
    api_key: str | None = None,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    style: str | None = None,
) -> Path:
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu thư viện google-genai. Chạy: pip install -r requirements.txt"
        ) from exc

    api_key = (api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "Thiếu Gemini API key. Hãy dán key vào ô trên web hoặc set biến GEMINI_API_KEY."
        )

    prompt = build_prompt(text, style)
    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=model,
        input=prompt,
        response_format={"type": "audio"},
        generation_config={
            "speech_config": [
                {"voice": voice},
            ],
        },
    )

    output_path = Path(output_path)
    write_wave(output_path, extract_audio_data(interaction))
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo giọng đọc bằng Gemini Flash 3.1 TTS.")
    parser.add_argument("--text", help="Nội dung cần đọc.")
    parser.add_argument("--input-file", help="File .txt chứa nội dung cần đọc.")
    parser.add_argument("--out", default="output/gemini_tts.wav", help="File WAV đầu ra.")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help=f"Tên voice Gemini TTS. Mặc định: {DEFAULT_VOICE}.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model TTS. Mặc định: {DEFAULT_MODEL}.")
    parser.add_argument("--style", help='Chỉ dẫn phong cách đọc, ví dụ: "Đọc bằng giọng nam miền Nam, chậm, rõ, truyền cảm".')
    args = parser.parse_args()

    try:
        output = generate_tts(
            text=read_text(args),
            output_path=args.out,
            voice=args.voice,
            model=args.model,
            style=args.style,
        )
    except Exception as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Đã tạo file giọng đọc: {output}")


if __name__ == "__main__":
    main()
