#!/bin/sh
# package_appliance.sh — assemble a self-hosted mtlm-router appliance tarball.
#
#   sh tools/package_appliance.sh --bin anvil-serve --model m7router3s384.bin \
#       --tok tok4096.bin --heads "m7router3s384.head m7router3s384.noul.head m7router3s384.score.head" \
#       --name m7router3s384 --out /tmp/appliance
#
# Produces <out>/mtlm-router-<name>-linux-amd64.tar.gz containing:
#   anvil-serve (static binary), models/{model.bin,tokenizer.bin,*.head},
#   start.sh (systemd-free), mtlm-router.service (systemd), README.md, VERSION.
# The appliance serves /v1/route + all typed endpoints on port 8097 (PORT env).
set -e

BIN="" MODEL="" TOK="" HEADS="" NAME="router" OUT=/tmp
while [ $# -gt 0 ]; do
  case "$1" in
    --bin) BIN="$2"; shift 2;; --model) MODEL="$2"; shift 2;;
    --tok) TOK="$2"; shift 2;;  --heads) HEADS="$2"; shift 2;;
    --name) NAME="$2"; shift 2;; --out) OUT="$2"; shift 2;;
    *) echo "unknown arg $1"; exit 1;;
  esac
done
[ -n "$BIN" ] && [ -n "$MODEL" ] && [ -n "$TOK" ] || {
  echo "need --bin --model --tok [--heads 'a.head b.head'] [--name N] [--out D]"; exit 1; }

PKG="$OUT/mtlm-router-$NAME-linux-amd64"
rm -rf "$PKG"; mkdir -p "$PKG/models"
cp "$BIN" "$PKG/anvil-serve"
cp "$MODEL" "$PKG/models/model.bin"
cp "$TOK" "$PKG/models/tokenizer.bin"
HENV=""
i=0
for h in $HEADS; do
  i=$((i+1)); base=$(basename "$h"); cp "$h" "$PKG/models/$base"
  case $i in
    1) HENV="$HENV ANVIL_HEAD=models/$base";;
    2) HENV="$HENV ANVIL_NOUL=models/$base";;
    3) HENV="$HENV ANVIL_SCORE=models/$base";;
  esac
done

cat > "$PKG/start.sh" <<EOF
#!/bin/sh
# mtlm-router appliance — start the server (no systemd needed).
# Env knobs: PORT (8097), ANVIL_ROUTE_MINCONF (0.55), ANVIL_LOG (decisions.jsonl),
# ANVIL_DELEGATE_URL/KEY/MODEL/SYS (optional upstream for delegated requests).
cd "\$(dirname "\$0")"
PORT=\${PORT:-8097}
export ANVIL_TOOLS_INJECT=0
export$HENV
export ANVIL_LOG=logs/decisions.jsonl
mkdir -p logs
echo "mtlm-router on http://0.0.0.0:\$PORT  (logs: logs/decisions.jsonl)"
exec ./anvil-serve models/model.bin "\$PORT"
EOF
chmod +x "$PKG/start.sh"

cat > "$PKG/mtlm-router.service" <<EOF
[Unit]
Description=mtlm-router — typed decision layer (pure MFL)
After=network.target
[Service]
Type=simple
WorkingDirectory=%h/mtlm-router-$NAME-linux-amd64
Environment=ANVIL_TOOLS_INJECT=0 ANVIL_LOG=logs/decisions.jsonl
ExecStart=%h/mtlm-router-$NAME-linux-amd64/anvil-serve models/model.bin 8097
Restart=on-failure
RestartSec=3
[Install]
WantedBy=default.target
EOF

cat > "$PKG/README.md" <<'EOF'
# mtlm-router appliance

Self-hosted typed decision layer — 7M-param router + decision heads, pure MFL,
no dependencies beyond a Linux x86_64 box.

## Run

    ./start.sh                 # systemd-free
    # or: cp mtlm-router.service ~/.config/systemd/user/ && systemctl --user start mtlm-router

## Use

    curl localhost:8097/v1/route -H 'content-type: application/json' \
        -d '{"state":"remind me to call the dentist tomorrow","execute":true}'
    # {"action":"tool_call","route":"set_reminder","confidence":0.99,...}

Endpoints: /v1/route (dispatcher), /v1/decide /v1/noul /v1/score /v1/assess
(typed heads), /v1/chat/completions (generative), /health.

Docs: github.com/javimosch/mtlm-router · HF: javimosch/mtlm-7m-router3s384
EOF

date -u +%Y-%m-%dT%H:%M:%SZ > "$PKG/VERSION"
echo "$NAME" >> "$PKG/VERSION"

tar -czf "$PKG.tar.gz" -C "$OUT" "mtlm-router-$NAME-linux-amd64"
du -sh "$PKG.tar.gz"
echo "wrote $PKG.tar.gz"
