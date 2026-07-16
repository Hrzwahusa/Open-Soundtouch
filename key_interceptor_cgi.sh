#!/bin/sh
# key_interceptor_cgi.sh  (fork-arm optimiert)
# Läuft pro Verbindung via BusyBox 'nc -l -e' auf Port 8089.
# - Fängt NUR einen echten PRESET_[1-6]-Tastendruck (state=press) ab -> lokale
#   Radiowiedergabe; antwortet dann sofort mit 200.
# - Alles andere wird transparent an den echten Bose-Server (127.0.0.1:8090)
#   weitergeleitet.
#
# Latenz-Optimierung: statt awk/sed/grep/wc + Subshell-Pipes werden Shell-
# Builtins (Parameter-Expansion, case) genutzt und der Forward in EINEM printf
# an nc gepiped. Für GET-Anfragen (Volume/now_playing/info-Polling) bleibt so
# nur ein einziger Fork (nc) statt ~5-6. Kein Logging im Hot-Path.

HANDLER="/mnt/nv/preset_handler_daemon.sh"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT=8090
LOG="/tmp/key_interceptor.log"
CR=$(printf '\r')
NL='
'
CRLF="$CR$NL"

# --- Request-Zeile (CR strippen) ---
IFS= read -r REQ_LINE || exit 0
REQ_LINE=${REQ_LINE%$CR}

# Pfad ohne awk: nach der Methode bis zum nächsten Space
_rest=${REQ_LINE#* }
REQ_PATH=${_rest%% *}

# --- Header lesen; Forward-Puffer direkt mit echtem CRLF aufbauen ---
FWD_HEADERS=""
CONTENT_LENGTH=0
while IFS= read -r line; do
  line=${line%$CR}
  [ -z "$line" ] && break
  case "$line" in
    [Cc]onnection:*) continue ;;              # eigene Connection-Policy
    [Cc]ontent-[Ll]ength:*)                    # nicht durchreichen -> neu berechnen
      _v=${line#*:}; _v=${_v# }
      CONTENT_LENGTH=${_v%%[!0-9]*}
      [ -z "$CONTENT_LENGTH" ] && CONTENT_LENGTH=0
      continue ;;
  esac
  FWD_HEADERS="$FWD_HEADERS$line$CRLF"
done

# --- Body (nur bei Content-Length) ---
BODY=""
if [ "$CONTENT_LENGTH" -gt 0 ] 2>/dev/null; then
  BODY=$(dd bs=1 count="$CONTENT_LENGTH" 2>/dev/null)
fi

# --- Preset-Press erkennen (nur Builtins) ---
NUM=""
case "$REQ_PATH" in
  */key*)
    _scan="$REQ_PATH $BODY"
    case "$_scan" in
      *PRESET_[1-6]*)
        case "$_scan" in
          *press*|*PRESS*)
            NUM=$(printf '%s' "$_scan" | sed -n 's/.*PRESET_\([1-6]\).*/\1/p') ;;
        esac ;;
    esac ;;
esac

if [ -n "$NUM" ]; then
  echo "[$(date '+%H:%M:%S')] Intercept PRESET_$NUM press -> play $NUM" >> "$LOG"
  "$HANDLER" play "$NUM" >/dev/null 2>&1 &
  RESP='<?xml version="1.0"?><status>/key</status>'
  printf 'HTTP/1.1 200 OK\r\nContent-Type: text/xml\r\nConnection: close\r\nContent-Length: %s\r\n\r\n%s' "${#RESP}" "$RESP"
else
  # Forward: komplette Anfrage in EINEM printf an nc (einziger Fork im GET-Fall)
  if [ "$CONTENT_LENGTH" -gt 0 ] 2>/dev/null; then
    BLEN=$(printf '%s' "$BODY" | wc -c); BLEN=${BLEN## }
    printf '%s\r\n%sContent-Length: %s\r\nConnection: close\r\n\r\n%s' \
      "$REQ_LINE" "$FWD_HEADERS" "$BLEN" "$BODY" | nc -w 10 "$BACKEND_HOST" "$BACKEND_PORT"
  else
    printf '%s\r\n%sConnection: close\r\n\r\n' \
      "$REQ_LINE" "$FWD_HEADERS" | nc -w 10 "$BACKEND_HOST" "$BACKEND_PORT"
  fi
fi
