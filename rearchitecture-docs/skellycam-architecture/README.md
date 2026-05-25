# SkellyCam Rust — Documentation

## Re-architecture Playbook

The methodology we used to re-architect the Python SkellyCam backend into Rust. Use this when bringing Rust into other FreeMoCap components.

→ [rearchitecture-playbook/](./rearchitecture-playbook/)

| # | Document | Purpose |
|---|----------|---------|
| — | [README](./rearchitecture-playbook/README.md) | The 5-step methodology at a glance |
| 1 | [Understand the Problem](./rearchitecture-playbook/01-understand-the-problem.md) | How to analyze a Python component before touching Rust |
| 2 | [Extract Invariants](./rearchitecture-playbook/02-extract-invariants.md) | Separating WHAT must be achieved from HOW Python did it |
| 3 | [Separate Python Concerns](./rearchitecture-playbook/03-separate-python-concerns.md) | Identifying Python-specific baggage that doesn't apply to Rust |
| 4 | [Design Rust Architecture](./rearchitecture-playbook/04-design-rust-architecture.md) | Designing from invariants, using Rust's strengths |
| 5 | [Patterns Catalog](./rearchitecture-playbook/05-patterns-catalog.md) | Reusable Rust patterns that emerged from skellycam |

## SkellyCam: Worked Example

The output of applying the methodology to the SkellyCam camera backend. 9 documents covering every architectural component.

→ [skellycam/](./skellycam/)

| # | Document | Component |
|---|----------|-----------|
| 01 | [System Startup](./skellycam/01-system-startup.md) | Process model, lifecycle, shutdown |
| 02 | [Camera Group Manager](./skellycam/02-camera-group-manager.md) | Group lifecycle, config updates |
| 03 | [Camera Sync Gate](./skellycam/03-camera-sync-gate.md) | Multi-camera lockstep, capture loop |
| 04 | [Frame Fan-Out](./skellycam/04-frame-fanout.md) | Gatherer to frontend + recorder |
| 05 | [Recording Pipeline](./skellycam/05-recording-pipeline.md) | Video encoding, metadata, finalization |
| 06 | [Timestamp Pipeline](./skellycam/06-timestamp-pipeline.md) | Per-frame timing, performance clock |
| 07 | [HTTP API Surface](./skellycam/07-http-api-surface.md) | Endpoints, JSON shapes, error handling |
| 08 | [WebSocket Binary Protocol](./skellycam/08-websocket-binary-protocol.md) | Wire format, image processing |
| 09 | [Channel Architecture](./skellycam/09-channel-architecture.md) | Thread communication, sync primitives |

## How to Use These Docs

**If you're porting a FreeMoCap component to Rust:**
1. Read the [playbook README](./rearchitecture-playbook/README.md) (5 minutes)
2. Skim the [skellycam-rearchitecture/ example](./skellycam-rearchitecture/) to see what good output looks like
3. Follow the 5 steps, using the skellycam docs as reference for depth and structure
4. Reference the [patterns catalog](./rearchitecture-playbook/05-patterns-catalog.md) for reusable Rust solutions

**If you're working on skellycam-rust itself:**
- The skellycam docs explain WHY the codebase looks the way it does
- Each doc maps to specific source files and architectural decisions
- The comparison sections explain what diverged from Python and why
