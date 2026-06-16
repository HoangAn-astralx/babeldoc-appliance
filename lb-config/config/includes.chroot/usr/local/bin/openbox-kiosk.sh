#!/bin/bash
# Tắt screensaver và power management
xset s off
xset s noblank
xset -dpms

# Ẩn chuột khi không dùng
unclutter -idle 1 &

# Start openbox làm window manager nhẹ
openbox &

# Chờ BabelDOC web sẵn sàng
until curl -sf http://localhost:3000 > /dev/null; do
    sleep 3
done

# Mở Chromium fullscreen
exec chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --disable-translate \
    http://localhost:3000
