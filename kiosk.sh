#!/bin/bash
# Launch the app in fullscreen kiosk mode on the Pi's screen.
# Run this after start.sh (or in a separate terminal/service).

# Wait for Flask to be ready
sleep 3

# Hide cursor, disable screen blanking
xset s off
xset -dpms
xset s noblank
unclutter -idle 0.1 -root &

# Launch Chromium in kiosk mode pointed at our local server
chromium-browser \
  --kiosk \
  --window-size=480,320 \
  --force-device-scale-factor=0.65 \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state \
  --no-first-run \
  --touch-events=enabled \
  --enable-features=TouchpadAndWheelScrollLatching \
  "http://localhost:5050"
