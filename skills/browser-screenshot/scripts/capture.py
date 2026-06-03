#!/usr/bin/env python3
"""capture.py — fed to `browser-harness` over stdin, NOT run standalone.

    SHOT_URL=... SHOT_OUT=... [opts] browser-harness < capture.py

browser-harness execs this with its helpers (new_tab, wait_for_load, js, cdp,
capture_screenshot, close_tab, ...) already imported into globals, and with the
current process environment visible via os.environ. That is why every parameter
arrives as an env var rather than argv: there is no argv inside the exec context.

It bundles the CDP incantations for the four capture modes + a host-aware
credential resolver + a pluggable form-login, so callers never re-derive them.

Parameters (env vars)
  SHOT_URL          (required) page to capture
  SHOT_OUT          (required) output PNG path
  SHOT_MODE         viewport | full | element        (default: viewport)
  SHOT_SELECTOR     CSS selector            (required when SHOT_MODE=element)
  SHOT_WIDTH        viewport CSS width px               (default: 1200)
  SHOT_HEIGHT       viewport CSS height px              (default: 900)
  SHOT_SCALE        deviceScaleFactor 1|2               (default: 1)
  SHOT_DARK         "1" forces prefers-color-scheme: dark before load
  SHOT_WAIT_MS      extra settle wait after load, ms    (default: 400)
  SHOT_WAIT_SELECTOR  wait until this selector exists before capturing
  SHOT_MAX_DIM      downscale longest side to this many px (viewport/full)
  SHOT_AUTH_OK      "1" = a login form is acceptable content (e.g. the shot
                    IS the login page); skips the AUTH_WALL bail-out

Login (all optional; supply together to auto-fill a form before capturing)
  SHOT_LOGIN_URL    navigate here first and log in
  SHOT_USER_SEL     CSS selector for the username field
  SHOT_PASS_SEL     CSS selector for the password field
  SHOT_SUBMIT_SEL   CSS selector for the submit button
  SHOT_USER_ENVVAR  name of the env var holding the username
  SHOT_PASS_ENVVAR  name of the env var holding the password

Exit codes
  0  screenshot written
  2  bad/missing parameters
  3  AUTH_WALL — a login form was detected and no login config was supplied
"""
import base64
import json
import os
import sys
import time


def fail(msg, code=2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


URL = os.environ.get("SHOT_URL")
OUT = os.environ.get("SHOT_OUT")
if not URL or not OUT:
    fail("SHOT_URL and SHOT_OUT are required")

MODE = os.environ.get("SHOT_MODE", "viewport")
SELECTOR = os.environ.get("SHOT_SELECTOR")
WIDTH = int(os.environ.get("SHOT_WIDTH", "1200"))
HEIGHT = int(os.environ.get("SHOT_HEIGHT", "900"))
SCALE = int(os.environ.get("SHOT_SCALE", "1"))
DARK = os.environ.get("SHOT_DARK") == "1"
WAIT_MS = int(os.environ.get("SHOT_WAIT_MS", "400"))
WAIT_SELECTOR = os.environ.get("SHOT_WAIT_SELECTOR")
MAX_DIM = os.environ.get("SHOT_MAX_DIM")

if MODE not in ("viewport", "full", "element"):
    fail(f"SHOT_MODE must be viewport|full|element, got {MODE!r}")
if MODE == "element" and not SELECTOR:
    fail("SHOT_MODE=element requires SHOT_SELECTOR")


def resolve_cred(envvar):
    """Host-aware credential lookup. Mac: env (sourced from .env). Secure-pod:
    sshd/exec may scrub the env, so fall back to PID 1's environ where s6 put it.
    Returns the value or None; never prints it."""
    v = os.environ.get(envvar)
    if v:
        return v
    try:
        with open("/proc/1/environ", "rb") as f:
            for kv in f.read().split(b"\0"):
                if kv.startswith(envvar.encode() + b"="):
                    return kv.split(b"=", 1)[1].decode()
    except OSError:
        pass
    return None


def apply_emulation():
    # browser-harness's cdp() takes CDP params as kwargs, NOT a positional dict
    # (cdp(method, session_id=None, **params)) — a dict 2nd arg binds to
    # session_id and the wire rejects it.
    cdp("Emulation.setDeviceMetricsOverride",
        width=WIDTH, height=HEIGHT, deviceScaleFactor=SCALE, mobile=False)
    if DARK:
        cdp("Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "dark"}])


def has_password_field():
    return bool(js("!!document.querySelector('input[type=password]')"))


def do_login():
    login_url = os.environ.get("SHOT_LOGIN_URL")
    if not login_url:
        return False
    user_sel = os.environ.get("SHOT_USER_SEL")
    pass_sel = os.environ.get("SHOT_PASS_SEL")
    submit_sel = os.environ.get("SHOT_SUBMIT_SEL")
    user_var = os.environ.get("SHOT_USER_ENVVAR")
    pass_var = os.environ.get("SHOT_PASS_ENVVAR")
    if not all([user_sel, pass_sel, submit_sel, user_var, pass_var]):
        fail("SHOT_LOGIN_URL set but a SHOT_USER_SEL/PASS_SEL/SUBMIT_SEL/"
             "USER_ENVVAR/PASS_ENVVAR is missing")
    user = resolve_cred(user_var)
    pwd = resolve_cred(pass_var)
    if not user or not pwd:
        fail(f"credential not found in env (looked for ${user_var} / ${pass_var} "
             f"in os.environ and /proc/1/environ)")
    new_tab(login_url)
    wait_for_load()
    # Set values via the DOM and fire input events so reactive forms register
    # them. The secret rides inside this Runtime.evaluate expression — acceptable
    # for local automation; we never echo it ourselves.
    js("(function(u,p){"
       f"var U=document.querySelector({json.dumps(user_sel)});"
       f"var P=document.querySelector({json.dumps(pass_sel)});"
       "if(U){U.value=u;U.dispatchEvent(new Event('input',{bubbles:true}));}"
       "if(P){P.value=p;P.dispatchEvent(new Event('input',{bubbles:true}));}"
       f"}})({json.dumps(user)},{json.dumps(pwd)})")
    js(f"document.querySelector({json.dumps(submit_sel)}).click()")
    wait_for_load()
    print("logged in via form", file=sys.stderr)
    return True


def capture_element(out):
    rect = js("(function(){"
              f"var e=document.querySelector({json.dumps(SELECTOR)});"
              "if(!e)return null;e.scrollIntoView();"
              "var r=e.getBoundingClientRect();"
              "return {x:r.x+window.scrollX,y:r.y+window.scrollY,"
              "width:r.width,height:r.height};})()")
    if not rect:
        fail(f"selector not found: {SELECTOR}")
    res = cdp("Page.captureScreenshot",
              format="png", captureBeyondViewport=True,
              clip={"x": rect["x"], "y": rect["y"],
                    "width": rect["width"], "height": rect["height"], "scale": 1})
    with open(out, "wb") as f:
        f.write(base64.b64decode(res["data"]))


# --- drive the browser ---------------------------------------------------
# Open the tab, apply width/theme, then reload so the page lays out at the
# emulated width and reads the dark media query at load time.
new_tab(URL)
wait_for_load()
apply_emulation()
cdp("Page.reload")
wait_for_load()

if WAIT_SELECTOR:
    for _ in range(50):  # up to ~5s
        if js(f"!!document.querySelector({json.dumps(WAIT_SELECTOR)})"):
            break
        time.sleep(0.1)
if WAIT_MS:
    time.sleep(WAIT_MS / 1000.0)

# Auth handling: log in if configured, else stop loudly on a login wall so the
# caller can decide — never guess credentials. SHOT_AUTH_OK=1 means the login
# page itself is the intended subject, so don't treat it as a wall.
if os.environ.get("SHOT_AUTH_OK") != "1" and has_password_field():
    if not do_login():
        print("AUTH_WALL: a login form was detected and no SHOT_LOGIN_* config "
              "was supplied. Provide login selectors + credential env-var names, "
              "or target a page that does not require auth.", file=sys.stderr)
        try:
            close_tab()
        except Exception:
            pass
        sys.exit(3)
    # back to the real target after logging in
    new_tab(URL)
    wait_for_load()
    apply_emulation()
    cdp("Page.reload")
    wait_for_load()
    if WAIT_MS:
        time.sleep(WAIT_MS / 1000.0)

kwargs = {}
if MAX_DIM:
    kwargs["max_dim"] = int(MAX_DIM)

if MODE == "viewport":
    capture_screenshot(OUT, **kwargs)
elif MODE == "full":
    capture_screenshot(OUT, full=True, **kwargs)
else:  # element
    capture_element(OUT)

try:
    close_tab()
except Exception:
    pass

# --- report --------------------------------------------------------------
size = os.path.getsize(OUT)
print(f"wrote {OUT} ({size} bytes, mode={MODE}, width={WIDTH}, "
      f"scale={SCALE}, dark={int(DARK)})")
if size > 512000:
    print(f"WARN: {size} bytes is over the 500KB blog budget — optimize "
          f"(pngquant/optipng) or lower SHOT_SCALE.", file=sys.stderr)
