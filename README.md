# Voice Studio AI

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/dxuanphuong41-sketch/voice-studio-ai)

Ứng dụng FastAPI tạo giọng đọc Gemini TTS. Mỗi người dùng tự nhập API key; ứng dụng không lưu API key trên máy chủ.

## Tải bản desktop

Mở trang [Releases](https://github.com/dxuanphuong41-sketch/voice-studio-ai/releases/latest) và tải đúng phiên bản:

- **Windows:** `VoiceStudioAI-Windows.zip` — giải nén rồi chạy `VoiceStudioAI.exe`.
- **Mac Apple Silicon (M1/M2/M3/M4):** `VoiceStudioAI-macOS-Apple-Silicon.zip`.
- **Mac Intel đời cũ:** `VoiceStudioAI-macOS-Intel.zip`.

Ứng dụng chưa ký chứng thư nhà phát triển. Windows SmartScreen có thể yêu cầu chọn **More info > Run anyway**; trên macOS, nhấp chuột phải vào ứng dụng và chọn **Open** ở lần chạy đầu tiên.

## Chạy local

```powershell
pip install -r requirements-tts.txt
python -m uvicorn tts_web:app --host 127.0.0.1 --port 7860
```

Mở `http://127.0.0.1:7860`.

## Triển khai Render

1. Đẩy toàn bộ thư mục này lên repository GitHub.
2. Trong Render, chọn **New > Blueprint**.
3. Kết nối repository vừa tạo và bấm **Deploy Blueprint**.
4. Render dùng `render.yaml` và `Dockerfile` để build, sau đó cấp URL HTTPS công khai.

Ứng dụng có health check tại `/health`. File âm thanh trên gói miễn phí là tạm thời và có thể mất khi dịch vụ khởi động lại.
