#!/bin/sh
# Shows the TrainMetrics wall screen full screen. Started by the desktop at login.
URL=http://localhost:8000/scherm.html

# The app needs a while after boot; a browser that starts first shows an error page.
until curl -fs -o /dev/null http://localhost:8000/api/health; do
  sleep 3
done

# The panel has no EDID, so the desktop picks a standard mode unless told otherwise.
wlr-randr --output HDMI-A-1 --mode 480x800 || true

# The GPU path draws only a white window on a Pi 3, and this page needs no GPU.
# A Chromium window is at least 500 wide, so the page is drawn a little smaller to fit 480.
exec chromium \
  --kiosk "$URL" \
  --ozone-platform=wayland \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --password-store=basic \
  --disable-features=Translate,TranslateUI \
  --lang=nl \
  --accept-lang=nl-BE,nl \
  --window-position=0,0 \
  --window-size=480,800 \
  --force-device-scale-factor=0.96 \
  --disable-gpu \
  --renderer-process-limit=1 \
  --disk-cache-size=20000000
