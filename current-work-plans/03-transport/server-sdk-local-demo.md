# Review the integrated JavaScript SDK

The result is a reusable client underneath the existing app, not a different
graphical product. The SDK and its default-app integration were validated in the
completed W6 run. The manual browser recipe below was inspected against current
source and installed files; it has **not** been launched in this planning pass.
No server, browser, camera or GPU job was started.

The commands below target the canonical Core checkout and its in-repository
`packages/freemocap-client` package. The UI's `npm install` and `npm run dev` build
that package; running its examples without the UI needs `npm ci --ignore-scripts`
and `npm run build` in it first.
Normal editable imports resolve the configured Cam/Tracker/Forge checkouts;
this is not a frozen dependency environment. The earlier W6 acceptance evidence
came from its isolated checkout. These manual commands have not been launched
as part of this documentation update.

## 1. Start the isolated backend in its own PowerShell terminal

These commands deliberately use an explicit port. Without `--port`, this backend
entry point can terminate the process occupying its preferred port. Do not replace
this invocation with a generic `python -m freemocap` or Electron's executable picker.

```powershell
$w6Core = 'C:/Users/jonma/code-stuff/github/freemocap/project/repos/freemocap'
$w6Python = 'C:/Users/jonma/code-stuff/github/freemocap/project/repos/freemocap/.venv/Scripts/python.exe'
Set-Location $w6Core
if (Get-NetTCPConnection -State Listen -LocalPort 58117,17777 -ErrorAction SilentlyContinue) {
    throw 'A review port is occupied. Stop here; do not terminate the other process.'
}
git check-ignore .test-artifacts/w6/manual-review/data
if ($LASTEXITCODE -ne 0) { throw 'Review outputs must be ignored before creation.' }
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:FREEMOCAP_BASE_FOLDER = "$w6Core/.test-artifacts/w6/manual-review/data"
$env:SKELLYLOGS_LOG_DIR = "$w6Core/.test-artifacts/w6/manual-review/logs"
New-Item -ItemType Directory -Force $env:FREEMOCAP_BASE_FOLDER,$env:SKELLYLOGS_LOG_DIR | Out-Null
& $w6Python -B -m freemocap --port 58117
```

Wait for successful startup on 58117. A failed bind is a stop condition, not a
reason to connect to some other process at that address. These environment changes
are confined to this terminal. Keep the terminal open; use Ctrl+C for shutdown.
Starting the server does not start camera capture.

## 2. Run the SDK without a graphical client

In a second terminal:

```powershell
Set-Location 'C:/Users/jonma/code-stuff/github/freemocap/project/repos/freemocap/packages/freemocap-client'
node examples/inspect-server.mjs http://127.0.0.1:58117
node examples/stream.mjs http://127.0.0.1:58117 5
node examples/recording.mjs http://127.0.0.1:58117 freemocap_test_data C:/tmp/fmc-4lokv7vn/p/freemocap_test_data/current/recordings
```

Expect server inspection, a connection report, and decoded reference recording
channel summaries. An idle server has no live motion frames; zero frames there
does not mean decoding failed. The reference Parquet path exists on this machine.
The recording example reads it without processing or exporting it. The separate
`export.mjs` example writes server output and is intentionally not part of this
read-only reference review.

## 3. Open the SDK-backed app in an isolated browser session

Use the existing UI build. This avoids the normal Vite configuration's Electron
startup and `dist-electron` cleanup. In the second terminal, prepare a separate
ignored HTML entry that sets the target before any app module executes:

```powershell
$w6Core = 'C:/Users/jonma/code-stuff/github/freemocap/project/repos/freemocap'
$w6Python = 'C:/Users/jonma/code-stuff/github/freemocap/project/repos/freemocap/.venv/Scripts/python.exe'
Set-Location $w6Core
if (Get-NetTCPConnection -State Listen -LocalPort 17777 -ErrorAction SilentlyContinue) {
    throw 'The browser review port is occupied. Stop here.'
}
git check-ignore freemocap-ui/dist/w6-review.html
if ($LASTEXITCODE -ne 0) { throw 'Review HTML must be ignored before creation.' }
$w6Settings = @'
<head><script>
localStorage.setItem('freemocap:serverHost', JSON.stringify('127.0.0.1'));
localStorage.setItem('freemocap:serverPort', '58117');
localStorage.setItem('freemocap:autoLaunchServer', 'false');
localStorage.setItem('freemocap:autoConnectWs', 'true');
</script>
'@
$w6Html = Get-Content -Raw freemocap-ui/dist/index.html
if (-not $w6Html.Contains('<head>')) { throw 'Unexpected UI entry; stop and inspect.' }
$w6Html.Replace('<head>', $w6Settings) | Set-Content -Encoding utf8 freemocap-ui/dist/w6-review.html
& $w6Python -B -m http.server 17777 --bind 127.0.0.1 --directory "$w6Core/freemocap-ui/dist"
```

Open a **new private/InPrivate browser session** to
`http://127.0.0.1:17777/w6-review.html`. Do not open `/index.html` first: its default
target is localhost:53117. The review entry writes only the four named keys in
this isolated browser origin/session; it does not clear storage or modify the
canonical app's browser/Electron profile. No installer or dependency refresh is needed.

The familiar app should appear. Expand the server connection panel and verify
host `127.0.0.1`, port `58117`, and connected status. Disconnect/reconnect and
confirm that it reconnects to the same target. The camera/scene panes remain idle
until capture is explicitly requested. Reserve a camera/GPU slot through the
coordinator before testing camera controls. Do not use shutdown controls for an
unverified server address.

Browser mode lacks Electron's native file dialogs and automatic backend launching;
the recording-folder picker is disabled there. Use the SDK recording example above
for this immediate reference-data check. A fully packaged desktop launch and a
new visible live demo are not claimed by this browser recipe. Existing W6 live
validation evidence is recorded separately in `server-sdk-handoff.md`.

Close the private browser window and Ctrl+C the static-server terminal, then the
backend terminal. Check that these two processes exited. Do not stop unrelated
processes. No automatic camera capture, export, or processing is part of this recipe.
