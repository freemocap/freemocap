# Re-architecture Playbook

How to re-architect a Python FreeMoCap component into Rust — the methodology we used for skellycam.

**This is not a porting guide.** You are not translating Python to Rust line by line. You are re-solving the same problem with a different set of constraints. Expect the architecture to look different. That's the point.

## The 5 Steps

1. **Understand the problem** — analyze the Python implementation to learn WHAT it does and WHY each architectural decision was made ([01-understand-the-problem](./01-understand-the-problem.md))

2. **Extract the invariants** — separate WHAT must be achieved from HOW Python achieved it. API contracts, binary protocols, file formats, behavioral guarantees. These are non-negotiable. ([02-extract-invariants](./02-extract-invariants.md))

3. **Separate Python-specific from universal** — identify which parts of the Python architecture exist solely because of Python constraints (GIL, multiprocessing, pickle, etc.) and which parts are inherent to the problem. This prevents accidentally carrying Python baggage into the Rust design. ([03-separate-python-concerns](./03-separate-python-concerns.md))

4. **Design Rust architecture from the invariants** — start from WHAT must be achieved, not HOW Python did it. Use Rust's strengths: threads sharing address space, compile-time guarantees, zero-cost abstractions, deterministic cleanup. ([04-design-rust-architecture](./04-design-rust-architecture.md))

5. **Document the comparison** — for each component, show the abstract problem, Python's solution (with rationale), Rust's solution (with rationale), and what changed. ([05-patterns-catalog](./05-patterns-catalog.md) catalogs reusable Rust patterns that emerged.)

## The Worked Examples

The [`../skellycam-architecture/`](../skellycam-architecture/) directory contains the output of applying this methodology to the SkellyCam camera backend. The [`../skellytracker-architecture/`](../skellytracker-architecture/) directory covers the skellytracker pose-estimation backend. The [`../freemocap-architecture/`](../freemocap-architecture/) directory is the active work-in-progress — applying the same methodology to the FreeMoCap real-time pipeline.

Use them as a reference when applying this methodology to another FreeMoCap component.
