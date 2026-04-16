#!/usr/bin/env bash
# Sync the skill folders in this repo to the OpenClaw skills directory.
# Usage: ./scripts/install-skills.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${OPENCLAW_SKILLS_DIR:-$HOME/.openclaw/skills}/autofanpage"

echo "Installing skills from $REPO_ROOT/skills -> $TARGET"
mkdir -p "$TARGET"

for skill_dir in "$REPO_ROOT"/skills/*/; do
    skill_name="$(basename "$skill_dir")"
    dest="$TARGET/$skill_name"
    rm -rf "$dest"
    cp -R "$skill_dir" "$dest"
    echo "  ✓ $skill_name"
done

echo "Done. Skills installed at $TARGET"
echo "Verify with: openclaw skills list | grep autofanpage"
