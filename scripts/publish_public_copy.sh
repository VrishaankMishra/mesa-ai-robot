#!/usr/bin/env bash
# Regenerate the PUBLIC repo (VrishaankMishra/mesa-ai-robot) from this PRIVATE
# working repo (mesa-ai-robot-private), with sensitive paths scrubbed from the
# ENTIRE history. Run from the private repo root after merging to main.
#
#   bash scripts/publish_public_copy.sh
#
# THE EXCLUSION LIST BELOW IS THE SINGLE SOURCE OF TRUTH for what never goes
# public. Add new sensitive paths here AND put new sensitive files under
# private/ so they're covered by default.
set -euo pipefail

EXCLUDE_PATHS=(
  private
  docs/paper
  docs/proposal
  docs/engineering-notebook.md
  docs/eval/val_batch0_pred.jpg
  scripts/make_paper_pdf.py
  scripts/make_urtc_poster.py
  scripts/make_poster_figures.py
)
# Secret strings rewritten across all history (literal==>replacement per line).
REPLACEMENTS="$(mktemp)"
cat > "$REPLACEMENTS" <<'REPL'
mesa-alerts-CHANGEME==>mesa-alerts-CHANGEME
REPL

command -v git-filter-repo >/dev/null || { echo "pip install git-filter-repo first"; exit 1; }

SRC="$(git rev-parse --show-toplevel)"
BUILD="$(mktemp -d)/public-build"
git -C "$SRC" fetch -q origin && git -C "$SRC" merge -q --ff-only origin/main 2>/dev/null || true

git clone -q --no-local "$SRC" "$BUILD"
cd "$BUILD" && git checkout -q main
# Fresh clones do NOT inherit the source repo's local git config — pin the
# project author explicitly or new commits fall back to the machine's global
# identity (this bit us once: the curation commit published as the wrong author).
git config user.name  "VrishaankMishra"
git config user.email "vrishaank.mishra@gmail.com"

ARGS=(--force --invert-paths --replace-text "$REPLACEMENTS")
for p in "${EXCLUDE_PATHS[@]}"; do ARGS+=(--path "$p"); done
git-filter-repo "${ARGS[@]}"

# Verify nothing excluded survives anywhere in history.
for p in "${EXCLUDE_PATHS[@]}"; do
  if [ -n "$(git log --all --oneline -- "$p")" ]; then
    echo "FATAL: history still contains $p"; exit 1
  fi
done

# Public curation: README/link fixes live in the private repo as a patch so they
# re-apply identically each publish.
if [ -f "$SRC/scripts/public-curation.patch" ]; then
  git apply "$SRC/scripts/public-curation.patch"
  git add -A && git commit -q -m "Public release curation"
fi

git remote add public https://github.com/VrishaankMishra/mesa-ai-robot.git
echo "About to FORCE-PUSH the regenerated history to the public repo."
read -r -p "Type PUBLISH to continue: " ans
[ "$ans" = "PUBLISH" ] || { echo "aborted"; exit 1; }
git push --force public main
echo "done: https://github.com/VrishaankMishra/mesa-ai-robot"
