#!/bin/bash
# If gscore is up and listening on 8765, but no client WS is established,
# restart discordbot (covers GsCore in-process AutoRestart leaving a stale bridge).
set -euo pipefail
systemctl --user is-active --quiet gscore || exit 0
systemctl --user is-active --quiet discordbot || exit 0
ss -ltn | grep -q ':8765 ' || exit 0
if ss -tn state established '( dport = :8765 or sport = :8765 )' 2>/dev/null | grep -q ESTAB; then
  exit 0
fi
# Fallback parse if ss filter unsupported
if ss -tnp 2>/dev/null | grep -E '127\.0\.0\.1:[0-9]+ +127\.0\.0\.1:8765|127\.0\.0\.1:8765 +127\.0\.0\.1:' | grep -q ESTAB; then
  exit 0
fi
logger -t discordbot-ws-watch 'no established WS to :8765; restarting discordbot'
systemctl --user restart discordbot
