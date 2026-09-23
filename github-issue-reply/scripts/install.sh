#!/usr/bin/env bash
# One-time per-user setup: GitHub token + default repo.
# Writes to this skill's own .env (skills/github-issue-reply/.env) — tracked
# in the shared skills repo dir, but the bare ".env" name is repo-gitignored
# (see the shared repo's top-level .gitignore), so it never leaves this
# developer's own clone. Same convention as apgpas-query/.env.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [[ -f "$ENV_FILE" ]]; then
    echo "Existing config found at $ENV_FILE:"
    echo ""
    grep -v '^GITHUB_TOKEN=' "$ENV_FILE" | sed 's/^/  /'
    echo "  GITHUB_TOKEN=********$(grep '^GITHUB_TOKEN=' "$ENV_FILE" | tail -c5)"
    echo ""
    read -rp "Overwrite? [y/N]: " OVERWRITE
    if [[ "$OVERWRITE" != "y" && "$OVERWRITE" != "Y" ]]; then
        echo "Keeping existing config."
        exit 0
    fi
fi

echo ""
echo "=== GitHub Issue Reply — Setup ==="
echo ""
echo "Get a token (fine-grained, GitHub's recommended type):"
echo "  1. https://github.com/settings/personal-access-tokens/new"
echo "  2. Resource owner -> pick the account/org that owns the repo(s)"
echo "  3. Repository access -> Only select repositories -> pick your repo(s)"
echo "  4. Permissions -> Add permissions -> Issues -> Read and write"
echo "  5. Generate token, copy it (starts with github_pat_)"
echo ""
read -rsp "GitHub token: " GITHUB_TOKEN
echo ""
read -rp "Default repo (owner/name, optional — leave blank to always pass --repo): " DEFAULT_REPO

echo "Verifying token..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/user")

if [[ "$STATUS" != "200" ]]; then
    echo "Warning: token check returned HTTP ${STATUS} — verify the token and re-run install.sh"
    exit 1
fi

LOGIN=$(curl -s \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/user" | python3 -c "import json,sys; print(json.load(sys.stdin).get('login'))")
echo "Connected as: ${LOGIN}"

cat > "$ENV_FILE" <<EOF
# Personal, per-developer config for the github-issue-reply skill.
# Tracked in the shared skills repo dir, but the bare ".env" name is
# repo-gitignored — this file stays on your own machine only.
GITHUB_TOKEN=${GITHUB_TOKEN}
GITHUB_DEFAULT_REPO=${DEFAULT_REPO}
GITHUB_LOGIN=${LOGIN}
EOF
chmod 600 "$ENV_FILE"

echo ""
echo "Written to $ENV_FILE (chmod 600)"
