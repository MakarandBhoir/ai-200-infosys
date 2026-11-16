"""AI-200 Day 1 demo app: runs in a container, stored in ACR, hosted on App Service.

Open "/" for a dashboard. Every card calls one endpoint and shows the result live:
  /health        used by the App Service health check
  /info          port, version, instance and selected app settings
  /secret-check  shows whether a secret reached the app (never prints the value)
  /counter       writes to /home so you can test persistent storage
  /slow          slow response, to show timeouts and logs
  /crash         logs an error and returns 500, to practise troubleshooting
"""
import logging
import os
import socket
import sys
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("day1")

VERSION = os.getenv("APP_VERSION", "1.0.0")
GIT_SHA = os.getenv("GIT_SHA", "local")
DATA_DIR = os.getenv("DATA_DIR", "/home/data")
STARTED = datetime.now(timezone.utc)

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-200 Day 1 Demo</title>
<style>
  :root { --blue:#0078d4; --dark:#0b2a4a; --bg:#f3f6fa; --card:#fff; --text:#1b2733;
          --muted:#5b6b7b; --ok:#107c10; --bad:#c50f1f; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font-family:"Segoe UI Light","Segoe UI",system-ui,-apple-system,Arial,sans-serif; }
  header { background:linear-gradient(135deg,var(--dark),var(--blue)); color:#fff; padding:36px 24px 56px; }
  .wrap { max-width:1000px; margin:0 auto; }
  header h1 { margin:0 0 6px; font-size:32px; font-weight:300; }
  header p { margin:0; opacity:.85; font-size:16px; }
  .chips { margin-top:18px; display:flex; flex-wrap:wrap; gap:10px; }
  .chip { background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.3);
          border-radius:20px; padding:6px 14px; font-size:14px; }
  .chip b { font-weight:600; }
  main { max-width:1000px; margin:-32px auto 40px; padding:0 24px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(290px,1fr)); gap:18px; }
  .card { background:var(--card); border-radius:10px; padding:20px;
          box-shadow:0 2px 10px rgba(11,42,74,.10); display:flex; flex-direction:column; }
  .card h2 { margin:0 0 4px; font-size:19px; font-weight:600; }
  .card .path { color:var(--blue); font-family:Consolas,Menlo,monospace; font-size:13px; }
  .card p { color:var(--muted); font-size:14px; margin:10px 0 14px; flex:1; }
  button { background:var(--blue); color:#fff; border:0; border-radius:6px; padding:9px 16px;
           font-size:14px; cursor:pointer; font-family:inherit; }
  button:hover { background:#106ebe; }
  button.warn { background:var(--bad); }
  pre { background:#0f1b2a; color:#d6e4f0; border-radius:6px; padding:10px; margin:12px 0 0;
        font-size:12.5px; min-height:44px; max-height:160px; overflow:auto; white-space:pre-wrap; }
  .status { font-size:12px; margin-top:8px; color:var(--muted); }
  .ok { color:var(--ok); } .bad { color:var(--bad); }
  footer { text-align:center; color:var(--muted); font-size:13px; padding-bottom:30px; }
</style>
</head>
<body>
<header><div class="wrap">
  <h1>AI-200 Day 1 &middot; Containers on Azure</h1>
  <p>Image in Azure Container Registry, running on App Service for Containers</p>
  <div class="chips">
    <span class="chip">Version <b>{{ version }}</b></span>
    <span class="chip">Build <b>{{ build }}</b></span>
    <span class="chip">Host <b>{{ host }}</b></span>
    <span class="chip">Python <b>{{ py }}</b></span>
    <span class="chip">Started <b>{{ started }}</b></span>
  </div>
</div></header>

<main><div class="grid">
{% for c in cards %}
  <div class="card">
    <h2>{{ c.title }}</h2>
    <div class="path">GET {{ c.path }}</div>
    <p>{{ c.text }}</p>
    <div><button class="{{ c.cls }}" onclick="call('{{ c.path }}','{{ c.id }}')">{{ c.button }}</button></div>
    <pre id="out-{{ c.id }}">Click the button to call this endpoint.</pre>
    <div class="status" id="st-{{ c.id }}"></div>
  </div>
{% endfor %}
</div></main>
<footer>Tip: open the App Service log stream while you click, and watch each request appear.</footer>

<script>
async function call(path, id) {
  const out = document.getElementById('out-' + id);
  const st = document.getElementById('st-' + id);
  out.textContent = 'Calling...'; st.textContent = '';
  const t0 = performance.now();
  try {
    const r = await fetch(path);
    const ms = Math.round(performance.now() - t0);
    const txt = await r.text();
    try { out.textContent = JSON.stringify(JSON.parse(txt), null, 2); } catch { out.textContent = txt; }
    st.innerHTML = '<span class="' + (r.ok ? 'ok' : 'bad') + '">HTTP ' + r.status + '</span> &middot; ' + ms + ' ms';
  } catch (e) {
    out.textContent = String(e); st.innerHTML = '<span class="bad">Request failed</span>';
  }
}
</script>
</body>
</html>"""

CARDS = [
    dict(id="health", path="/health", title="Health check", button="Check health", cls="",
         text="The path App Service probes to decide if an instance is healthy."),
    dict(id="info", path="/info", title="App info", button="Show info", cls="",
         text="Version, build, host and the non-secret settings this container received."),
    dict(id="secret", path="/secret-check", title="Secret check", button="Check secret", cls="",
         text="Did API_KEY arrive from Key Vault? Shows true or false, never the value."),
    dict(id="counter", path="/counter", title="Persistent storage", button="Increment counter", cls="",
         text="Writes a counter under /home. Restart the app and see if the number survives."),
    dict(id="slow", path="/slow?seconds=3", title="Slow request", button="Wait 3 seconds", cls="",
         text="Sleeps for a few seconds. Useful to see timing in the logs."),
    dict(id="crash", path="/crash", title="Simulate a failure", button="Trigger error", cls="warn",
         text="Logs an error and returns HTTP 500. Practise finding it with az webapp log tail."),
]


@app.get("/")
def index():
    log.info("dashboard requested")
    return render_template_string(
        PAGE, version=VERSION, build=GIT_SHA, host=socket.gethostname(),
        py=sys.version.split()[0], cards=CARDS,
        started=STARTED.strftime("%Y-%m-%d %H:%M UTC"))


@app.get("/health")
def health():
    return jsonify(status="healthy", time=datetime.now(timezone.utc).isoformat())


@app.get("/info")
def info():
    # Only non-secret settings are shown.
    keys = ["APP_ENV", "WEBSITES_PORT", "PORT", "WEBSITE_SITE_NAME",
            "WEBSITE_INSTANCE_ID", "WEBSITE_SLOT_NAME"]
    return jsonify(
        version=VERSION,
        build=GIT_SHA,
        hostname=socket.gethostname(),
        python=sys.version.split()[0],
        settings={k: os.getenv(k) for k in keys if os.getenv(k) is not None},
    )


@app.get("/secret-check")
def secret_check():
    value = os.getenv("API_KEY")
    configured = value is not None and value != ""
    # A Key Vault reference that failed to resolve stays as the literal text.
    unresolved = bool(value) and value.startswith("@Microsoft.KeyVault")
    log.info("secret check: configured=%s unresolved=%s", configured, unresolved)
    return jsonify(api_key_configured=configured,
                   key_vault_reference_unresolved=unresolved,
                   length=len(value) if configured and not unresolved else 0)


@app.get("/counter")
def counter():
    """Increment a counter stored under /home (persistent when storage is enabled)."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        path = os.path.join(DATA_DIR, "counter.txt")
        n = int(open(path).read()) + 1 if os.path.exists(path) else 1
        with open(path, "w") as f:
            f.write(str(n))
        return jsonify(count=n, path=path)
    except OSError as exc:
        log.error("storage error: %s", exc)
        return jsonify(error=str(exc),
                       hint="Set DATA_DIR to a writable folder, e.g. ./data"), 500


@app.get("/slow")
def slow():
    seconds = min(float(request.args.get("seconds", 5)), 60)
    log.info("sleeping %.1f seconds", seconds)
    time.sleep(seconds)
    return jsonify(slept=seconds)


@app.get("/crash")
def crash():
    log.error("simulated failure requested on /crash")
    return jsonify(error="simulated failure"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))