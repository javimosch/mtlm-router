#!/bin/sh
# package_appliance.sh — assemble a self-hosted mtlm-router appliance tarball.
#
#   sh tools/package_appliance.sh --bin anvil-serve --model m7router3s384.bin \
#       --tok tok4096.bin --heads "m7router3s384.head m7router3s384.noul.head m7router3s384.score.head" \
#       --gate moe_gate.head --experts "it_helpdesk:helpdesk.head fleet_gate:fleet_gate.head" \
#       --eval out/gate_eval.json --name m7router3s384 --out /tmp/appliance
#
# Produces <out>/mtlm-router-<name>-linux-amd64.tar.gz containing:
#   anvil-serve (static binary), models/{model.bin,tokenizer.bin,*.head},
#   start.sh (systemd-free), mtlm-router.service (systemd), README.md,
#   VERSION, manifest.json (sha256 of every artifact + embedded eval).
# The appliance serves /v1/route + all typed endpoints on port 8097 (PORT env).
set -e

BIN="" MODEL="" TOK="" HEADS="" GATE="" EXPERTS="" EVAL="" NAME="router" OUT=/tmp
while [ $# -gt 0 ]; do
  case "$1" in
    --bin) BIN="$2"; shift 2;; --model) MODEL="$2"; shift 2;;
    --tok) TOK="$2"; shift 2;;  --heads) HEADS="$2"; shift 2;;
    --gate) GATE="$2"; shift 2;; --experts) EXPERTS="$2"; shift 2;;
    --eval) EVAL="$2"; shift 2;;
    --name) NAME="$2"; shift 2;; --out) OUT="$2"; shift 2;;
    *) echo "unknown arg $1"; exit 1;;
  esac
done
[ -n "$BIN" ] && [ -n "$MODEL" ] && [ -n "$TOK" ] || {
  echo "need --bin --model --tok [--heads 'a.head b.head'] [--gate g.head --experts 'd:h.head'] [--eval f.json] [--name N] [--out D]"; exit 1; }

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
GENV=""
if [ -n "$GATE" ]; then
  cp "$GATE" "$PKG/models/$(basename "$GATE")"
  GENV="$GENV ANVIL_GATE=models/$(basename "$GATE")"
fi
XENV=""
if [ -n "$EXPERTS" ]; then
  xe="ANVIL_EXPERTS="
  first=1
  for d in $EXPERTS; do
    dom=${d%%:*}; h=${d#*:}; base=$(basename "$h")
    cp "$h" "$PKG/models/$base"
    if [ $first = 1 ]; then first=0; else xe="$xe,"; fi
    xe="$xe$dom:models/$base"
  done
  XENV=" $xe"
fi

cat > "$PKG/start.sh" <<EOF
#!/bin/sh
# mtlm-router appliance — start the server (no systemd needed).
# Env knobs: PORT (8097), ANVIL_ROUTE_MINCONF (0.55), ANVIL_GATE_MINCONF,
# ANVIL_POOL=max|mean, ANVIL_LOG (decisions.jsonl),
# ANVIL_DELEGATE_URL/KEY/MODEL/SYS (optional upstream for delegated requests).
cd "\$(dirname "\$0")"
PORT=\${PORT:-8097}
export ANVIL_TOOLS_INJECT=0
export$HENV$GENV$XENV
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
Environment=ANVIL_TOOLS_INJECT=0 ANVIL_LOG=logs/decisions.jsonl$HENV$GENV$XENV
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

With a gate head + experts loaded, the same call answers domain/expert too:

    {"action":"tool_call","route":"ticket_status","confidence":0.86,
     "domain":"it_helpdesk","gate_confidence":0.99,"expert":"it_helpdesk",...}

Endpoints: /v1/route (dispatcher), /v1/decide /v1/noul /v1/score /v1/assess
(typed heads), /v1/chat/completions (generative), /health.

manifest.json records sha256 of every shipped artifact and the eval of the
gate/head set at packaging time — check it before trusting confidences.

Docs: github.com/javimosch/mtlm-router · HF: javimosch/mtlm-7m-router3s384
EOF

date -u +%Y-%m-%dT%H:%M:%SZ > "$PKG/VERSION"
echo "$NAME" >> "$PKG/VERSION"

# manifest.json — the honesty artifact: what shipped, checksummed, evaluated.
sum() { sha256sum "$PKG/$1" | cut -d' ' -f1; }
M="$PKG/manifest.json"
{
  echo "{"
  echo "  \"name\": \"$NAME\","
  echo "  \"built\": \"$(cat "$PKG/VERSION" | head -1)\","
  echo "  \"model\": {\"file\": \"models/model.bin\", \"sha256\": \"$(sum models/model.bin)\"},"
  echo "  \"tokenizer\": {\"file\": \"models/tokenizer.bin\", \"sha256\": \"$(sum models/tokenizer.bin)\"},"
  echo -n "  \"heads\": {"
  first=1
  for f in "$PKG"/models/*.head; do
    b=$(basename "$f")
    [ "$b" = "$(basename "$GATE" 2>/dev/null)" ] && continue
    skip=0
    for d in $EXPERTS; do [ "$(basename "${d#*:}")" = "$b" ] && skip=1; done
    [ $skip = 1 ] && continue
    [ $first = 1 ] && first=0 || echo -n ","
    echo -n "\"$b\": \"$(sum "models/$b")\""
  done
  echo "},"
  if [ -n "$GATE" ]; then
    b=$(basename "$GATE")
    echo "  \"gate\": {\"file\": \"models/$b\", \"sha256\": \"$(sum "models/$b")\"},"
  fi
  if [ -n "$EXPERTS" ]; then
    echo -n "  \"experts\": {"
    first=1
    for d in $EXPERTS; do
      dom=${d%%:*}; b=$(basename "${d#*:}")
      [ $first = 1 ] && first=0 || echo -n ","
      echo -n "\"$dom\": {\"file\": \"models/$b\", \"sha256\": \"$(sum "models/$b")\"}"
    done
    echo "},"
  fi
  if [ -n "$EVAL" ] && [ -f "$EVAL" ]; then
    echo "  \"eval\": $(cat "$EVAL"),"
  fi
  echo "  \"endpoints\": [\"/v1/route\",\"/v1/decide\",\"/v1/noul\",\"/v1/score\",\"/v1/assess\",\"/v1/chat/completions\",\"/health\"]"
  echo "}"
} > "$M"
python3 -m json.tool "$M" > /dev/null 2>&1 || { echo "manifest.json invalid"; exit 1; }

tar -czf "$PKG.tar.gz" -C "$OUT" "mtlm-router-$NAME-linux-amd64"
du -sh "$PKG.tar.gz"
echo "wrote $PKG.tar.gz"
