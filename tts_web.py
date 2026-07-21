from __future__ import annotations

from datetime import datetime
from html import escape
import json
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from gemini_tts import DEFAULT_MODEL, DEFAULT_VOICE, generate_tts
from player_blur.config import ROOT, settings


app = FastAPI(title="Gemini TTS Tool")
settings.ensure_directories()
CONFIG_DIR = ROOT / "data" / "config"
KEY_FILE = CONFIG_DIR / "gemini_api_key.txt"
KEY_STORE_FILE = CONFIG_DIR / "gemini_keys.json"
HISTORY_FILE = CONFIG_DIR / "tts_history.json"
MAX_TEXT_LENGTH = 20_000
MAX_STYLE_LENGTH = 2_000


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response

VOICE_OPTIONS = [
    ("Zephyr", "An Nhiên — sáng và tươi"),
    ("Puck", "Minh Khôi — vui và năng lượng"),
    ("Charon", "Đức Minh — thuyết minh rõ ràng"),
    ("Kore", "Khánh An — chắc, rõ và nghiêm"),
    ("Fenrir", "Nhật Minh — hào hứng"),
    ("Leda", "Bảo Ngọc — trẻ trung"),
    ("Orus", "Hoàng Nam — chắc giọng"),
    ("Aoede", "Thanh Mai — nhẹ và thoáng"),
    ("Callirrhoe", "Thu Hà — tự nhiên, dễ nghe"),
    ("Autonoe", "Minh Anh — trong sáng"),
    ("Enceladus", "Ngọc Lan — mềm và thoáng hơi"),
    ("Iapetus", "Quang Minh — rõ chữ"),
    ("Umbriel", "Gia Hân — gần gũi, tự nhiên"),
    ("Algieba", "Hải Đăng — mượt mà"),
    ("Despina", "Thảo Vy — mềm mượt"),
    ("Erinome", "Anh Thư — phát âm rõ"),
    ("Algenib", "Quốc Bảo — khàn và dày"),
    ("Rasalgethi", "Tuấn Kiệt — bản tin chuyên nghiệp"),
    ("Laomedeia", "Yến Nhi — vui tươi"),
    ("Achernar", "Phương Anh — mềm mại"),
    ("Alnilam", "Thành Đạt — vững vàng"),
    ("Schedar", "Mai Chi — đều và ổn định"),
    ("Gacrux", "Trọng Nghĩa — trưởng thành"),
    ("Pulcherrima", "Kim Oanh — nổi bật"),
    ("Achird", "Minh Châu — thân thiện"),
    ("Zubenelgenubi", "Gia Bảo — đời thường"),
    ("Vindemiatrix", "Bích Ngọc — dịu dàng"),
    ("Sadachbia", "Khánh Linh — sinh động"),
    ("Sadaltager", "Đức Anh — hiểu biết"),
    ("Sulafat", "Hoài An — ấm áp"),
]

STYLE_PRESETS = {
    "Tự nhiên tiếng Việt": "Đọc tiếng Việt tự nhiên, rõ chữ, truyền cảm, tốc độ vừa phải.",
    "Review phim / kể chuyện": "Giọng kể chuyện cuốn hút như review phim ngắn, hơi bí ẩn, nhấn nhá ở các chi tiết quan trọng, không quá nhanh.",
    "Tin tức nghiêm túc": "Giọng phát thanh viên tin tức, nghiêm túc, rõ ràng, nhịp ổn định, phát âm chuẩn và ít cảm xúc quá đà.",
    "TikTok năng lượng": "Giọng short-video/TikTok năng lượng cao, mở đầu bắt tai, nhịp nhanh vừa, có vocal smile, nhấn mạnh các cụm gây tò mò.",
    "YouTube documentary": "Giọng tài liệu YouTube, trầm ổn, điện ảnh, chậm vừa, tạo cảm giác đáng tin và có chiều sâu.",
    "Quảng cáo bán hàng": "Giọng quảng cáo thân thiện, tự tin, mời gọi nhưng không lố, nhấn rõ lợi ích và lời kêu gọi hành động.",
    "Podcast ấm áp": "Giọng podcast gần gũi, ấm, chậm vừa, như đang nói chuyện riêng với người nghe.",
    "Kể chuyện ma": "Giọng thấp, chậm, nhiều khoảng nghỉ, bí ẩn và căng nhẹ; có thể dùng sắc thái [whispers] ở đoạn hồi hộp.",
    "Truyền cảm hứng": "Giọng truyền cảm hứng, chắc, ấm, nhấn mạnh hy vọng và quyết tâm; cadence tăng dần ở cuối câu.",
    "Hài hước đời thường": "Giọng đời thường, dí dỏm, thoải mái, có chút tinh nghịch nhưng vẫn rõ chữ.",
    "ASMR nhẹ": "Giọng rất nhẹ, gần micro, chậm, êm, ít lực, tạo cảm giác thư giãn.",
    "Đọc sách nói": "Giọng audiobook, giàu hình ảnh, tốc độ chậm vừa, ngắt nghỉ theo ý nghĩa câu, không kịch hóa quá mức.",
    "Tùy chỉnh": "",
}


def render_options(options: list[tuple[str, str]], selected: str) -> str:
    parts = []
    for value, label in options:
        attr = " selected" if value == selected else ""
        parts.append(f'<option value="{value}"{attr}>{label}</option>')
    return "\n".join(parts)


def render_style_options() -> str:
    return "\n".join(f'<option value="{name}">{name}</option>' for name in STYLE_PRESETS)


def has_saved_key() -> bool:
    return bool(load_active_key())


def load_saved_key() -> str:
    active = load_active_key()
    if active:
        return active
    if not KEY_FILE.exists():
        return ""
    return KEY_FILE.read_text(encoding="utf-8").strip()


def save_key(api_key: str) -> None:
    api_key = api_key.strip()
    if not api_key:
        return
    add_managed_key("Key đã lưu", api_key, make_active=True)


def mask_key(api_key: str) -> str:
    api_key = (api_key or "").strip()
    if len(api_key) <= 12:
        return "••••"
    return f"{api_key[:6]}…{api_key[-4:]}"


def load_key_store() -> dict:
    if not KEY_STORE_FILE.exists():
        return {"active_id": "", "keys": []}
    try:
        data = json.loads(KEY_STORE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"active_id": "", "keys": []}
    if not isinstance(data, dict):
        return {"active_id": "", "keys": []}
    data.setdefault("active_id", "")
    data.setdefault("keys", [])
    return data


def save_key_store(store: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    KEY_STORE_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_project(project: str) -> str:
    return (project or "Default").strip() or "Default"


def add_managed_key(label: str, api_key: str, project: str = "Default", make_active: bool = True) -> str:
    api_key = api_key.strip()
    label = (label or "Gemini key").strip()
    project = normalize_project(project)
    if not api_key:
        raise RuntimeError("API key đang trống.")
    store = load_key_store()
    existing = next((item for item in store["keys"] if item.get("key") == api_key), None)
    if existing:
        existing["label"] = label
        existing["project"] = project
        key_id = existing["id"]
    else:
        key_id = datetime.now().strftime("key_%Y%m%d_%H%M%S_%f")
        store["keys"].append(
            {
                "id": key_id,
                "label": label,
                "project": project,
                "key": api_key,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    if make_active or not store.get("active_id"):
        store["active_id"] = key_id
    save_key_store(store)
    return key_id


def get_managed_key(key_id: str) -> dict | None:
    for item in load_key_store().get("keys", []):
        if item.get("id") == key_id:
            return item
    return None


def load_active_key_item() -> dict | None:
    store = load_key_store()
    active_id = store.get("active_id")
    if active_id:
        item = get_managed_key(active_id)
        if item:
            return item
    if store.get("keys"):
        return store["keys"][0]
    if KEY_FILE.exists():
        legacy_key = KEY_FILE.read_text(encoding="utf-8").strip()
        if legacy_key:
            add_managed_key("Key cũ đã lưu", legacy_key, make_active=True)
            return load_active_key_item()
    return None


def list_projects() -> list[str]:
    projects = {normalize_project(item.get("project", "Default")) for item in load_key_store().get("keys", [])}
    if not projects:
        projects.add("Default")
    return sorted(projects)


def load_active_key() -> str:
    item = load_active_key_item()
    return item.get("key", "") if item else ""


def set_active_key(key_id: str) -> None:
    store = load_key_store()
    if not any(item.get("id") == key_id for item in store.get("keys", [])):
        raise RuntimeError("Không tìm thấy key.")
    store["active_id"] = key_id
    save_key_store(store)


def delete_managed_key(key_id: str) -> None:
    store = load_key_store()
    store["keys"] = [item for item in store.get("keys", []) if item.get("id") != key_id]
    if store.get("active_id") == key_id:
        store["active_id"] = store["keys"][0]["id"] if store["keys"] else ""
    save_key_store(store)


def test_gemini_key(api_key: str) -> str:
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        models = client.models.list()
        first_names = []
        for index, model in enumerate(models):
            if index >= 3:
                break
            first_names.append(getattr(model, "name", "model"))
        details = ", ".join(first_names) if first_names else "không đọc được danh sách model"
        return f"OK — key gọi Gemini được ({details})."
    except Exception as exc:
        return f"LỖI — {exc}"


def is_quota_or_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = [
        "quota",
        "rate limit",
        "ratelimit",
        "resource_exhausted",
        "too many requests",
        "free tier",
        "limit exceeded",
        "429",
        "billing",
        "insufficient",
    ]
    return any(marker in text for marker in markers)


def key_candidates(managed_key_id: str, inline_api_key: str, project: str) -> list[dict[str, str]]:
    inline_api_key = (inline_api_key or "").strip()
    project = normalize_project(project)
    if inline_api_key:
        return [{"id": "inline", "label": "Key vừa dán", "project": project, "key": inline_api_key}]

    store = load_key_store()
    candidates = []
    if managed_key_id:
        item = get_managed_key(managed_key_id)
        if item and normalize_project(item.get("project", "Default")) == project:
            candidates.append(item)

    active = load_active_key_item()
    if active and not any(item.get("id") == active.get("id") for item in candidates):
        if normalize_project(active.get("project", "Default")) == project:
            candidates.append(active)

    for item in store.get("keys", []):
        if normalize_project(item.get("project", "Default")) != project:
            continue
        if not any(existing.get("id") == item.get("id") for existing in candidates):
            candidates.append(item)

    legacy_key = ""
    if not candidates and KEY_FILE.exists():
        legacy_key = KEY_FILE.read_text(encoding="utf-8").strip()
    if legacy_key:
        candidates.append({"id": "legacy", "label": "Key cũ đã lưu", "key": legacy_key})
    return candidates


def generate_tts_with_fallback(
    *,
    candidates: list[dict[str, str]],
    text: str,
    output_path: Path,
    voice: str,
    model: str,
    style: str,
) -> tuple[Path, dict[str, str], list[str]]:
    if not candidates:
        raise RuntimeError("Chưa có Gemini API key. Hãy dán key hoặc thêm key trong Key Manager.")

    attempts = []
    last_error: Exception | None = None
    for index, item in enumerate(candidates, start=1):
        label = item.get("label", "Gemini key")
        try:
            output = generate_tts(
                text=text,
                output_path=output_path,
                api_key=item.get("key", ""),
                voice=voice,
                model=model,
                style=style,
            )
            attempts.append(f"#{index} {label}: OK")
            return Path(output), item, attempts
        except Exception as exc:
            last_error = exc
            attempts.append(f"#{index} {label}: Lỗi — {exc}")
            if is_quota_or_rate_limit_error(exc):
                raise RuntimeError(
                    "Key đang bị quota/rate-limit/billing limit nên tool không tự đổi key để né giới hạn.\n\n"
                    + "\n".join(attempts)
                ) from exc

    raise RuntimeError("Tất cả key dự phòng đều lỗi:\n\n" + "\n".join(attempts)) from last_error


def load_history() -> list[dict[str, str]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def save_history(items: list[dict[str, str]]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(items[:30], ensure_ascii=False, indent=2), encoding="utf-8")


def record_history(
    wav_path: Path,
    mp3_path: Path | None,
    voice: str,
    style_preset: str,
    text: str,
    project: str = "Default",
    key_label: str = "",
) -> None:
    items = load_history()
    items.insert(
        0,
        {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "wav": wav_path.name,
            "mp3": mp3_path.name if mp3_path else "",
            "voice": voice,
            "style": style_preset,
            "project": project,
            "key_label": key_label,
            "preview": " ".join(text.split())[:110],
        },
    )
    save_history(items)


def convert_wav_to_mp3(wav_path: Path) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg = None
    if not ffmpeg:
        return None
    mp3_path = wav_path.with_suffix(".mp3")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(wav_path),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(mp3_path),
        ],
        check=True,
    )
    return mp3_path


def safe_output_file(filename: str, suffix: str) -> Path:
    path = (settings.outputs_dir / Path(filename).name).resolve()
    outputs_dir = settings.outputs_dir.resolve()
    if outputs_dir not in path.parents or path.suffix.lower() != suffix:
        raise RuntimeError("Tên file tải không hợp lệ.")
    if not path.exists():
        raise RuntimeError("File không tồn tại hoặc đã bị xóa.")
    return path


def render_result_page(
    wav_path: Path,
    mp3_path: Path | None,
    mp3_error: str | None = None,
    used_key_label: str = "",
    attempts: list[str] | None = None,
) -> str:
    wav_name = wav_path.name
    mp3_block = (
        f'<a class="button secondary" href="/download/mp3/{escape(mp3_path.name)}">Tải MP3</a>'
        if mp3_path
        else f'<span class="disabled">MP3 chưa tạo được: {escape(mp3_error or "máy chưa có FFmpeg trong PATH")}</span>'
    )
    attempts_html = ""
    if attempts:
        attempts_html = "<pre>" + escape("\n".join(attempts)) + "</pre>"
    return f"""
    <!doctype html>
    <html lang="vi">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Đã tạo giọng đọc</title>
      <style>
        body {{ font-family: system-ui, Arial, sans-serif; max-width: 900px; margin: 32px auto; padding: 0 16px; background: #070b16; color: #e5e7eb; }}
        .card {{ background: linear-gradient(145deg, #111827, #0f172a); border: 1px solid #166534; border-radius: 20px; padding: 26px; box-shadow: 0 18px 60px rgba(0,0,0,.35); }}
        audio {{ width: 100%; margin: 16px 0; }}
        pre {{ white-space: pre-wrap; background: #020617; border-radius: 12px; padding: 12px; color: #cbd5e1; }}
        .button {{ display: inline-block; margin: 8px 10px 8px 0; border-radius: 12px; background: #22c55e; color: #052e16; padding: 12px 18px; font-weight: 800; text-decoration: none; }}
        .secondary {{ background: #38bdf8; color: #082f49; }}
        .disabled {{ display: inline-block; margin: 8px 0; color: #fca5a5; background: #450a0a; border: 1px solid #991b1b; border-radius: 12px; padding: 12px 14px; }}
        a {{ color: #86efac; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Đã tạo giọng đọc</h1>
        <p>Nghe thử trước, rồi chọn file muốn tải.</p>
        <p>Key đã dùng: <strong>{escape(used_key_label)}</strong></p>
        <audio controls src="/download/wav/{escape(wav_name)}"></audio>
        <div>
          <a class="button" href="/download/wav/{escape(wav_name)}">Tải WAV</a>
          {mp3_block}
        </div>
        {attempts_html}
        <p><a href="/">← Về Voice Studio</a></p>
      </div>
    </body>
    </html>
    """


def render_history() -> str:
    rows = []
    for item in load_history()[:10]:
        wav = item.get("wav", "")
        mp3 = item.get("mp3", "")
        if not wav:
            continue
        wav_link = f'<a href="/download/wav/{escape(wav)}">WAV</a>'
        mp3_link = f' · <a href="/download/mp3/{escape(mp3)}">MP3</a>' if mp3 else ""
        rows.append(
            f"""
            <div class="history-item">
              <div><strong>{escape(item.get("created_at", ""))}</strong> · {escape(item.get("project", "Default"))} · {escape(item.get("voice", ""))} · {escape(item.get("style", ""))}</div>
              <div class="tiny">Key: {escape(item.get("key_label", ""))}</div>
              <div class="tiny">{escape(item.get("preview", ""))}</div>
              <div>{wav_link}{mp3_link}</div>
            </div>
            """
        )
    if not rows:
        return '<p class="hint">Chưa có file nào. Tạo thử một audio để lịch sử hiện ở đây.</p>'
    return "\n".join(rows)


def render_key_rows(test_result: str = "") -> str:
    store = load_key_store()
    active_id = store.get("active_id")
    rows = []
    for item in store.get("keys", []):
        key_id = item.get("id", "")
        active_badge = '<span class="ok">Đang dùng</span>' if key_id == active_id else ""
        rows.append(
            f"""
            <div class="key-row">
              <div>
                <strong>{escape(item.get("label", "Gemini key"))}</strong> {active_badge}
                <div class="tiny">Project: {escape(normalize_project(item.get("project", "Default")))} · {escape(mask_key(item.get("key", "")))} · thêm lúc {escape(item.get("created_at", ""))}</div>
              </div>
              <div class="key-actions">
                <form action="/keys/active" method="post"><input type="hidden" name="key_id" value="{escape(key_id)}"><button type="submit">Dùng key này</button></form>
                <form action="/keys/test" method="post"><input type="hidden" name="key_id" value="{escape(key_id)}"><button type="submit">Test</button></form>
                <form action="/keys/delete" method="post"><input type="hidden" name="key_id" value="{escape(key_id)}"><button class="danger-btn" type="submit">Xóa</button></form>
              </div>
            </div>
            """
        )
    if not rows:
        rows.append('<p class="hint">Chưa có key nào. Thêm key Gemini đầu tiên ở form bên dưới.</p>')
    result_html = f'<div class="notice">{escape(test_result)}</div>' if test_result else ""
    return result_html + "\n".join(rows)


def render_key_options() -> str:
    store = load_key_store()
    active_id = store.get("active_id")
    options = ['<option value="">Dùng key đang chọn trong Key Manager</option>']
    for item in store.get("keys", []):
        selected = " selected" if item.get("id") == active_id else ""
        label = f'{normalize_project(item.get("project", "Default"))} / {item.get("label", "Gemini key")} — {mask_key(item.get("key", ""))}'
        options.append(f'<option value="{escape(item.get("id", ""))}"{selected}>{escape(label)}</option>')
    return "\n".join(options)


def render_project_options() -> str:
    return "\n".join(f'<option value="{escape(project)}">{escape(project)}</option>' for project in list_projects())


def render_key_manager_page(test_result: str = "") -> str:
    active = load_active_key_item()
    active_text = (
        f'Đang dùng: <strong>{escape(active.get("label", ""))}</strong> ({escape(mask_key(active.get("key", "")))})'
        if active
        else "Chưa chọn key nào."
    )
    return f"""
    <!doctype html>
    <html lang="vi">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Key Manager — Voice Studio AI</title>
      <style>
        body {{ font-family: system-ui, Arial, sans-serif; max-width: 980px; margin: 28px auto; padding: 0 16px; background: #070b16; color: #e5e7eb; }}
        .card {{ background: rgba(17,24,39,.94); border: 1px solid #334155; border-radius: 20px; padding: 24px; box-shadow: 0 18px 60px rgba(0,0,0,.28); }}
        label {{ display: block; margin: 14px 0 6px; font-weight: 650; }}
        input {{ width: 100%; box-sizing: border-box; border-radius: 10px; border: 1px solid #475569; background: #020617; color: #e5e7eb; padding: 11px 12px; font-size: 15px; }}
        button {{ border: 0; border-radius: 10px; background: #22c55e; color: #052e16; padding: 10px 14px; font-weight: 850; cursor: pointer; }}
        .danger-btn {{ background: #ef4444; color: #fff; }}
        .tiny {{ color: #94a3b8; font-size: 13px; margin-top: 6px; }}
        .hint {{ color: #94a3b8; }}
        .ok {{ color: #86efac; border: 1px solid #166534; background: #052e16; border-radius: 999px; padding: 3px 8px; font-size: 12px; }}
        .notice {{ color: #fde68a; background: #422006; border: 1px solid #a16207; border-radius: 12px; padding: 12px; margin: 12px 0; }}
        .key-row {{ display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center; border-top: 1px solid #334155; padding: 14px 0; }}
        .key-actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
        a {{ color: #86efac; }}
        @media (max-width: 780px) {{ .key-row, .row {{ grid-template-columns: 1fr; }} }}
      </style>
    </head>
    <body>
      <div class="card">
        <p><a href="/">← Về Voice Studio</a></p>
        <h1>Quản lý Gemini API key</h1>
        <p class="hint">Lưu nhiều key theo project/khách hàng, chọn key đang dùng, và test thủ công. Khi tạo audio, fallback chỉ thử key cùng project đã chọn.</p>
        <p>{active_text}</p>
        {render_key_rows(test_result)}
      </div>

      <div class="card" style="margin-top:18px;">
        <h2>Thêm key mới</h2>
        <form action="/keys/add" method="post">
          <div class="row">
            <div>
              <label>Tên key / project / khách hàng</label>
              <input name="label" placeholder="Ví dụ: Shop A / Project YouTube / Key chính" required />
            </div>
            <div>
              <label>Project / khách hàng</label>
              <input name="project" placeholder="Ví dụ: Shop A, Kênh Review Phim, Khách X" value="Default" required />
            </div>
          </div>
          <div>
              <label>Gemini API key</label>
              <input name="api_key" type="password" placeholder="Dán key Gemini" required />
          </div>
          <button type="submit">Lưu và dùng key này</button>
        </form>
      </div>
    </body>
    </html>
    """


HTML = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Voice Studio AI</title>
  <style>
    body { font-family: system-ui, Arial, sans-serif; max-width: 1120px; margin: 28px auto; padding: 0 16px; background: radial-gradient(circle at top left, #1e3a8a 0, transparent 34%), #070b16; color: #e5e7eb; }
    .hero { margin-bottom: 18px; }
    .card { background: rgba(17,24,39,.92); border: 1px solid #334155; border-radius: 20px; padding: 24px; box-shadow: 0 18px 60px rgba(0,0,0,.28); backdrop-filter: blur(10px); }
    .brand { display: inline-flex; align-items: center; gap: 8px; color: #86efac; font-weight: 900; letter-spacing: .04em; text-transform: uppercase; font-size: 13px; }
    h1 { font-size: clamp(34px, 5vw, 58px); line-height: 1.02; margin: 14px 0; }
    h2 { margin: 0 0 10px; }
    .gradient { background: linear-gradient(90deg, #86efac, #38bdf8); -webkit-background-clip: text; color: transparent; }
    label { display: block; margin: 14px 0 6px; font-weight: 650; }
    input, textarea, select { width: 100%; box-sizing: border-box; border-radius: 10px; border: 1px solid #475569; background: #020617; color: #e5e7eb; padding: 11px 12px; font-size: 15px; }
    textarea { min-height: 150px; resize: vertical; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
    .pill { display:inline-block; border: 1px solid #334155; border-radius: 999px; padding: 6px 10px; margin: 4px 4px 4px 0; color:#cbd5e1; font-size: 13px; }
    button { margin-top: 18px; border: 0; border-radius: 12px; background: #22c55e; color: #052e16; padding: 13px 20px; font-weight: 900; cursor: pointer; font-size: 16px; }
    button:hover { background: #4ade80; }
    .hint { color: #94a3b8; }
    .tiny { color: #94a3b8; font-size: 13px; margin-top: 6px; }
    .saved { color: #86efac; background: #052e16; border: 1px solid #166534; padding: 10px 12px; border-radius: 10px; }
    .check { width: auto; margin-right: 8px; }
    .danger { color: #fca5a5; }
    .history-item { border-top: 1px solid #334155; padding: 12px 0; }
    a { color: #86efac; }
    @media (max-width: 880px) { .row, .row3 { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <section class="hero">
    <div class="card">
      <div class="brand">● Voice Studio AI</div>
      <h1>Tạo giọng đọc <span class="gradient">MP3/WAV</span> cho TikTok, YouTube và bán hàng.</h1>
      <p class="hint">Mỗi người tự dùng Gemini API key của mình, chọn voice/phong cách và tạo file nhanh ngay trên trình duyệt.</p>
      <div>
        <span class="pill">30 voice</span>
        <span class="pill">Preset tiếng Việt</span>
        <span class="pill">MP3 + WAV</span>
        <span class="pill">Không lưu API key</span>
      </div>
    </div>
  </section>

  <div class="card">
    <h2>Tạo giọng đọc</h2>
    <p class="hint">Dán Gemini API key của bạn để tạo audio. Key chỉ được gửi tới Gemini trong yêu cầu này và không được lưu trên máy chủ.</p>
    <form action="/tts" method="post">
      <label>Gemini API key</label>
      <input name="api_key" type="password" placeholder="Dán GEMINI_API_KEY từ Google AI Studio" autocomplete="off" minlength="20" maxlength="512" required />
      <div class="tiny">Ứng dụng không ghi key vào file, lịch sử hay nhật ký. Không dùng key của người khác.</div>

      <label>Nội dung cần đọc</label>
      <textarea name="text" maxlength="20000" placeholder="Xin chào, đây là bản đọc thử bằng Gemini Flash TTS." required></textarea>

      <div class="row">
        <div>
          <label>Voice</label>
          <select name="voice">
            __VOICE_OPTIONS__
          </select>
          <div class="tiny">Gợi ý: Khánh An hoặc Quang Minh cho rõ chữ; Minh Khôi hoặc Nhật Minh cho năng lượng; Hoài An hoặc Phương Anh cho chất giọng ấm mềm.</div>
        </div>
        <div>
          <label>Phong cách có sẵn</label>
          <select id="style_preset" name="style_preset">
            __STYLE_OPTIONS__
          </select>
          <div class="tiny">Chọn preset rồi chỉnh thêm ở ô bên dưới nếu muốn.</div>
        </div>
      </div>

      <label>Phong cách đọc tùy chỉnh / bổ sung</label>
      <textarea id="custom_style" name="custom_style" maxlength="2000" style="min-height: 92px;">Đọc tiếng Việt tự nhiên, rõ chữ, truyền cảm, tốc độ vừa phải.</textarea>

      <div class="row3">
        <div>
          <label>Tốc độ</label>
          <select name="pace">
            <option value="tốc độ vừa phải">Vừa phải</option>
            <option value="chậm, nhiều khoảng nghỉ">Chậm</option>
            <option value="nhanh vừa, không nuốt chữ">Nhanh vừa</option>
            <option value="rất nhanh nhưng vẫn rõ chữ">Rất nhanh</option>
          </select>
        </div>
        <div>
          <label>Cảm xúc</label>
          <select name="emotion">
            <option value="tự nhiên">Tự nhiên</option>
            <option value="vui vẻ và sáng">Vui vẻ</option>
            <option value="nghiêm túc và đáng tin">Nghiêm túc</option>
            <option value="hồi hộp và bí ẩn">Hồi hộp</option>
            <option value="ấm áp và thân thiện">Ấm áp</option>
            <option value="mạnh mẽ và truyền cảm hứng">Truyền cảm hứng</option>
          </select>
        </div>
        <div>
          <label>Model</label>
          <input name="model" value="__MODEL__" readonly />
        </div>
      </div>

      <button type="submit">Tạo giọng đọc</button>
    </form>
  </div>

  <script>
    const presets = __PRESETS_JSON__;
    const preset = document.getElementById("style_preset");
    const custom = document.getElementById("custom_style");
    preset.addEventListener("change", () => {
      if (presets[preset.value] !== undefined) custom.value = presets[preset.value];
      custom.focus();
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (
        HTML.replace("__VOICE_OPTIONS__", render_options(VOICE_OPTIONS, DEFAULT_VOICE))
        .replace("__STYLE_OPTIONS__", render_style_options())
        .replace("__MODEL__", DEFAULT_MODEL)
        .replace("__PRESETS_JSON__", __import__("json").dumps(STYLE_PRESETS, ensure_ascii=False))
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/forget-key")
def forget_key():
    return HTMLResponse("Tính năng lưu key không khả dụng trên bản công khai.", status_code=404)


@app.get("/keys", response_class=HTMLResponse)
def keys_page() -> str:
    return HTMLResponse("Tính năng quản lý key không khả dụng trên bản công khai.", status_code=404)


@app.post("/keys/add")
def keys_add():
    return HTMLResponse("Không khả dụng.", status_code=404)


@app.post("/keys/active")
def keys_active():
    return HTMLResponse("Không khả dụng.", status_code=404)


@app.post("/keys/delete")
def keys_delete():
    return HTMLResponse("Không khả dụng.", status_code=404)


@app.post("/keys/test", response_class=HTMLResponse)
def keys_test() -> str:
    return HTMLResponse("Không khả dụng.", status_code=404)


@app.get("/download/wav/{filename}")
def download_wav(filename: str):
    path = safe_output_file(filename, ".wav")
    return FileResponse(path, media_type="audio/wav", filename=path.name)


@app.get("/download/mp3/{filename}")
def download_mp3(filename: str):
    path = safe_output_file(filename, ".mp3")
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


@app.post("/tts")
def tts(
    api_key: str = Form(...),
    text: str = Form(...),
    style_preset: str = Form("Tự nhiên tiếng Việt"),
    custom_style: str = Form(""),
    pace: str = Form("tốc độ vừa phải"),
    emotion: str = Form("tự nhiên"),
    voice: str = Form(DEFAULT_VOICE),
    model: str = Form(DEFAULT_MODEL),
):
    api_key = (api_key or "").strip()
    text = (text or "").strip()
    custom_style = (custom_style or "").strip()

    allowed_voices = {name for name, _ in VOICE_OPTIONS}
    allowed_paces = {
        "tốc độ vừa phải",
        "chậm, nhiều khoảng nghỉ",
        "nhanh vừa, không nuốt chữ",
        "rất nhanh nhưng vẫn rõ chữ",
    }
    allowed_emotions = {
        "tự nhiên",
        "vui vẻ và sáng",
        "nghiêm túc và đáng tin",
        "hồi hộp và bí ẩn",
        "ấm áp và thân thiện",
        "mạnh mẽ và truyền cảm hứng",
    }
    validation_error = ""
    if not 20 <= len(api_key) <= 512:
        validation_error = "API key không hợp lệ. Hãy dán đúng Gemini API key của bạn."
    elif not text or len(text) > MAX_TEXT_LENGTH:
        validation_error = f"Nội dung phải có từ 1 đến {MAX_TEXT_LENGTH:,} ký tự."
    elif voice not in allowed_voices:
        validation_error = "Giọng đọc không hợp lệ."
    elif style_preset not in STYLE_PRESETS:
        validation_error = "Phong cách đọc không hợp lệ."
    elif len(custom_style) > MAX_STYLE_LENGTH:
        validation_error = f"Mô tả phong cách không được vượt quá {MAX_STYLE_LENGTH:,} ký tự."
    elif pace not in allowed_paces or emotion not in allowed_emotions:
        validation_error = "Tốc độ hoặc cảm xúc không hợp lệ."
    elif model != DEFAULT_MODEL:
        validation_error = "Model không được hỗ trợ trên ứng dụng này."

    if validation_error:
        return HTMLResponse(
            f'<h1>Thông tin chưa hợp lệ</h1><p>{escape(validation_error)}</p><p><a href="/">← Quay lại</a></p>',
            status_code=400,
        )

    preset_style = STYLE_PRESETS.get(style_preset, "")
    style_parts = [
        custom_style or preset_style,
        f"Tốc độ: {pace}.",
        f"Cảm xúc tổng thể: {emotion}.",
        "Phát âm tiếng Việt rõ, tự nhiên; không đọc tiêu đề DIRECTOR NOTES hoặc TRANSCRIPT.",
    ]
    style = "\n".join(part for part in style_parts if part)
    try:
        output_path = settings.outputs_dir / f"gemini_tts_{uuid4().hex}.wav"
        candidates = [{"id": "inline", "label": "API key riêng", "key": api_key}]
        output, used_key, attempts = generate_tts_with_fallback(
            candidates=candidates,
            text=text,
            output_path=output_path,
            voice=voice or DEFAULT_VOICE,
            model=model or DEFAULT_MODEL,
            style=style,
        )
        mp3_path = None
        mp3_error = None
        try:
            mp3_path = convert_wav_to_mp3(Path(output))
        except Exception as mp3_exc:
            mp3_error = str(mp3_exc)
        return HTMLResponse(
            render_result_page(
                Path(output),
                mp3_path,
                mp3_error,
                used_key_label="API key riêng của bạn — không lưu",
                attempts=attempts,
            )
        )
    except Exception as exc:
        public_error = str(exc).replace(api_key, "[API KEY]")[:1200]
        return HTMLResponse(
            f"""
            <!doctype html>
            <html lang="vi">
            <head>
              <meta charset="utf-8" />
              <title>Lỗi Gemini TTS</title>
              <style>
                body {{ font-family: system-ui, Arial, sans-serif; max-width: 820px; margin: 32px auto; padding: 0 16px; background: #0f172a; color: #e5e7eb; }}
                .card {{ background: #111827; border: 1px solid #ef4444; border-radius: 16px; padding: 22px; }}
                pre {{ white-space: pre-wrap; background: #020617; border-radius: 12px; padding: 14px; color: #fecaca; }}
                a {{ color: #86efac; }}
              </style>
            </head>
            <body>
              <div class="card">
                <h1>Chưa tạo được giọng đọc</h1>
                <p>Gemini trả về lỗi bên dưới. API key của bạn đã được ẩn:</p>
                <pre>{escape(public_error)}</pre>
                <p><a href="/">← Quay lại trang TTS</a></p>
              </div>
            </body>
            </html>
            """,
            status_code=502,
        )
