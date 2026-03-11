#!/bin/bash
# Quick Langfuse trace viewer
# Usage: ./scripts/traces.sh [limit] [trace_id]

source .env 2>/dev/null

AUTH="$LANGFUSE_PUBLIC_KEY:$LANGFUSE_SECRET_KEY"
BASE="$LANGFUSE_BASE_URL/api/public"

if [ -n "$2" ]; then
    # Fetch specific trace with observations
    curl -s -u "$AUTH" "$BASE/traces/$2" | python3 -c "
import sys, json
t = json.load(sys.stdin)
print(f\"Trace: {t['id']}\")
print(f\"User: {t.get('userId', '?')}\")
print(f\"Input: {json.dumps(t.get('input', {}), ensure_ascii=False)[:200]}\")
print(f\"Output: {json.dumps(t.get('output', {}), ensure_ascii=False)[:300]}\")
print(f\"Latency: {t.get('latency', '?')}s\")
print(f\"Tags: {t.get('tags', [])}\")
print()
for obs in t.get('observations', []):
    print(f\"  [{obs.get('type','?')}] {obs.get('name','?')} — {obs.get('model','?')} — {obs.get('latency','?')}s\")
    if obs.get('input'):
        inp = json.dumps(obs['input'], ensure_ascii=False)[:200]
        print(f\"    input: {inp}\")
    if obs.get('output'):
        out = json.dumps(obs['output'], ensure_ascii=False)[:200]
        print(f\"    output: {out}\")
"
else
    # List recent traces
    LIMIT=${1:-5}
    curl -s -u "$AUTH" "$BASE/traces?limit=$LIMIT&orderBy=timestamp.desc" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data.get('data', []):
    ts = t.get('timestamp', '')[:19]
    user = t.get('userId', '?')
    inp = json.dumps(t.get('input', {}), ensure_ascii=False)[:100]
    latency = t.get('latency', '?')
    print(f\"{ts} | user={user} | {latency}s | {inp}\")
    print(f\"  id={t['id']}\")
    out = json.dumps(t.get('output', {}), ensure_ascii=False)[:150]
    print(f\"  output: {out}\")
    print()
"
fi
