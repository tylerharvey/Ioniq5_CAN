#!/bin/bash
# Render a screenshot of a WiCAN http-config UI tab from the firmware's
# homepage HTML, with the requested sidebar tab highlighted and the
# device-default values selected.
#
# Usage:
#   wican_ui_screenshot.sh <homepage_full.html> <tab-id> <out.png> [--width W] [--height H]
#                          [--scale N] [--car-model auto|ioniq5|ev6|ioniq6]
#
#   <homepage_full.html>  path to the firmware's main/homepage_full.html
#   <tab-id>              HTML id of the tab to show (e.g. buttons_tab, status_view)
#   <out.png>             output file
#   --width/--height      optional viewport size, in CSS px (default 900x1200)
#   --scale               device pixel ratio for the PNG (default 2). The CSS
#                         layout is unchanged, so the PNG comes out SCALE times
#                         larger in each dimension; this is what keeps the small
#                         UI text sharp once the figure is printed large.
#                         Note the figure's *printed* size is set by the
#                         \includegraphics height/width in the manual, not here.
#   --car-model           value for the "Select Vehicle" dropdown (default: auto,
#                         the device default, which filters nothing by car)
#
# Browser: found automatically, in this order — google-chrome,
# google-chrome-stable, chromium, chromium-browser, chromium-headless-shell.
# Override with WICAN_UI_CHROME=/path/to/binary. Full Chrome/Chromium builds are
# driven with --headless=new; the *-headless-shell builds are already headless
# and ignore that flag, so it is omitted for them. If the browser cannot start
# because no sandbox is usable (common in containers, where unprivileged user
# namespaces are restricted) the script probes once and then re-runs with
# --no-sandbox, printing a note, rather than disabling the sandbox everywhere.
#
# The script clones the page, shows the requested tab, adds the "active" class
# to the matching sidebar button, and sets the device defaults before rendering:
# precon_mode=once, precon_button=sw_star, precon_press=short, can_fwd_mode=mitm,
# egmp_car_model=auto, battery_temp_unit=c. It then calls the firmware's own
# updatePreconButtonVisibility() so the activation-button list is filtered the
# way a real device filters it (car-model detection, #105) instead of showing
# every option the <select> happens to contain. Use the tablink onclick text to
# find the button: the tab-id must appear inside the onclick attribute of a
# .tablinks button.
#
# The screenshot is cropped just below the "Submit Changes" button: the page
# leaves a large blank area below it, so we find the button's viewport-relative
# bottom edge (recorded into <title> via the injected script and read back with
# --dump-dom) and trim the image to that row plus a small margin. Cropping needs
# Python PIL; without it the image is left uncropped with a warning.

set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

if [ "$#" -lt 3 ]; then
    echo "usage: $0 <homepage_full.html> <tab-id> <out.png> [--width W] [--height H] [--scale N] [--car-model auto|ioniq5|ev6|ioniq6]" >&2
    exit 2
fi

SRC="$1"
TAB_ID="$2"
OUT="$3"
WIDTH=900
HEIGHT=1200
SCALE=2
CAR_MODEL=auto

shift 3
while [ "$#" -gt 0 ]; do
    case "$1" in
        --width) WIDTH="$2"; shift 2 ;;
        --height) HEIGHT="$2"; shift 2 ;;
        --scale) SCALE="$2"; shift 2 ;;
        --car-model) CAR_MODEL="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

case "$CAR_MODEL" in
    auto|ioniq5|ev6|ioniq6) ;;
    *) echo "unknown --car-model: $CAR_MODEL (expected auto|ioniq5|ev6|ioniq6)" >&2; exit 2 ;;
esac

case "$SCALE" in
    ''|*[!0-9.]*) echo "unknown --scale: $SCALE (expected a number, e.g. 2)" >&2; exit 2 ;;
esac

[ -r "$SRC" ] || die "cannot read $SRC"

# ---- browser ----
if [ -n "${WICAN_UI_CHROME:-}" ]; then
    BROWSER="$WICAN_UI_CHROME"
    [ -x "$BROWSER" ] || die "WICAN_UI_CHROME=$BROWSER is not executable"
else
    BROWSER=""
    for candidate in google-chrome google-chrome-stable chromium chromium-browser chromium-headless-shell; do
        if resolved="$(command -v "$candidate" 2>/dev/null)"; then BROWSER="$resolved"; break; fi
    done
    [ -n "$BROWSER" ] || die "no headless browser found (tried google-chrome, google-chrome-stable, chromium, chromium-browser, chromium-headless-shell); install one or set WICAN_UI_CHROME"
fi

# *-headless-shell is always headless and ignores --headless=new
HEADLESS_FLAGS=()
case "$(basename "$BROWSER")" in
    *headless-shell*) ;;
    *) HEADLESS_FLAGS=(--headless=new) ;;
esac

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# A browser that cannot start because no sandbox is usable prints "No usable
# sandbox!" and writes no PNG. Probe once, then retry with --no-sandbox.
PROBE_HTML="$TMP/probe.html"
PROBE_PNG="$TMP/probe.png"
printf '<html><body>probe</body></html>' > "$PROBE_HTML"

probe() {
    rm -f "$PROBE_PNG"
    "$BROWSER" ${HEADLESS_FLAGS[@]+"${HEADLESS_FLAGS[@]}"} ${SANDBOX_FLAGS[@]+"${SANDBOX_FLAGS[@]}"} \
        --disable-gpu --window-size=200,100 --screenshot="$PROBE_PNG" \
        "file://$PROBE_HTML" >/dev/null 2>&1 || true
    [ -s "$PROBE_PNG" ]
}

SANDBOX_FLAGS=()
if ! probe; then
    SANDBOX_FLAGS=(--no-sandbox)
    if probe; then
        echo "note: rendering with --no-sandbox (no usable browser sandbox here)" >&2
    else
        die "$BROWSER could not render even with --no-sandbox"
    fi
fi

# ---- render ----
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
  var c=document.getElementById("egmp_car_model"); if (c) c.value="$CAR_MODEL";
  var u=document.getElementById("battery_temp_unit"); if (u) u.value="c";
  // apply the firmware's own car-model filtering (#105): without this the
  // activation-button <select> shows options no real car offers, because the
  // options are hidden client-side rather than omitted from the markup
  if (typeof updatePreconButtonVisibility === "function") { updatePreconButtonVisibility(); }
  // record the bottom edge of the submit button for cropping
  var sub = document.getElementById("submit_button");
  if (sub) { document.title = "SUBMIT_BOTTOM=" + Math.round(sub.getBoundingClientRect().bottom); }
})();
</script>
EOF

"$BROWSER" ${HEADLESS_FLAGS[@]+"${HEADLESS_FLAGS[@]}"} ${SANDBOX_FLAGS[@]+"${SANDBOX_FLAGS[@]}"} \
    --disable-gpu \
    --window-size="${WIDTH},${HEIGHT}" \
    --force-device-scale-factor="$SCALE" \
    --virtual-time-budget=5000 \
    --screenshot="$OUT" \
    --hide-scrollbars \
    "file://$RENDERED" >/dev/null 2>&1 || true

[ -s "$OUT" ] || die "$BROWSER produced no image for tab '$TAB_ID' (check that the tab id exists)"

# ---- crop ----
# read back the recorded button bottom edge. --window-size MUST match the
# screenshot's: layout differs with viewport width, so a default-sized
# --dump-dom run wraps labels differently and reports a bottom edge that does
# not correspond to the image (measured 822 vs 769 for buttons_tab, 1244 vs
# 1176 for status_view).
BOTTOM="$("$BROWSER" ${HEADLESS_FLAGS[@]+"${HEADLESS_FLAGS[@]}"} ${SANDBOX_FLAGS[@]+"${SANDBOX_FLAGS[@]}"} \
    --disable-gpu \
    --window-size="${WIDTH},${HEIGHT}" \
    --force-device-scale-factor="$SCALE" \
    --virtual-time-budget=5000 \
    --dump-dom \
    "file://$RENDERED" 2>/dev/null | grep -o 'SUBMIT_BOTTOM=[0-9]*' | head -1 | cut -d= -f2)" || true

if [ -z "$BOTTOM" ]; then
    echo "warning: no SUBMIT_BOTTOM marker in the render; left the image uncropped" >&2
elif [ "$((BOTTOM + 24))" -gt "$HEIGHT" ]; then
    echo "warning: the tab is taller than the ${HEIGHT}px viewport (submit button bottom ${BOTTOM}px), so the screenshot is clipped; rerun with --height $((BOTTOM + 48))" >&2
elif ! python3 -c 'import PIL' 2>/dev/null; then
    echo "warning: python3 has no PIL; left the image uncropped (pip install pillow)" >&2
else
    # getBoundingClientRect() is in CSS px, but --force-device-scale-factor
    # multiplies the PNG, so scale the crop (and its margin) to match
    if ! python3 -c "
from PIL import Image
img = Image.open('$OUT')
h = min(int(round((int('$BOTTOM') + 24) * float('$SCALE'))), img.size[1])
img.crop((0, 0, img.size[0], h)).save('$OUT')
" 2>/dev/null; then
        echo "warning: cropping failed; left the image uncropped" >&2
    fi
fi

echo "wrote $OUT"
