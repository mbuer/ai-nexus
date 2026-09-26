#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

fail=0
ok(){ printf '✓ %s\n' "$1"; }
bad(){ printf '✗ %s\n' "$1" >&2; fail=1; }

echo "== AI Nexus repository hygiene =="

syntax_failed=0
while IFS= read -r file; do
    bash -n "$file" || syntax_failed=1
done < <(git ls-files 'scripts/*.sh')
[[ "$syntax_failed" -eq 0 ]] && ok "shell syntax passed" || bad "shell syntax failed"

perl_failed=0
while IFS= read -r file; do
    perl -c "$file" >/dev/null || perl_failed=1
done < <(git ls-files 'proxmox/*.pl')
[[ "$perl_failed" -eq 0 ]] && ok "Perl syntax passed" || bad "Perl syntax failed"

if git ls-files | grep -Eq '(^|/)(secrets|credentials)/|runtime\.local\.env$|\.key$|\.pem$|\.secret$'; then
    bad "Git tracks a secret-like path"
else
    ok "secret-like path check passed"
fi

tracked_text="$(git ls-files '*.md' '*.sh' '*.pl' '*.env' '*.yaml' '*.yml' '*.toml' '*.txt')"
if [[ -n "$tracked_text" ]] && grep -nE '-----BEGIN ([A-Z0-9 ]+ )?PRIVATE KEY-----|sk-proj-[A-Za-z0-9_-]+|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+' $tracked_text 2>/dev/null; then
    bad "possible credential material found"
else
    ok "credential-content check passed"
fi

scan_files="$(git ls-files '*.md' '*.sh' '*.pl' '*.env' '*.yaml' '*.yml' '*.toml' '*.txt' | grep -vE '(^|/)config/.*\.example\.(env|ya?ml)$' || true)"

if [[ -n "$scan_files" ]] && grep -nE '(^|[^0-9])(10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|192\.168\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3})([^0-9]|$)' $scan_files 2>/dev/null; then
    bad "private IPv4 address found outside example config"
else
    ok "private-address check passed"
fi

if [[ -n "$scan_files" ]] && grep -nE '/home/[A-Za-z0-9._-]+/' $scan_files 2>/dev/null; then
    bad "hard-coded home-directory path found"
else
    ok "environment-specific home-path check passed"
fi

if [[ -n "$scan_files" ]] && grep -nE 'VM[[:space:]]+[0-9]{2,}' $scan_files 2>/dev/null; then
    bad "hard-coded VM identifier found"
else
    ok "VM-identifier check passed"
fi

if ((fail)); then
    echo "Repository hygiene check failed." >&2
    exit 1
fi

echo "Repository hygiene check passed."
