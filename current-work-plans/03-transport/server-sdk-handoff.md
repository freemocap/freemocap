# JavaScript/TypeScript server SDK handoff

## Reuse by other applications

Branch `sfn26-ultraskelly` adds application-defined message kinds, image payload
decoding, a browser bundle, insecure-context connections and a Python encoder
package so other servers can use this stream. See
[sdk-for-other-applications.md](sdk-for-other-applications.md) for the changes and
[sdk-external-review.md](sdk-external-review.md) for the integration review and wish list.

## Additive output milestone

The current working source adds five server-owned output controls to the original
59-operation SDK baseline below (64 total). See `streaming-output-contract-delta.md`
for lifecycle, acquisition-clock provenance, optional LSL runtime and limitations.
The original compatibility record remains historical evidence for its tested
baseline. Live LSL capture and a rendered VMC receiver avatar are still open.

## Original SDK milestone

The approved six-step W6 checklist is complete. The result is the standalone
`@freemocap/client` development package, integrated into the default app, with
HTTP/WS/recording conformance and real-server acceptance. Python/Rust clients,
VMC/LSL outputs and engine connectors remain future workstreams.

The proposed continuation is in `streaming-ecosystem-next-phase.md`; it keeps
every requested target open and recommends Python plus Blender as the first
visible next milestone. `server-sdk-local-demo.md` gives the isolated local
review recipe, including explicit backend port and browser-origin settings.
That recipe was source-inspected, not freshly launched during planning.

## Source ownership and integration

- SDK source is `packages/freemocap-client` within the FreeMoCap repository. It is
  a private, unpublished `0.1.0-dev.0` package with its own API, tests and build.
  The original isolated sibling source remains preserved as historical evidence.
- Core UI consumes `file:../packages/freemocap-client`. Build the SDK before building
  the UI. The SDK owns HTTP bindings, connection/decoder/resolver code and pure
  recording readers. Existing UI import paths re-export these implementations.
- Core retains application configuration, stores, rendering, worker ownership and
  cross-repository integration tests. No component detector/geometry logic moved.
- Public documentation changes belong to the separate `freemocap.github.io` repository.
  All source changes remain unstaged and uncommitted; nothing was published.

The server baseline is runtime `90cd474e94eb320be22cadd2b65472108725dd54`,
handoff/Core checkout `19acf12c68d008e0250fd8921b2d468f996a47a4`.
SDK `contracts/operations.json` and `compatibility/0.1.0-dev.0.json` identify schema,
source fingerprints, dependency revisions and the tested runtime. Application
version strings alone do not identify this API.

All 59 public operations have typed bindings and raw-response variants. Binary
resource responses remain unconsumed; errors, request abort and explicit task
cancellation keep their distinct meanings. Every CBOR frame remains independently
interpretable. Repeated metadata identity and numerical ownership are preserved.
The generic recording reader includes all declared dynamic channels and retains
stage provenance; the app's scene reader keeps its prior allocation policy.

Typed application integration also corrected calibration capture's request body:
capture sends `calibrationRecordingDirectory` and `calibrationTaskConfig`;
processing retains its separate `kind`/`config` body.

## Validation evidence

- SDK: 93 tests passed, zero failures/skips; negative TypeScript cases passed;
  generated bindings reproduced byte-for-byte; 59 coverage entries verified.
- Application: 82 Node checks, 7 operation-progress checks and 2 camera-store scripts;
  21 affected browser cases and3 native video cases passed. Earlier 15- and 71-case
  campaigns had fixture/mock issues subsequently closed; these overlap later runs.
  Strict types and Vite build passed. Existing asset/CSS/chunk warnings remain.
- Private server/reference reads: 222 and 1,108 frames, 36 channels each; 494,760 landmark
  values matched independent PyArrow reads exactly. Exports completed through
  HTTP and WebSocket; range reads, HTTP 404/409/422, request abort, reconnect and offline
  ECONNREFUSED passed. Source hashes were unchanged; server cleanup reported exit code 0 and no errors.
- Recorded-channel socket replay: 2,586 frames including late joins at frame 37; 961,992
  float32 comparisons passed. Canonical Python encoding, model identity reuse,
  retained arrays, ping/pong and display feedback were checked. This was transport
  replay, not a fresh inference run.
- Physical acceptance: four cameras/Python/CUDA, 152 frames per camera, no missing
  frame numbers, matching capture/video timestamps and capture rates of 29.8618 to 29.8686 FPS.
  The production app received 317 processed frames in 20 seconds (15.82 arrival FPS),
  with no reported UI errors. Capture rate is not processed-stream rate.
  Both GPU and cameras were explicitly released after delayed checks found no
  surviving owned process identities or open server port.
- Four runnable examples executed successfully against another private server;
  their export used a private copy. Local tarball entry points, declarations and
  license were checked without publishing or installing a new environment.

Raw local evidence is under `.test-artifacts/w6/`: `integration-evidence.json`,
`server-acceptance-01/`, `replay-03/`, `live-01/`, `examples-01/`, and documentation/
package reports. `live-01/ui/application.png` shows the tested app. The versioned
SDK compatibility record contains portable summaries and limitations.

Node 24.21.0, Edge 156.0.4314.58 and Electron 35.7.5 were exercised. Node 22 is declared
but was not separately tested. Full isolated Docusaurus builds were not run;
affected documentation compiled with the existing MDX compiler. Blender install/
launch and microphone side effects were not exercised merely to satisfy binding
coverage. There is no claim that every external integration or platform is tested.

## Reproduction and next work

In the SDK, run `npm test`; the README documents source installation and all four
examples. In the UI, `npm run test:sdk` runs the maintained Node integration checks;
set the documented reference-file environment variables to exercise reference data.
Core modules `freemocap.tools.sdk_validation`, `sdk_replay_validation`,
`sdk_live_validation` and `sdk_examples_validation` expose their inputs with
`--help`. Use a new ignored output directory. Physical validation needs an assigned
camera/GPU slot; the completed W6 slot is released.

Further publication/repository setup remains owner-controlled. Future clients and
adapters should reuse the accepted contract and independent fixtures; this handoff
does not authorize new protocols, metadata deltas or component ownership changes.
