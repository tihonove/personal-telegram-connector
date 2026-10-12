#!/usr/bin/env bash
# Opens a PR to tihonove.dev-apps with apps/<app>.yaml, as described in its GUIDE.md.
set -euo pipefail
APP="$1"
REPO_URL="$(gh repo view --json url -q .url)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

gh repo clone tihonove/tihonove.dev-apps "$WORK" -- -q
cd "$WORK"
git switch -c "register-$APP"
sed -e "s/APP/$APP/g" -e "s#REPO_URL#$REPO_URL#" -e 's/BRANCH/main/' -e 's#PATH_IN_REPO#./deploy#' \
  templates/app.yaml > "apps/$APP.yaml"
git add "apps/$APP.yaml"
git commit -qm "Register $APP"
git push -qu origin "register-$APP"
gh pr create --fill --body "Регистрация $APP из $REPO_URL (ветка main, ./deploy)."
