# Voice Studio AI

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/dxuanphuong41-sketch/voice-studio-ai)

Ứng dụng FastAPI tạo giọng đọc Gemini TTS. Mỗi người dùng tự nhập API key; ứng dụng không lưu API key trên máy chủ.

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
