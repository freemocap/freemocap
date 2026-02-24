"""
Debug endpoint: serves an HTML page that displays raw settings JSON
from both the HTTP GET /settings endpoint and the WebSocket settings/state
push, side by side, for visual confirmation of backend/frontend sync.

Access at: /debug/settings-sync
"""
import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

debug_router = APIRouter(prefix="/debug", tags=["Debug"])

_DEBUG_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>FreeMoCap Settings Sync Debug</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=DM+Sans:wght@400;500;700&display=swap');

    * { margin: 0; padding: 0; box-sizing: border-box; }

    :root {
      --bg: #0d1117;
      --surface: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-dim: #8b949e;
      --green: #3fb950;
      --red: #f85149;
      --yellow: #d29922;
      --blue: #58a6ff;
      --orange: #d18616;
      --mono: 'JetBrains Mono', monospace;
      --sans: 'DM Sans', sans-serif;
    }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans);
      padding: 24px;
      min-height: 100vh;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }

    h1 {
      font-family: var(--mono);
      font-size: 18px;
      font-weight: 700;
      color: #f0f6fc;
      letter-spacing: -0.5px;
    }

    h1 span { color: var(--blue); }

    .controls {
      display: flex;
      gap: 12px;
      align-items: center;
    }

    label {
      font-family: var(--mono);
      font-size: 12px;
      color: var(--text-dim);
    }

    input[type="number"] {
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text);
      font-family: var(--mono);
      font-size: 13px;
      padding: 6px 10px;
      border-radius: 6px;
      width: 80px;
    }

    button {
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text);
      font-family: var(--mono);
      font-size: 12px;
      padding: 6px 14px;
      border-radius: 6px;
      cursor: pointer;
      transition: border-color 0.15s;
    }

    button:hover { border-color: var(--blue); color: var(--blue); }

    .status-bar {
      display: flex;
      gap: 24px;
      margin-bottom: 16px;
      font-family: var(--mono);
      font-size: 12px;
    }

    .status-item {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--text-dim);
    }

    .dot.connected { background: var(--green); box-shadow: 0 0 6px var(--green); }
    .dot.error { background: var(--red); box-shadow: 0 0 6px var(--red); }

    .sync-verdict {
      margin-left: auto;
      padding: 4px 12px;
      border-radius: 4px;
      font-weight: 600;
      font-size: 13px;
    }

    .sync-verdict.synced { background: rgba(63,185,80,0.15); color: var(--green); }
    .sync-verdict.desynced { background: rgba(248,81,73,0.15); color: var(--red); }
    .sync-verdict.pending { background: rgba(210,153,34,0.15); color: var(--yellow); }

    .panels {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }

    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .panel-header {
      padding: 10px 16px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-family: var(--mono);
      font-size: 13px;
      font-weight: 600;
    }

    .panel-header .source { color: var(--blue); }
    .panel-header .meta { color: var(--text-dim); font-weight: 400; font-size: 11px; }

    .panel-body {
      padding: 12px 16px;
      overflow: auto;
      max-height: calc(100vh - 200px);
    }

    pre {
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
      color: var(--text);
    }

    pre .key { color: var(--blue); }
    pre .string { color: #a5d6ff; }
    pre .number { color: #79c0ff; }
    pre .boolean { color: var(--orange); }
    pre .null { color: var(--text-dim); }

    .empty-state {
      color: var(--text-dim);
      font-family: var(--mono);
      font-size: 13px;
      padding: 40px 0;
      text-align: center;
    }

    .diff-summary {
      margin-top: 16px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 16px;
    }

    .diff-summary h3 {
      font-family: var(--mono);
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 8px;
      color: var(--text-dim);
    }

    .diff-entry {
      font-family: var(--mono);
      font-size: 12px;
      padding: 4px 0;
      border-bottom: 1px solid var(--border);
    }

    .diff-entry:last-child { border-bottom: none; }
    .diff-path { color: var(--yellow); }
    .diff-val-http { color: var(--red); }
    .diff-val-ws { color: var(--green); }
  </style>
</head>
<body>

<header>
  <h1>💀 FreeMoCap <span>Settings Sync Debug</span></h1>
  <div class="controls">
    <label>Poll (ms)
      <input type="number" id="poll-interval" value="2000" />
    </label>
    <button id="btn-connect">Connect</button>
    <button id="btn-disconnect" style="display:none;">Disconnect</button>
    <button id="btn-fetch-once">Fetch HTTP Once</button>
  </div>
</header>

<div class="status-bar">
  <div class="status-item">
    <div class="dot" id="dot-ws"></div>
    <span>WebSocket: <span id="ws-status">disconnected</span></span>
  </div>
  <div class="status-item">
    <div class="dot" id="dot-http"></div>
    <span>HTTP: <span id="http-status">idle</span></span>
  </div>
  <div class="status-item">
    <div class="dot" id="dot-http-version"></div>
    <span>HTTP v<span id="http-version">—</span></span>
  </div>
  <div class="status-item">
    <div class="dot" id="dot-ws-version"></div>
    <span>WS v<span id="ws-version">—</span></span>
  </div>
  <div class="sync-verdict pending" id="sync-verdict">waiting for data</div>
</div>

<div class="panels">
  <div class="panel">
    <div class="panel-header">
      <span><span class="source">GET /settings</span> — Backend (HTTP)</span>
      <span class="meta" id="http-timestamp">—</span>
    </div>
    <div class="panel-body">
      <pre id="http-json"><div class="empty-state">Click "Connect" or "Fetch HTTP Once"</div></pre>
    </div>
  </div>
  <div class="panel">
    <div class="panel-header">
      <span><span class="source">ws://…/websocket/connect</span> — Frontend (WebSocket)</span>
      <span class="meta" id="ws-timestamp">—</span>
    </div>
    <div class="panel-body">
      <pre id="ws-json"><div class="empty-state">Click "Connect" to open WebSocket</div></pre>
    </div>
  </div>
</div>

<div class="diff-summary" id="diff-section" style="display:none;">
  <h3>⚠ Differences (HTTP settings ↔ WebSocket settings)</h3>
  <div id="diff-entries"></div>
</div>

<script>
  let ws = null;
  let pollTimer = null;
  let httpData = null;
  let wsData = null;

  const $ = (id) => document.getElementById(id);

  // Derive HTTP and WS base URLs from the page's own origin,
  // since this page is served by the same FastAPI app.
  const HTTP_BASE = window.location.origin;
  const WS_BASE = HTTP_BASE.replace(/^http/, 'ws');

  function highlightJson(obj) {
    const raw = JSON.stringify(obj, null, 2);
    return raw
      .replace(/("(?:[^"\\\\]|\\\\.)*")\s*:/g, (_, key) => `<span class="key">${key}</span>:`)
      .replace(/:\s*("(?:[^"\\\\]|\\\\.)*")/g, (m, v) => m.replace(v, `<span class="string">${v}</span>`))
      .replace(/:\s*(\d+\.?\d*)/g, (m, v) => m.replace(v, `<span class="number">${v}</span>`))
      .replace(/:\s*(true|false)/g, (m, v) => m.replace(v, `<span class="boolean">${v}</span>`))
      .replace(/:\s*(null)/g, (m, v) => m.replace(v, `<span class="null">${v}</span>`));
  }

  function deepDiff(a, b, path) {
    path = path || '';
    const diffs = [];
    if (a === b) return diffs;
    if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') {
      diffs.push({ path: path || '(root)', httpVal: a, wsVal: b });
      return diffs;
    }
    const allKeys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const key of allKeys) {
      const sub = path ? path + '.' + key : key;
      if (!(key in a)) {
        diffs.push({ path: sub, httpVal: undefined, wsVal: b[key] });
      } else if (!(key in b)) {
        diffs.push({ path: sub, httpVal: a[key], wsVal: undefined });
      } else {
        diffs.push(...deepDiff(a[key], b[key], sub));
      }
    }
    return diffs;
  }

  function truncVal(v) {
    const s = JSON.stringify(v);
    return s && s.length > 80 ? s.substring(0, 77) + '...' : s;
  }

  function updateSyncVerdict() {
    if (!httpData || !wsData) {
      $('sync-verdict').className = 'sync-verdict pending';
      $('sync-verdict').textContent = 'waiting for data';
      $('diff-section').style.display = 'none';
      return;
    }

    const diffs = deepDiff(httpData.settings, wsData.settings);

    if (diffs.length === 0) {
      $('sync-verdict').className = 'sync-verdict synced';
      const vDiff = (httpData.version || 0) - (wsData.version || 0);
      $('sync-verdict').textContent = '\u2713 IN SYNC' + (vDiff !== 0 ? ' (version diff: ' + vDiff + ')' : '');
      $('diff-section').style.display = 'none';
    } else {
      $('sync-verdict').className = 'sync-verdict desynced';
      $('sync-verdict').textContent = '\u2717 ' + diffs.length + ' DIFFERENCE' + (diffs.length > 1 ? 'S' : '') + ' DETECTED';
      $('diff-section').style.display = 'block';
      $('diff-entries').innerHTML = diffs.map(function(d) {
        return '<div class="diff-entry">' +
          '<span class="diff-path">' + d.path + '</span>: ' +
          '<span class="diff-val-http">HTTP=' + truncVal(d.httpVal) + '</span> \u2194 ' +
          '<span class="diff-val-ws">WS=' + truncVal(d.wsVal) + '</span>' +
          '</div>';
      }).join('');
    }
  }

  async function fetchHttp() {
    $('http-status').textContent = 'fetching\u2026';
    $('dot-http').className = 'dot';
    try {
      const resp = await fetch(HTTP_BASE + '/settings');
      if (!resp.ok) throw new Error('HTTP ' + resp.status + ': ' + resp.statusText);
      httpData = await resp.json();
      $('http-json').innerHTML = highlightJson(httpData);
      $('http-timestamp').textContent = new Date().toLocaleTimeString();
      $('http-version').textContent = httpData.version != null ? httpData.version : '\u2014';
      $('http-status').textContent = 'ok';
      $('dot-http').className = 'dot connected';
      updateSyncVerdict();
    } catch (err) {
      $('http-status').textContent = 'error: ' + err.message;
      $('dot-http').className = 'dot error';
    }
  }

  function connectWs() {
    const url = WS_BASE + '/websocket/connect';
    ws = new WebSocket(url);

    ws.onopen = function() {
      $('ws-status').textContent = 'connected';
      $('dot-ws').className = 'dot connected';
    };

    ws.onmessage = function(event) {
      if (typeof event.data !== 'string') return;
      try {
        var data = JSON.parse(event.data);
        if (data.message_type === 'settings/state') {
          wsData = data;
          $('ws-json').innerHTML = highlightJson(data);
          $('ws-timestamp').textContent = new Date().toLocaleTimeString();
          $('ws-version').textContent = data.version != null ? data.version : '\u2014';
          updateSyncVerdict();
        }
      } catch (e) {
        // Non-JSON or non-settings message — ignore
      }
    };

    ws.onclose = function(event) {
      $('ws-status').textContent = 'closed (code ' + event.code + ')';
      $('dot-ws').className = 'dot';
      ws = null;
    };

    ws.onerror = function() {
      $('ws-status').textContent = 'error';
      $('dot-ws').className = 'dot error';
    };
  }

  function disconnectAll() {
    if (ws) { ws.close(); ws = null; }
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    $('btn-connect').style.display = '';
    $('btn-disconnect').style.display = 'none';
    $('ws-status').textContent = 'disconnected';
    $('dot-ws').className = 'dot';
    $('http-status').textContent = 'idle';
    $('dot-http').className = 'dot';
  }

  $('btn-connect').addEventListener('click', function() {
    connectWs();
    fetchHttp();
    var interval = parseInt($('poll-interval').value, 10) || 2000;
    pollTimer = setInterval(fetchHttp, interval);
    $('btn-connect').style.display = 'none';
    $('btn-disconnect').style.display = '';
  });

  $('btn-disconnect').addEventListener('click', disconnectAll);
  $('btn-fetch-once').addEventListener('click', fetchHttp);
</script>

</body>
</html>"""


@debug_router.get(
    "/settings-sync",
    summary="Settings Sync Debug Page",
    tags=["Debug"],
    response_class=HTMLResponse,
)
def settings_sync_debug_page() -> HTMLResponse:
    """
    Serve the settings sync debug page.

    Displays raw JSON from both GET /settings (HTTP) and the
    WebSocket settings/state push side-by-side, with a live diff
    showing any discrepancies between the two.
    """
    return HTMLResponse(content=_DEBUG_PAGE_HTML)
