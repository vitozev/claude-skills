#!/usr/bin/env bash
# Is this file ready to upload? Prints size, fps, duration, loudness and true peak, and fails if the loudness is
# off target (-14 LUFS ±1) or the true peak is above -1 dBTP.
# Usage: bash check-final.sh <video> [expected WxH, e.g. 1080x1920]
set -euo pipefail
v="${1:?usage: bash check-final.sh <video> [WxH]}"
want="${2:-}"
IFS=, read -r w h fps <<<"$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$v")"
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$v")
stats=$(ffmpeg -nostats -i "$v" -af ebur128=peak=true -f null - 2>&1 | tail -14)
lufs=$(echo "$stats" | awk '/I:/{print $2; exit}')
tp=$(echo "$stats" | awk '/Peak:/{print $2; exit}')
printf '%s\n  %sx%s  %s fps  %.2f s\n  loudness %s LUFS  true peak %s dBTP\n' "$v" "$w" "$h" "$fps" "$dur" "$lufs" "$tp"
fail=0
[ -n "$want" ] && [ "${w}x${h}" != "$want" ] && { echo "  FAIL size: want $want"; fail=1; }
python3 -c "import sys; sys.exit(0 if abs($lufs + 14) <= 1 else 1)" || { echo "  FAIL loudness: want -14 LUFS ±1"; fail=1; }
python3 -c "import sys; sys.exit(0 if $tp <= -1 else 1)" || { echo "  FAIL true peak: want ≤ -1 dBTP"; fail=1; }
[ $fail = 0 ] && echo "  PASS"
exit $fail
