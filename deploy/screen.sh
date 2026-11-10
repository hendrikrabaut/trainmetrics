#!/bin/sh
# Shows the TrainMetrics wall screen full screen. Started by the desktop at login.
URL=http://localhost:8000/scherm.html

# The app needs a while after boot; a browser that starts first shows an error page.
until curl -fs -o /dev/null http://localhost:8000/api/health; do
  sleep 3
done

exec chromium \
  --kiosk "$URL" \
  --ozone-platform=wayland \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --password-store=basic \
  --disable-features=Translate \
  --renderer-process-limit=1 \
  --disk-cache-size=20000000
