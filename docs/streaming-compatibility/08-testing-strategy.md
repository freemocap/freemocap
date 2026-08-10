# 08 — Testing Strategy

The wire is unforgiving and the failure modes are silent: a coordinate flip produces a
plausible-looking stream that a real consumer renders as a horror. The strategy is layered so each
layer catches a class of bug the others can't.

## 1. Golden bytes — standard stream and each adapter

A fixed canonical frame in → **exact expected bytes** out. The cheapest possible guard against silent
wire-format regressions.

Because the standard stream deliberately **mirrors LSL's data model**
([01](01-canonical-data-model.md#the-stream-schema--samples)), the golden-byte fixtures split the
same way the stream does:
- a **schema** fixture (the StreamInfo-like descriptor), and
- a **sample** fixture (one timestamped frame).

Aligning our own binarization with the LSL sample model means the standard-stream fixtures and the
LSL-route fixtures are the *same shape* — the LSL route should reproduce the standard-stream samples
byte-for-byte (modulo LSL's own framing), which is itself the pass-through test (§6). Each
foreign-protocol adapter (VMC) gets its own golden fixture over several message shapes.

## 2. Loopback conformance

Emit → receive → reconstruct → compare against a direct computation. Send over real UDP loopback and
reproduce all bones' world positions against direct forward kinematics.

- Validates the *round trip*, not just the encoder.
- **Cross-machine variant for VMC:** loopback's 64 KB datagram limit hides the MTU-splitting
  requirement ([03](03-emitters.md#the-vmc-adapter)). At least one test (or documented manual
  procedure) must exercise the multi-datagram path on a real ~1500-byte-MTU link.

## 3. Coordinate-converter golden vectors

The single convention-conversion function ([07](07-coordinate-conventions.md#one-conversion-function))
is tested against hand-computed golden vectors: known input in the canonical convention (mm / right /
+Z) → known output in each target convention (VMC left / +Y / m, Unreal +Z / cm, etc.), including the
handedness flip and the local-vs-world rotation transform. This is where the "looks perfect locally,
explodes remotely" class of bug is caught before it reaches an adapter.

## 4. Positive-capability test

Assert that each adapter's **declared emitted channels** match what it *actually* emits, and that its
`required_fields` / `required_views` are satisfiable by the schema. Positive only — we test what a
thing *is*, never a "what it discards" list. A declaration that drifts from reality is a test
failure, not a support ticket.

## 5. Schema / standard-stream round-trip

- Encode the schema, decode it, and confirm the channel set, joint hierarchy, rest pose, and
  convention reconstruct exactly.
- Confirm a decoded stream of samples reassembles into the canonical frame values (positions,
  rotations, confidence, timestamps).

## 6. LSL pass-through

Because the LSL route is a pass-through of the standard stream, test it as one: standard-stream schema
→ LSL `StreamInfo`, standard-stream samples → `push_sample`, captured by a real **LabRecorder**, and
the recorded channels reconstruct to the canonical values with LSL's own timestamps intact.

## 7. Mailbox / dispatch tests

The latest-frame slot ([02](02-streaming-hub.md#the-handoff--a-single-slot-mailbox-not-a-queue)) has
behavior worth pinning:
- Drop-oldest: writing N frames before a slow output reads yields only the newest.
- Per-output rate decoupling: a 90 Hz and a 30 Hz output reading the same slot each get their own
  cadence; a stalled output never backpressures the tap.

## 8. At least one real third-party consumer per protocol

**The decisive test.** A self-written receiver shares your misconceptions and cannot validate your
understanding of a protocol — see
[07](07-coordinate-conventions.md#why-a-self-written-receiver-cant-validate-this). So each protocol
has at least one test (automated where possible, **manual and documented** where not) against real
third-party software:

- **LSL:** LabRecorder captures the outlet and the recorded channels reconstruct (also §6).
- **VMC:** VirtualMotionCapture and EVMC4U, or VSeeFace / Warudo. Conformance means "does the avatar
  move correctly in these," because for VMC **the reference implementation *is* the spec** —
  non-conforming software exists in the wild that works by accident.

## 9. Control-plane / failure tests

- Setup failures ([04](04-http-control-plane.md#failure-model)) return the right status synchronously:
  port in use → error naming the conflict; bad config → `422`.
- A runtime error moves **only** that stream to `FAILED`, leaves other streams and the capture session
  running, and the error is retrievable via `GET /streaming/streams/{id}`.
- Start-with-no-capture starts idle and begins emitting when frames appear.
- Multiple concurrent streams (two protocols; two instances of one protocol on different ports) start,
  run, and stop independently.

## What "done" looks like per output

A transport/adapter is shippable when: golden bytes pass, loopback (incl. cross-machine where relevant)
passes, its positive-capability declaration is asserted, and it has been shown driving **real**
third-party software at least once.
