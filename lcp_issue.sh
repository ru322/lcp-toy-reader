#!/usr/bin/env bash
set -euo pipefail

OUT="licensed.epub"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ライセンス（.lcpl）を取得
curl -fsS -u admin:admin \
  -H 'Content-Type: application/json' \
  -X POST --data-binary @"$(dirname "$0")/test/partial-license.json" \
  "http://localhost:8989/licenses/" \
  -o "$WORK/license.lcpl"

# ライセンスの publication リンクから暗号化済み EPUB を取得する
PUB_URL="$(jq -r '.links[] | select(.rel == "publication") | .href' "$WORK/license.lcpl")"
curl -fsS "$PUB_URL" -o "$OUT"

# license.lcpl を埋め込む
mkdir -p "$WORK/META-INF"
cp "$WORK/license.lcpl" "$WORK/META-INF/license.lcpl"
(cd "$WORK" && zip -q "$OLDPWD/$OUT" META-INF/license.lcpl)

echo "issued: $OUT"
jq . "$WORK/license.lcpl"
