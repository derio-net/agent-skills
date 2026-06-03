---
name: browser-screenshot
description: Capture a PNG screenshot of any web page or web app by driving a real browser via browser-harness. Use whenever the user wants to screenshot, capture, or grab an image of a URL, web page, dashboard, or web UI — including auth-walled apps like Grafana, ArgoCD, Longhorn, or Authentik that need a real logged-in session. Use this even when the user says "take a picture of the page", "snapshot this site", "grab the dashboard", or "screenshot the Grafana panel" without naming a tool. Handles viewport, full-page, and element-cropped captures, dark mode, and host-aware login. Decoupled from any blog or doc system, but pairs with media skills that need screenshot assets.
---

# Browser Screenshot

Drive a real browser (whatever `browser-harness` is wired to on this host) to
capture a PNG of a URL. This skill is deliberately generic — it knows nothing
about blogs, docs, or placeholders. It produces a file at a path you choose.
Higher-level skills (e.g. `media-screenshots`) call it to fill their own needs.

**Announce at start:** "Using browser-screenshot to capture `<url>`."

## Why a real browser (and not headless wget / a fresh Chromium)

The point is to capture pages exactly as a human sees them — including web apps
behind a login and pages whose layout depends on real CSS/JS. `browser-harness`
attaches to a real browser over CDP; the *environment* decides which browser, so
this skill stays decoupled:

- **On a desktop**: browser-harness attaches to the locally running
  CDP-enabled browser (often a dedicated automation profile).
- **On a secure-pod / headless host**: it uses the remote/headless browser
  configured there.

You only ever call `browser-harness` — never hard-code a browser or CDP port here.

## The capture script

All four capture modes, dark mode, and login are bundled in
`scripts/capture.py`. It is **fed to `browser-harness` over stdin** (browser-
harness reads stdin and `exec()`s it with its helpers + `os.environ` in scope),
so parameters arrive as env vars, not argv:

```bash
SHOT_URL="https://example.com" \
SHOT_OUT="/tmp/shot.png" \
SHOT_MODE="viewport" SHOT_WIDTH=1200 SHOT_DARK=1 \
  browser-harness < ~/.agents/skills/browser-screenshot/scripts/capture.py
```

Read the docstring at the top of `scripts/capture.py` for the full parameter
list. The common ones:

| Param | Meaning | Default |
|-------|---------|---------|
| `SHOT_URL` | page to capture (required) | — |
| `SHOT_OUT` | output PNG path (required) | — |
| `SHOT_MODE` | `viewport` \| `full` \| `element` | `viewport` |
| `SHOT_SELECTOR` | CSS selector (required for `element`) | — |
| `SHOT_WIDTH` | viewport CSS width | `1200` |
| `SHOT_SCALE` | deviceScaleFactor (2 = crisper, ~4× bytes) | `1` |
| `SHOT_DARK` | `1` forces `prefers-color-scheme: dark` | off |
| `SHOT_WAIT_SELECTOR` | wait until this element exists | — |
| `SHOT_MAX_DIM` | downscale longest side (viewport/full) | — |

## Workflow

### Step 1 — Bring the browser up (host-aware lifecycle)

Some hosts frame every browser-automation session with a pair of begin/end
lifecycle commands (launch the browser with CDP enabled / tear it down after).
Check the machine-level agent rules or dotfiles for such a wrapper; if one
exists, run its begin command now — and its end command in Step 4.

On hosts without a wrapper, skip this — browser-harness brings up whatever it
is configured for. **Security note:** a CDP-enabled desktop browser exposes
*every* open profile (including the operator's personal one) to any local
process. If a lifecycle wrapper exists, always pair the begin with the end.

### Step 2 — Decide the mode

| Want | Mode | Notes |
|------|------|-------|
| The page as it fits in a window | `viewport` | Set `SHOT_WIDTH` (≈1200 for blog assets). |
| Everything top-to-bottom | `full` | Scroll-stitched; larger/slower. |
| Just one panel/card/region | `element` | Pass a stable `SHOT_SELECTOR`. |

Add `SHOT_DARK=1` when the convention prefers dark (most dashboards, and the
Frank/blog-craft screenshot style). Prefer `SHOT_WAIT_SELECTOR` over a blind
sleep when a known element marks "the data has rendered" (e.g. a Grafana panel's
`.panel-content`), so you don't capture a spinner.

### Step 3 — Capture (and authenticate if needed)

Run the script with the env vars for your mode (see the example above).

**Auth-walled targets.** If the page shows a login form and you supplied no login
config, the script prints `AUTH_WALL` and exits `3` — it never guesses
credentials. To log in, the credentials must already exist in the host
environment (Mac: a sourced `.env`; secure-pod: injected by s6, readable from
`/proc/1/environ`). You pass the **names** of the env vars, not the secrets:

```bash
SHOT_URL="https://grafana.internal.example/d/abc" \
SHOT_OUT="/tmp/grafana.png" SHOT_DARK=1 \
SHOT_LOGIN_URL="https://grafana.internal.example/login" \
SHOT_USER_SEL="input[name=user]" SHOT_PASS_SEL="input[name=password]" \
SHOT_SUBMIT_SEL="button[type=submit]" \
SHOT_USER_ENVVAR="GRAFANA_ADMIN_USER" SHOT_PASS_ENVVAR="GRAFANA_ADMIN_PASSWORD" \
  browser-harness < ~/.agents/skills/browser-screenshot/scripts/capture.py
```

The script resolves each credential from `os.environ` first, then
`/proc/1/environ` (the secure-pod fallback), and never echoes it. SSO redirect
flows that can't be driven by a simple username/password form are out of scope
for v1 — stop and tell the user which target needs a richer recipe.

If credentials aren't already in the environment, **do not** ask the user to
paste them into the chat or read them off a screenshot. Tell them which env var
to populate (e.g. "source the `.env` that defines `$GRAFANA_ADMIN_PASSWORD`").

### Step 4 — Verify and tear down

```bash
file "$SHOT_OUT"                 # expect: PNG image data
wc -c < "$SHOT_OUT"             # blog budget is 500KB; warn above
# then run your host's lifecycle END command, if it has one (see Step 1)
```

The script already calls `close_tab()` on the tab it opened, so the browser's
session-restore won't resurrect it. If you opened extra tabs by hand, close
those too.

## Notes & gotchas

- **Device pixels.** Screenshots are written in *device* pixels — on a 2×
  display, `SHOT_SCALE=2` quadruples the byte count. For blog assets,
  `SHOT_SCALE=1` usually keeps you under the 500KB budget; bump to 2 only when
  a panel's text is too soft.
- **Optimization isn't this skill's job.** It produces a faithful PNG. Callers
  that care about byte budgets run `pngquant`/`optipng` afterward.
- **`SHOT_MAX_DIM`** is for keeping an image small enough to hand back into the
  conversation (some models reject images > ~2000px/side) — it applies to
  `viewport`/`full`, not `element` clips.
- **Element mode** uses CDP `Page.captureScreenshot` with a clip computed from
  the selector's bounding box, so it can capture a region taller than the
  viewport without scroll-stitching.
- **Never type credentials read from a screenshot or from chat.** Credentials
  come from the host environment by name, or the run stops.
