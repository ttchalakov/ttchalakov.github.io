#!/usr/bin/env bash
# Publish the site with no git history: replace main with a single commit of the current files and
# force-push it. Pushing main starts .github/workflows/deploy.yml, which rebuilds the site and also
# keeps gh-pages to a single commit.
#
# History is wiped on purpose, for privacy: once an email, photo, or other detail is removed from the
# site, it should not stay visible in the repository's commit history on GitHub.
#
# Usage: bin/publish.sh "Commit message"
set -euo pipefail

message="${1:?Usage: bin/publish.sh \"Commit message\"}"
cd "$(dirname "$0")/.."

if [ "$(git rev-parse --abbrev-ref HEAD)" != main ]; then
  echo "Switch to main first." >&2
  exit 1
fi

# Build a new root commit from everything git doesn't ignore, then make it main.
git checkout --quiet --orphan publish-tmp
git add -A
git commit --quiet -m "$message"
git branch -D main >/dev/null
git branch -m main
git push --force --set-upstream origin main

# Drop the old commits from this computer too.
git reflog expire --expire=now --all
git gc --quiet --prune=now

echo "Published $(git rev-parse --short HEAD) as the only commit on main."
