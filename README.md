# BabelDOC ISO Builder

Build Ubuntu ISO tùy biến cho DGX Spark — cài xong tự boot vào BabelDOC PDF Translate.

## Kiến trúc

```
Boot DGX Spark
    │
    ├── Docker tự start (babeldoc.service)
    │       ├── gateway  :8088  ← API cho 3rd party
    │       └── web      :3000  ← giao diện web
    │
    └── Chromium kiosk fullscreen → http://localhost:3000
```

## Cách build (GitHub Actions)

1. **Push repo lên GitHub**

```bash
cd ~/babeldoc-appliance
git init && git add . && git commit -m "Initial"
gh repo create babeldoc-appliance --public --push
```

2. **Config Secrets** trong GitHub repo:
   - `Settings → Secrets and variables → Actions`
   - Add Repository secrets:
     - `TRANSLATION_API_KEY` — key LLM backend
     - `TRANSLATION_BASE_URL` — URL LLM backend
     - `API_KEYS` — key auth API
     - `NEXT_PUBLIC_API_KEY` — key frontend
     - `RETAIN_API_KEY`, `RETAIN_PADDLE_TOKEN` (nếu dùng OCR)
   - Add Repository variables (nếu cần override mặc định):
     - `TRANSLATION_MODEL`, `OCR_MODEL`, `QPS`...

3. **Chạy build**: `Actions → Build BabelDOC ISO → Run workflow`
4. **Download ISO** từ Artifacts (~15-20 phút)

## Port sau khi cài

| Port | Service |
|---|---|
| 22 | SSH |
| 3000 | Web UI |
| 8088 | API Gateway |

## API

```bash
# Upload PDF
curl -X POST http://<ip>:8088/api/v1/uploads \
  -H "X-Api-Key: YOUR_KEY" -F "file=@document.pdf"

# Create translation job
curl -X POST http://<ip>:8088/api/v1/jobs \
  -H "X-Api-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"upload_id": "xxx", "target_language": "vi"}'

# Check status
curl http://<ip>:8088/api/v1/jobs/<id> -H "X-Api-Key: YOUR_KEY"

# Download result
curl http://<ip>:8088/api/v1/jobs/<id>/artifacts/mono \
  -H "X-Api-Key: YOUR_KEY" -o translated.pdf
```

## Debug

```bash
journalctl -u babeldoc -f
journalctl -u babeldoc-x11 -f
docker compose -f /opt/babeldoc-web/docker-compose.yml logs
ss -tulpn | grep -E '3000|8088'
```
