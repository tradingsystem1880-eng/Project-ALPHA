#!/usr/bin/env bash
# Give every downloaded screenshot the extension its bytes actually deserve.
# Drive labels all of these .PNG but a couple are JPEG, and the Read tool needs a
# truthful extension to render them. Idempotent: safe to re-run while downloads land.
set -euo pipefail
cd "$(dirname "$0")/../../data/cache/ace_images" 2>/dev/null || exit 0
shopt -s nullglob
for f in *.img *.PNG; do
  case "$(file -b --mime-type "$f")" in
    image/png)  mv -f "$f" "${f%.*}.png" ;;
    image/jpeg) mv -f "$f" "${f%.*}.jpg" ;;
  esac
done
ls | wc -l
