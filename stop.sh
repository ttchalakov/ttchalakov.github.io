#!/usr/bin/env bash
# Turn off the local preview started by ./start.sh.
set -euo pipefail
cd "$(dirname "$0")"

PID_FILE=tmp/server.pid

# True if the PID belongs to a `jekyll serve` for this site (guards against stale or reused PIDs).
is_site_server() { ps -p "$1" -o command= 2>/dev/null | grep -F "$PWD/vendor/bundle/" | grep -q "jekyll serve"; }

# The PID recorded by ./start.sh, plus any other `jekyll serve` running for this site
# (for example one started by hand with `bundle exec jekyll serve`).
candidates="$(cat "$PID_FILE" 2>/dev/null || true) $(pgrep -f "$PWD/vendor/bundle/ruby/.*/bin/jekyll serve" || true)"

stopped=false
for pid in $(echo $candidates | tr ' ' '\n' | sort -u); do
  is_site_server "$pid" || continue
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do # give it up to 10 seconds to shut down cleanly
    is_site_server "$pid" || break
    sleep 0.5
  done
  if is_site_server "$pid"; then kill -9 "$pid" 2>/dev/null || true; fi
  stopped=true
done
rm -f "$PID_FILE"

if "$stopped"; then
  echo "Stopped the local website."
else
  echo "The local website isn't running."
fi
