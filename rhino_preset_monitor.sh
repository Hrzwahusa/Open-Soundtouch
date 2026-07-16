#!/bin/sh
# Überwacht den Rhino-Syslog auf Preset-Tastendrücke und triggert den Handler.
#
# Wichtig für niedrige Latenz: pro Log-Zeile wird KEIN 'echo | grep' mehr
# geforkt (das ließ die Schleife bei Log-Fluten während des Stream-Wechsels
# zurückfallen -> 9-15 s Verzögerung). Stattdessen filtert das 'case'-Builtin
# ohne Fork; nur bei echten Treffern wird 'sed' aufgerufen.

LOG="/tmp/rhino_preset_monitor.log"
HANDLER="/mnt/nv/preset_handler_daemon.sh"

echo "[$(date +%T)] === Rhino Preset Monitor Started ===" >> "$LOG"

last_num=""
last_time=0

logread -f | while read line; do
    case "$line" in
        *RhinoKeyHandler*invalid:*)
            preset_num=$(echo "$line" | sed -n 's/.*invalid: *\([0-9]\).*/\1/p')
            [ -z "$preset_num" ] && continue

            # Entprellung: gleiche Taste innerhalb von 2 s ignorieren
            now=$(date +%s)
            if [ "$preset_num" = "$last_num" ] && [ $((now - last_time)) -lt 2 ]; then
                continue
            fi
            last_num="$preset_num"
            last_time="$now"

            echo "[$(date +%T)] Detected Preset $preset_num press" >> "$LOG"
            "$HANDLER" play "$preset_num" >> "$LOG" 2>&1 &
            ;;
    esac
done
