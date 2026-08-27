#!/bin/bash
# Render a screenshot of a WiCAN http-config UI tab from the firmware's
# homepage HTML, with the requested sidebar tab highlighted and the
# device-default values selected.
#
# Usage:
#   wican_ui_screenshot.sh <homepage_full.html> <tab-id> <out.png> [--width W] [--height H]
#
#   <homepage_full.html>  path to the firmware's main/homepage_full.html
#   <tab-id>              HTML id of the tab to show (e.g. buttons_tab, status_view)
#   <out.png>             output file
#   --width/--height      optional viewport size (default 900x1200)
#
# The script clones the page, shows the requested tab, adds the "active" class
# to the matching sidebar button, and sets the precondition selects
# (precon_mode=once, precon_button=sw_star, precon_press=short,
# can_fwd_mode=mitm) to the device defaults before rendering. Requires
# google-chrome (headless). Use the tablink onclick text to find the button:
# the tab-id must appear inside the onclick attribute of a .tablinks button.
#
# The screenshot is cropped just below the "Submit Changes" button: the page
# leaves a large blank area below it, so we find the button's viewport-relative
# bottom edge (recorded into <title> via the injected script and read back with
# --dump-dom) and trim the image to that row plus a small margin.

set -euo pipefail

if [ "$#" -lt 3 ]; then
    echo "usage: $0 <homepage_full.html> <tab-id> <out.png> [--width W] [--height H]" >&2
    exit 2
fi

SRC="$1"
TAB_ID="$2"
OUT="$3"
WIDTH=900
HEIGHT=1200

shift 3
while [ "$#" -gt 0 ]; do
    case "$1" in
        --width) WIDTH="$2"; shift 2 ;;
        --height) HEIGHT="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
RENDERED="$TMP/render.html"

cp "$SRC" "$RENDERED"
cat >> "$RENDERED" << EOF
<script>
// injected: show the requested tab, highlight it in the sidebar, set device defaults
(function(){
  var tabs = document.getElementsByClassName("tabcontent");
  for (var i=0;i<tabs.length;i++){ tabs[i].style.display="none"; }
  var links = document.getElementsByClassName("tablinks");
  for (var j=0;j<links.length;j++){ links[j].classList.remove("active"); }
  var tab = document.getElementById("$TAB_ID");
  if (tab) { tab.style.display = "block"; }
  var btn = document.querySelector(".tablinks[onclick*='$TAB_ID']");
  if (btn) { btn.classList.add("active"); }
  // device defaults (mirror main/config_server.c defaults)
  var m=document.getElementById("precon_mode"); if (m) m.value="once";
  var b=document.getElementById("precon_button"); if (b) b.value="sw_star";
  var p=document.getElementById("precon_press"); if (p) p.value="short";
  var f=document.getElementById("can_fwd_mode"); if (f) f.value="mitm";
  // record the bottom edge of the submit button for cropping
  var sub = document.getElementById("submit_button");
  if (sub) { document.title = "SUBMIT_BOTTOM=" + Math.round(sub.getBoundingClientRect().bottom); }
})();
</script>
EOF

google-chrome --headless=new --disable-gpu \
    --window-size="${WIDTH},${HEIGHT}" \
    --virtual-time-budget=5000 \
    --screenshot="$OUT" \
    --hide-scrollbars \
    "file://$RENDERED" 2>/dev/null

# read back the recorded button bottom edge
BOTTOM="$(google-chrome --headless=new --disable-gpu \
    --virtual-time-budget=5000 \
    --dump-dom \
    "file://$RENDERED" 2>/dev/null | grep -o 'SUBMIT_BOTTOM=[0-9]*' | head -1 | cut -d= -f2)"

if [ -n "$BOTTOM" ]; then
    python3 -c "
from PIL import Image
img = Image.open('$OUT')
h = min(int('$BOTTOM') + 24, img.size[1])
img.crop((0, 0, img.size[0], h)).save('$OUT')
"
fi

echo "wrote $OUT"
