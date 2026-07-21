from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from uuid import uuid4

from gemini_tts import DEFAULT_MODEL, DEFAULT_VOICE, generate_tts


APP_TITLE = "Voice Studio AI"
_NULL_STREAMS: list[object] = []

VOICE_OPTIONS = [
    ("Zephyr", "Zephyr — sáng, tươi"),
    ("Puck", "Puck — vui, năng lượng"),
    ("Charon", "Charon — thuyết minh rõ"),
    ("Kore", "Kore — chắc, rõ, nghiêm"),
    ("Fenrir", "Fenrir — hào hứng"),
    ("Leda", "Leda — trẻ trung"),
    ("Orus", "Orus — chắc giọng"),
    ("Aoede", "Aoede — nhẹ, thoáng"),
    ("Callirrhoe", "Callirrhoe — dễ nghe"),
    ("Autonoe", "Autonoe — sáng"),
    ("Enceladus", "Enceladus — mềm, thoáng hơi"),
    ("Iapetus", "Iapetus — rõ chữ"),
    ("Umbriel", "Umbriel — tự nhiên"),
    ("Algieba", "Algieba — mượt"),
    ("Despina", "Despina — mượt"),
    ("Erinome", "Erinome — rõ"),
    ("Algenib", "Algenib — khàn, dày"),
    ("Rasalgethi", "Rasalgethi — tin tức"),
    ("Laomedeia", "Laomedeia — vui"),
    ("Achernar", "Achernar — mềm"),
    ("Alnilam", "Alnilam — vững"),
    ("Schedar", "Schedar — đều"),
    ("Gacrux", "Gacrux — trưởng thành"),
    ("Pulcherrima", "Pulcherrima — nổi bật"),
    ("Achird", "Achird — thân thiện"),
    ("Zubenelgenubi", "Zubenelgenubi — đời thường"),
    ("Vindemiatrix", "Vindemiatrix — dịu"),
    ("Sadachbia", "Sadachbia — sinh động"),
    ("Sadaltager", "Sadaltager — hiểu biết"),
    ("Sulafat", "Sulafat — ấm"),
]

STYLE_PRESETS = {
    "Tự nhiên tiếng Việt": "Đọc tiếng Việt tự nhiên, rõ chữ, truyền cảm, tốc độ vừa phải.",
    "Review phim / kể chuyện": "Giọng kể chuyện cuốn hút như review phim ngắn, hơi bí ẩn, nhấn nhá ở các chi tiết quan trọng, không quá nhanh.",
    "Tin tức nghiêm túc": "Giọng phát thanh viên tin tức, nghiêm túc, rõ ràng, nhịp ổn định, phát âm chuẩn và ít cảm xúc quá đà.",
    "TikTok năng lượng": "Giọng short-video/TikTok năng lượng cao, mở đầu bắt tai, nhịp nhanh vừa, có vocal smile, nhấn mạnh các cụm gây tò mò.",
    "YouTube documentary": "Giọng tài liệu YouTube, trầm ổn, điện ảnh, chậm vừa, tạo cảm giác đáng tin và có chiều sâu.",
    "Quảng cáo bán hàng": "Giọng quảng cáo thân thiện, tự tin, mời gọi nhưng không lố, nhấn rõ lợi ích và lời kêu gọi hành động.",
    "Podcast ấm áp": "Giọng podcast gần gũi, ấm, chậm vừa, như đang nói chuyện riêng với người nghe.",
    "Kể chuyện ma": "Giọng thấp, chậm, nhiều khoảng nghỉ, bí ẩn và căng nhẹ; có thể dùng sắc thái thì thầm ở đoạn hồi hộp.",
    "Truyền cảm hứng": "Giọng truyền cảm hứng, chắc, ấm, nhấn mạnh hy vọng và quyết tâm; nhịp tăng dần ở cuối câu.",
    "Hài hước đời thường": "Giọng đời thường, dí dỏm, thoải mái, có chút tinh nghịch nhưng vẫn rõ chữ.",
    "ASMR nhẹ": "Giọng rất nhẹ, gần micro, chậm, êm, ít lực, tạo cảm giác thư giãn.",
    "Đọc sách nói": "Giọng audiobook, giàu hình ảnh, tốc độ chậm vừa, ngắt nghỉ theo ý nghĩa câu, không kịch hóa quá mức.",
}

PACE_OPTIONS = [
    "tốc độ vừa phải",
    "chậm, nhiều khoảng nghỉ",
    "nhanh vừa, không nuốt chữ",
    "rất nhanh nhưng vẫn rõ chữ",
]

EMOTION_OPTIONS = [
    "tự nhiên",
    "vui vẻ và sáng",
    "nghiêm túc và đáng tin",
    "hồi hộp và bí ẩn",
    "ấm áp và thân thiện",
    "mạnh mẽ và truyền cảm hứng",
]


def ensure_console_streams() -> None:
    """Provide safe streams for GUI builds where PyInstaller sets them to None."""
    for stream_name in ("stdout", "stderr"):
        if getattr(sys, stream_name) is None:
            stream = open(os.devnull, "w", encoding="utf-8")
            _NULL_STREAMS.append(stream)
            setattr(sys, stream_name, stream)


def user_data_dir() -> Path:
    override = os.environ.get("VOICE_STUDIO_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return (base / "VoiceStudioAI").resolve()


def output_directory() -> Path:
    directory = user_data_dir() / "outputs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def ffmpeg_executable() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("Không tìm thấy bộ chuyển đổi MP3 đi kèm ứng dụng.") from exc


def convert_wav_to_mp3(wav_path: Path) -> Path:
    mp3_path = wav_path.with_suffix(".mp3")
    result = subprocess.run(
        [ffmpeg_executable(), "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0 or not mp3_path.exists():
        raise RuntimeError("Không thể chuyển file sang MP3.")
    return mp3_path


def open_file(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def build_style(preset: str, custom: str, pace: str, emotion: str) -> str:
    base_style = custom.strip() or STYLE_PRESETS.get(preset, STYLE_PRESETS["Tự nhiên tiếng Việt"])
    return "\n".join(
        [
            base_style,
            f"Tốc độ: {pace}.",
            f"Cảm xúc tổng thể: {emotion}.",
            "Phát âm tiếng Việt rõ, tự nhiên; không đọc phần hướng dẫn phong cách.",
        ]
    )


def smoke_test() -> int:
    ensure_console_streams()
    directory = output_directory()
    if not directory.is_dir() or not ffmpeg_executable():
        return 1
    if len(VOICE_OPTIONS) != 30 or not STYLE_PRESETS:
        return 1
    print("Voice Studio native desktop smoke test: OK")
    return 0


class NativeVoiceStudio:
    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, scrolledtext, ttk

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.scrolledtext = scrolledtext
        self.root = tk.Tk(className="VoiceStudioAI")
        self.root.title(APP_TITLE)
        self.root.geometry("820x780")
        self.root.minsize(760, 700)

        self.wav_path: Path | None = None
        self.mp3_path: Path | None = None
        self.generating = False
        self.voice_by_label = {label: value for value, label in VOICE_OPTIONS}

        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Primary.TButton", font=("Arial", 11, "bold"), padding=8)
        style.configure("Title.TLabel", font=("Arial", 22, "bold"))

        outer = ttk.Frame(self.root, padding=18, name="mainPanel")
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=APP_TITLE, style="Title.TLabel", name="titleLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Tạo giọng đọc MP3/WAV trực tiếp trên máy — không mở trình duyệt",
            name="subtitleLabel",
        ).pack(anchor="w", pady=(2, 14))

        ttk.Label(outer, text="API key của bạn").pack(anchor="w")
        self.api_key = ttk.Entry(outer, show="•", name="apiKeyInput")
        self.api_key.pack(fill="x", pady=(4, 4))
        ttk.Label(outer, text="Key chỉ dùng cho lần tạo hiện tại và không được lưu.").pack(anchor="w", pady=(0, 10))

        ttk.Label(outer, text="Nội dung cần đọc").pack(anchor="w")
        self.text_input = scrolledtext.ScrolledText(outer, height=9, wrap="word", name="textInput")
        self.text_input.pack(fill="both", expand=True, pady=(4, 10))

        selectors = ttk.Frame(outer)
        selectors.pack(fill="x")
        selectors.columnconfigure(0, weight=1)
        selectors.columnconfigure(1, weight=1)

        voice_frame = ttk.Frame(selectors)
        voice_frame.grid(row=0, column=0, sticky="ew", padx=(0, 7))
        ttk.Label(voice_frame, text="Giọng đọc").pack(anchor="w")
        self.voice = ttk.Combobox(voice_frame, state="readonly", values=list(self.voice_by_label), name="voiceSelect")
        self.voice.pack(fill="x", pady=(4, 8))
        default_label = next(label for value, label in VOICE_OPTIONS if value == DEFAULT_VOICE)
        self.voice.set(default_label)

        preset_frame = ttk.Frame(selectors)
        preset_frame.grid(row=0, column=1, sticky="ew", padx=(7, 0))
        ttk.Label(preset_frame, text="Phong cách").pack(anchor="w")
        self.preset = ttk.Combobox(preset_frame, state="readonly", values=list(STYLE_PRESETS), name="styleSelect")
        self.preset.pack(fill="x", pady=(4, 8))
        self.preset.set("Tự nhiên tiếng Việt")
        self.preset.bind("<<ComboboxSelected>>", self.apply_preset)

        ttk.Label(outer, text="Mô tả phong cách tùy chỉnh").pack(anchor="w")
        self.custom_style = scrolledtext.ScrolledText(outer, height=4, wrap="word", name="customStyleInput")
        self.custom_style.pack(fill="x", pady=(4, 10))
        self.custom_style.insert("1.0", STYLE_PRESETS["Tự nhiên tiếng Việt"])

        details = ttk.Frame(outer)
        details.pack(fill="x")
        details.columnconfigure(0, weight=1)
        details.columnconfigure(1, weight=1)
        pace_frame = ttk.Frame(details)
        pace_frame.grid(row=0, column=0, sticky="ew", padx=(0, 7))
        ttk.Label(pace_frame, text="Tốc độ").pack(anchor="w")
        self.pace = ttk.Combobox(pace_frame, state="readonly", values=PACE_OPTIONS, name="paceSelect")
        self.pace.pack(fill="x", pady=(4, 10))
        self.pace.set(PACE_OPTIONS[0])
        emotion_frame = ttk.Frame(details)
        emotion_frame.grid(row=0, column=1, sticky="ew", padx=(7, 0))
        ttk.Label(emotion_frame, text="Cảm xúc").pack(anchor="w")
        self.emotion = ttk.Combobox(emotion_frame, state="readonly", values=EMOTION_OPTIONS, name="emotionSelect")
        self.emotion.pack(fill="x", pady=(4, 10))
        self.emotion.set(EMOTION_OPTIONS[0])

        self.generate_button = ttk.Button(
            outer,
            text="Tạo giọng đọc",
            style="Primary.TButton",
            command=self.start_generation,
            name="generateButton",
        )
        self.generate_button.pack(fill="x", pady=(2, 8))

        actions = ttk.Frame(outer)
        actions.pack(fill="x")
        for column in range(3):
            actions.columnconfigure(column, weight=1)
        self.play_button = ttk.Button(actions, text="Nghe thử", command=self.play_audio, state="disabled", name="playButton")
        self.play_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.save_mp3_button = ttk.Button(actions, text="Lưu MP3", command=self.save_mp3, state="disabled", name="saveMp3Button")
        self.save_mp3_button.grid(row=0, column=1, sticky="ew", padx=5)
        self.save_wav_button = ttk.Button(actions, text="Lưu WAV", command=self.save_wav, state="disabled", name="saveWavButton")
        self.save_wav_button.grid(row=0, column=2, sticky="ew", padx=(5, 0))

        self.progress = ttk.Progressbar(outer, mode="indeterminate", name="generationProgress")
        self.progress.pack(fill="x", pady=(12, 5))
        self.status = tk.StringVar(value="Sẵn sàng")
        ttk.Label(outer, textvariable=self.status, name="statusLabel").pack(anchor="w")

    def apply_preset(self, _event=None) -> None:
        self.custom_style.delete("1.0", "end")
        self.custom_style.insert("1.0", STYLE_PRESETS[self.preset.get()])

    def start_generation(self) -> None:
        api_key = self.api_key.get().strip()
        text = self.text_input.get("1.0", "end").strip()
        if not 20 <= len(api_key) <= 512:
            self.messagebox.showwarning(APP_TITLE, "Hãy nhập API key hợp lệ.")
            return
        if not text:
            self.messagebox.showwarning(APP_TITLE, "Hãy nhập nội dung cần đọc.")
            return
        if len(text) > 20_000:
            self.messagebox.showwarning(APP_TITLE, "Nội dung không được vượt quá 20.000 ký tự.")
            return

        voice = self.voice_by_label[self.voice.get()]
        style = build_style(
            self.preset.get(),
            self.custom_style.get("1.0", "end"),
            self.pace.get(),
            self.emotion.get(),
        )
        self.generating = True
        self.generate_button.configure(state="disabled")
        self.play_button.configure(state="disabled")
        self.save_mp3_button.configure(state="disabled")
        self.save_wav_button.configure(state="disabled")
        self.progress.start(12)
        self.status.set("Đang tạo giọng đọc...")
        thread = threading.Thread(
            target=self.generate_worker,
            args=(api_key, text, voice, style),
            daemon=True,
        )
        thread.start()

    def generate_worker(self, api_key: str, text: str, voice: str, style: str) -> None:
        try:
            wav_path = output_directory() / f"voice_studio_{uuid4().hex}.wav"
            output = Path(
                generate_tts(
                    text=text,
                    output_path=wav_path,
                    api_key=api_key,
                    voice=voice,
                    model=DEFAULT_MODEL,
                    style=style,
                )
            )
            mp3_path = convert_wav_to_mp3(output)
            self.root.after(0, lambda: self.generation_finished(output, mp3_path))
        except Exception as exc:
            message = str(exc).replace(api_key, "[API KEY]")[:1200]
            self.root.after(0, lambda: self.generation_failed(message))

    def generation_finished(self, wav_path: Path, mp3_path: Path) -> None:
        self.wav_path = wav_path
        self.mp3_path = mp3_path
        self.generating = False
        self.progress.stop()
        self.generate_button.configure(state="normal")
        self.play_button.configure(state="normal")
        self.save_mp3_button.configure(state="normal")
        self.save_wav_button.configure(state="normal")
        self.status.set("Đã tạo xong MP3 và WAV")
        self.messagebox.showinfo(APP_TITLE, "Đã tạo giọng đọc thành công.")

    def generation_failed(self, message: str) -> None:
        self.generating = False
        self.progress.stop()
        self.generate_button.configure(state="normal")
        self.status.set("Tạo giọng đọc thất bại")
        self.messagebox.showerror(APP_TITLE, message)

    def play_audio(self) -> None:
        if self.mp3_path:
            open_file(self.mp3_path)

    def save_file(self, source: Path | None, extension: str, file_types: list[tuple[str, str]]) -> None:
        if not source:
            return
        destination = self.filedialog.asksaveasfilename(
            title=f"Lưu file {extension.upper()}",
            defaultextension=extension,
            filetypes=file_types,
            initialfile=source.name,
        )
        if destination:
            shutil.copy2(source, destination)
            self.status.set(f"Đã lưu: {destination}")

    def save_mp3(self) -> None:
        self.save_file(self.mp3_path, ".mp3", [("MP3 audio", "*.mp3")])

    def save_wav(self) -> None:
        self.save_file(self.wav_path, ".wav", [("WAV audio", "*.wav")])

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    ensure_console_streams()
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--smoke-test", action="store_true", help="Kiểm tra thành phần ứng dụng rồi thoát")
    args = parser.parse_args()
    if args.smoke_test:
        return smoke_test()
    NativeVoiceStudio().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
