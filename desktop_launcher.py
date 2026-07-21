from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser


APP_TITLE = "Voice Studio AI"


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


def prepare_environment() -> Path:
    data_dir = user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["VOICE_STUDIO_DATA_DIR"] = str(data_dir)
    return data_dir


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def create_server(port: int):
    prepare_environment()
    import uvicorn
    from tts_web import app

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    return uvicorn.Server(config)


def health_is_ready(port: int, timeout: float = 0.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def smoke_test() -> int:
    port = find_free_port()
    server = create_server(port)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if health_is_ready(port):
            server.should_exit = True
            thread.join(timeout=5)
            print("Voice Studio desktop smoke test: OK")
            return 0
        if not thread.is_alive():
            break
        time.sleep(0.2)
    server.should_exit = True
    thread.join(timeout=3)
    print("Voice Studio desktop smoke test: FAILED", file=sys.stderr)
    return 1


class DesktopController:
    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import messagebox

        self.tk = tk
        self.messagebox = messagebox
        self.root = tk.Tk(className="VoiceStudioAI")
        self.root.title(APP_TITLE)
        self.root.geometry("440x245")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.stop)

        self.port = find_free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.server = create_server(self.port)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.opened_once = False
        self.closing = False

        frame = tk.Frame(self.root, padx=24, pady=22, name="mainPanel")
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=APP_TITLE, font=("Arial", 20, "bold"), name="titleLabel").pack()
        tk.Label(
            frame,
            text="Tạo giọng đọc MP3/WAV trên Windows và macOS",
            font=("Arial", 10),
            name="subtitleLabel",
        ).pack(pady=(5, 14))
        self.status = tk.StringVar(value="Đang khởi động...")
        tk.Label(frame, textvariable=self.status, fg="#2563eb", name="statusLabel").pack(pady=(0, 12))
        self.open_button = tk.Button(
            frame,
            text="Mở Voice Studio",
            width=24,
            state="disabled",
            command=self.open_browser,
            name="openVoiceStudioButton",
        )
        self.open_button.pack(pady=4)
        tk.Button(
            frame,
            text="Dừng và thoát",
            width=24,
            command=self.stop,
            name="stopVoiceStudioButton",
        ).pack(pady=4)
        tk.Label(
            frame,
            text="Đóng cửa sổ này để tắt ứng dụng.",
            fg="#64748b",
            name="closeHintLabel",
        ).pack(pady=(12, 0))

    def start(self) -> None:
        self.thread.start()
        self.root.after(150, self.poll_server)
        self.root.mainloop()

    def poll_server(self) -> None:
        if self.closing:
            return
        if health_is_ready(self.port):
            self.status.set("Sẵn sàng")
            self.open_button.configure(state="normal")
            if not self.opened_once:
                self.open_browser()
            return
        if not self.thread.is_alive():
            self.status.set("Không thể khởi động")
            self.messagebox.showerror(APP_TITLE, "Ứng dụng không thể khởi động. Vui lòng mở lại.")
            return
        self.root.after(250, self.poll_server)

    def open_browser(self) -> None:
        self.opened_once = True
        webbrowser.open(self.url, new=2)

    def stop(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.status.set("Đang dừng...")
        self.open_button.configure(state="disabled")
        self.server.should_exit = True
        self.root.after(100, self.finish_stop)

    def finish_stop(self) -> None:
        if self.thread.is_alive():
            self.root.after(100, self.finish_stop)
            return
        self.root.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--smoke-test", action="store_true", help="Kiểm tra máy chủ rồi thoát")
    args = parser.parse_args()
    if args.smoke_test:
        return smoke_test()
    DesktopController().start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
