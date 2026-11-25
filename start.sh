#!/usr/bin/env bash
# Turn on the local preview of the website (runs in the background).
#   ./start.sh          serve at http://localhost:4000; pages rebuild automatically when you save
#   ./start.sh --open   same, and open it in your browser
# Turn it off with ./stop.sh. Server output, including build errors, goes to tmp/server.log.
set -euo pipefail
cd "$(dirname "$0")"

PORT=4000
URL="http://localhost:$PORT"
PID_FILE=tmp/server.pid
LOG_FILE=tmp/server.log

# True if the PID belongs to a `jekyll serve` for this site (guards against stale or reused PIDs).
is_site_server() { ps -p "$1" -o command= 2>/dev/null | grep -F "$PWD/vendor/bundle/" | grep -q "jekyll serve"; }

if [ -f "$PID_FILE" ] && is_site_server "$(cat "$PID_FILE")"; then
  echo "Already running at $URL (turn it off with ./stop.sh)."
  exit 0
fi
rm -f "$PID_FILE"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use. If it's this site, run ./stop.sh first. Currently listening:"
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
  exit 1
fi

# Ruby 3.3 from Homebrew; the macOS system Ruby is too old for this site.
if [ -x /opt/homebrew/opt/ruby@3.3/bin/ruby ]; then
  export PATH="/opt/homebrew/opt/ruby@3.3/bin:$PATH"
fi

# Install the site's gems into vendor/bundle on the first run (or after the Gemfile changes).
bundle config set --local path vendor/bundle >/dev/null
bundle check >/dev/null 2>&1 || bundle install

mkdir -p tmp
config=_config.yml
# Responsive WebP images need ImageMagick's `convert`. Without it, serve the original images.
if ! command -v convert >/dev/null 2>&1; then
  printf 'imagemagick:\n  enabled: false\n' >tmp/no-imagemagick.yml
  config="$config,tmp/no-imagemagick.yml"
  echo "ImageMagick not found, so images won't be resized locally (to fix: brew install imagemagick)."
fi

echo "Starting the local website..."
nohup bundle exec jekyll serve --config "$config" --port "$PORT" --livereload >"$LOG_FILE" 2>&1 &
pid=$!
echo "$pid" >"$PID_FILE"

# Wait for the first build to finish (or fail).
for _ in $(seq 1 240); do
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "The server stopped while starting. Last lines of $LOG_FILE:"
    tail -n 25 "$LOG_FILE"
    exit 1
  fi
  if grep -q "Server running" "$LOG_FILE"; then
    echo "Website running at $URL"
    echo "Edits rebuild automatically (restart after changing _config.yml). Log: $LOG_FILE. Turn off: ./stop.sh"
    if [ "${1:-}" = "--open" ]; then open "$URL"; fi
    exit 0
  fi
  sleep 0.5
done
echo "Still starting after 2 minutes; check $LOG_FILE (turn off with ./stop.sh)."
