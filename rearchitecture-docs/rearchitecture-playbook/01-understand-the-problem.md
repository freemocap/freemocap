# Step 1: Understand the Problem

Before writing any Rust code, thoroughly analyze the Python implementation. The goal is to understand WHAT the code does and WHY each architectural decision was made — not to memorize HOW it was implemented.

## What to Read First

Start at the entry point and trace the data flow:

1. **Entry point**: How does the application start? What gets initialized and in what order?
2. **API surface**: What endpoints exist? What request/response shapes does the frontend depend on?
3. **Core data flow**: How does data move through the system? Trace a single frame/request from entry to exit.
4. **Lifecycle management**: How are resources created, managed, and destroyed? What ensures cleanup?

## Questions to Answer for Each Component

For each architectural component, produce answers to these four questions:

### What does it do?
A one-paragraph functional description. Be concrete — name the files, classes, and functions involved. This is the WHAT.

### How is it structured?
A diagram or bullet list showing:
- The components and their relationships
- The data flow between them
- The concurrency model (processes? threads? async tasks?)
- The communication mechanisms (shared memory? queues? channels?)

### Why those choices?
For each significant architectural decision, identify the constraint that drove it. This is the most important part. Examples:
- "Uses `multiprocessing.Process` because CPython threads serialize on the GIL for CPU-bound work"
- "Uses shared memory ring buffers because frames are multi-MB and can't be copied through pipes"
- "Uses PubSub with polling because processes can't call methods on each other"

### What problems does each pattern solve?
Look for the "Python-Specific Problems This Architecture Solves" pattern. Every Python multiprocessing workaround, every shared memory DTO, every polling loop — what concrete problem would occur if it weren't there?

## Output Format

Produce a per-component analysis document with this structure:

```
# Component: <name>

## What It Does
<one-paragraph functional description>

## Architecture
<structure diagram or bullet list, data flow, concurrency model>

## Python-Specific Problems This Architecture Solves
<Table: Problem | Python Solution | Why It Exists>

## Key Files
<list of Python files analyzed, with brief notes on what each contains>
```

## Reference

See the [skellycam example](../skellycam/) for 9 documents produced using this template.
