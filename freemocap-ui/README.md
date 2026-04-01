# FreeMoCap UI

React/Electron desktop interface for FreeMoCap — live multi-camera streaming, recording, and synchronized playback.

Built with **React 19**, **TypeScript**, **Material UI**, **Redux Toolkit**, and packaged as an **Electron** desktop app via [electron-vite](https://github.com/electron-vite/electron-vite-react).

---

## Quick Start

```bash
npm install
npm run dev        # Vite dev server + Electron
```

The UI expects the FreeMoCap Python server running on `localhost:53117` (default). Start the server first:

```bash
# From the repo root
python -m freemocap
```

---

## Pages

### Cameras (`/cameras`)

Live multi-camera view with real-time WebSocket streaming. Configure camera resolution, framerate, exposure, and rotation. Start/stop recordings from here.

### Playback (`/playback`)

Browse and play back recorded sessions with frame-perfect multi-camera synchronization.

**Recording Browser** — lists all recordings from `~/freemocap_data/recordings/`, sorted newest-first. Each entry shows:

- Number of camera streams
- Total recording size on disk
- Recording duration and frame count (read from timestamp CSVs)
- Effective FPS
- Relative time ("2h ago", "3d ago")

You can also type or paste a custom folder path to load any recording.

**Synced Video Player** — opens all camera streams in a responsive grid. Key features:

- **Frame-locked synchronization** — every camera displays the exact same frame number at all times, driven by a single authoritative counter
- **Per-camera overlays** — frame number (top-right, green), camera ID (bottom-left), SMPTE timecode (bottom-right)
- **Smooth native playback** — uses `HTMLVideoElement.play()` for hardware-decoded rendering, with a rAF drift-correction loop for sync
- **Frame stepping** — ←/→ keys step 1 frame, Shift+←/→ step 10 frames
- **Variable speed** — 0.1× through 8× with frame-lock maintained at all rates
- **Keyboard shortcuts** — Space (play/pause), Home/End (jump to start/end)

---

## Project Structure

```
src/
├── pages/
│   ├── CamerasPage.tsx          # Live camera view
│   ├── PlaybackPage.tsx         # Recording browser → synced player
│   └── WelcomePage.tsx          # Landing / home
│
├── components/
│   ├── playback/
│   │   ├── SyncedVideoPlayer.tsx   # Core frame-locked multi-video player
│   │   ├── PlaybackControls.tsx    # Transport bar (play, seek, step, speed)
│   │   ├── RecordingBrowser.tsx    # Recording list with metadata + manual path
│   │   └── index.ts               # Barrel exports
│   │
│   ├── camera-views/            # CameraView, CameraViewsGrid
│   ├── camera-config-panel/     # Resolution, framerate, exposure controls
│   ├── camera-config-tree-view/ # Sidebar camera tree
│   ├── camera-view-settings-overlay/  # Image scale slider
│   ├── framerate-viewer/        # Real-time FPS D3 charts
│   ├── recording-info-panel/    # Recording path, start/stop, settings
│   ├── video-folder-panel/      # Legacy folder picker (Electron IPC)
│   ├── ui-components/           # Header, Footer, LeftPanel, ThemeToggle
│   └── common/                  # ErrorBoundary
│
├── services/
│   ├── server/
│   │   ├── ServerContextProvider.tsx   # WebSocket lifecycle
│   │   └── server-helpers/
│   │       ├── server-urls.ts          # API endpoint URLs
│   │       ├── websocket-connection.ts # WebSocket manager
│   │       ├── canvas-manager.ts       # Canvas rendering
│   │       └── frame-processor/        # Binary frame parsing
│   └── electron-ipc/                   # Electron main ↔ renderer IPC
│
├── store/
│   ├── store.ts                 # Redux store configuration
│   ├── hooks.ts                 # useAppDispatch, useAppSelector
│   └── slices/
│       ├── cameras/             # Camera state, detection, config
│       ├── recording/           # Recording state, start/stop thunks
│       ├── videos/              # Video file state, folder selection
│       ├── framerate/           # FPS tracking data
│       ├── log-records/         # Server log entries
│       └── theme/               # Light/dark mode
│
└── layout/
    ├── AppContent.tsx           # Top-level app wrapper
    ├── BaseContentRouter.tsx    # React Router routes
    └── BasePanelLayout.tsx      # Resizable panel layout (react-resizable-panels)
```

---

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `react` / `react-dom` | UI framework |
| `@mui/material` | Component library |
| `@reduxjs/toolkit` / `react-redux` | State management |
| `react-router-dom` | Client-side routing |
| `react-resizable-panels` | Draggable panel layout |
| `d3` | Framerate charts |
| `electron` | Desktop packaging |
| `vite` | Build tool and dev server |

---

## Build

```bash
npm run build          # Production build (renderer + electron)
npm run build:unpack   # Build unpacked app for testing
```

See `electron-builder.json` for packaging configuration.

---

## Server Communication

The UI talks to the Python server over two channels:

**HTTP REST** — camera control, recording management, and playback. Base URL defaults to `http://localhost:53117`. Key playback endpoints:

- `GET /freemocap/playback/recordings` — list all recordings with metadata (size, frames, duration, fps)
- `POST /freemocap/playback/load` — load a recording folder
- `GET /freemocap/playback/video/{video_id}` — stream a video file (supports HTTP range requests for seeking)
- `GET /freemocap/playback/timestamps/{video_id}` — get timestamp CSV info

**WebSocket** — real-time binary frame streaming at `ws://localhost:53117/freemocap/websocket/connect`. Delivers synchronized multi-frame payloads (one JPEG per camera per frame event) plus JSON log messages.

---

## Playback Sync Architecture

The `SyncedVideoPlayer` component guarantees frame-perfect synchronization across all camera views:

1. **Native playback** — all `<video>` elements use `.play()` for smooth hardware decoding
2. **Authoritative counter** — a `requestAnimationFrame` loop computes the current frame from `wall-clock elapsed × fps × playbackRate`
3. **Drift correction** — every ~3 ticks, each video's `.currentTime` is compared against the target; videos drifting >0.5 frames are force-seeked back
4. **Single source of truth** — the frame number overlay on every camera comes from the authoritative counter, never from individual video elements
5. **Pause/step** — sets `.currentTime` directly on all elements (no `.play()` involved)

This hybrid approach delivers smooth rendering while maintaining the hard sync guarantee.
