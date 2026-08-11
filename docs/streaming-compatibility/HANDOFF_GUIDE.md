# How to write a handoff

A handoff lets the next agent resume **fast and correct**. It is a **bookmark + delta**, not a
re-derivation of the plan — the plan lives in the spec (`README` → `00`–`13` → `IMPLEMENTATION_PLAN` →
`phase-1/`). Link to it; don't restate it.

> Why this guide exists: a prior pickup burned real time on avoidable confusions — package-relative paths
> that hid the `freemocap/freemocap/` nesting; no "read the spec first" instruction (so the agent
> archaeologized the source instead of reading the plan); an ambiguous migration status (a half-finished
> change that read as done); and only one of two live threads surfaced. Each item below is a countermeasure
> to one of those.

## A handoff MUST contain

1. **Orientation first.** One line up top: *read the spec in order before touching code (link); current
   state = the `IMPLEMENTATION_PLAN` progress log + this file; workspace layout + cross-repo model are in
   `project/CLAUDE.md`.*
2. **Env, exactly.** The one command to get running, and that it's required before verifying. Name known
   blockers (heavy deps; **cross-repo = git, not local** — see `project/CLAUDE.md`). For a change in a
   skelly repo, say where it is verified (that repo's own env) and that the user must commit it before
   freemocap sees it.
3. **All live threads, with status** — not just "next." For each: `done | in-progress | blocked-on-X`,
   linked to its spec/plan doc. If two things are in flight, say so and which one the user prioritized.
4. **Where the last person stopped, and why** — the precise boundary and the blocker.
5. **Next actions, ordered and linked** — each to the plan doc that specifies it. Flag which are mechanical
   vs. which need a decision from the user.
6. **Load-bearing invariants — WITH STATUS.** Not just the rule but whether it is *done / active /
   aspirational*. Status ambiguity is what burned the last pickup (a rule stated flatly when the change was
   actually mid-migration).
7. **Correct, unambiguous paths.** Workspace-relative; call out nestings and duplicated files.
8. **Open decisions** — each with the **trigger** that resolves it.

## Template

```markdown
# <Phase/WS> Handoff — <date>

## Start here
Read the spec in order before coding: docs/streaming-compatibility/{README, 00–13, IMPLEMENTATION_PLAN,
phase-1/}. Workspace layout + cross-repo dev model: ../../../CLAUDE.md (project root). Don't re-derive the
plan from source. If scope/sequence is unclear after reading, ask.

## Env
<one command to run + verify; known blockers; where skelly-repo changes are verified>

## Where we are (all threads)
- <Thread A> — <done|in-progress|blocked-on-X> — <link to plan doc>
- <Thread B> — <status> — <link>
User's current priority: <which thread>.

## Where the last person stopped
<precise boundary + why (blocker)>

## Next actions (ordered)
1. [ ] <action> — <plan doc §> — <mechanical | needs-decision>
2. ...

## Load-bearing invariants (with status)
- <rule> — <done | active | aspirational> — <link>

## Open decisions
- <question> — trigger that resolves it: <event>

## Built so far (accurate, path-correct)
<what exists + tests, with real paths>
```

## Anti-patterns

- Restating the spec instead of linking it (breaks Single Source of Truth).
- Listing only the single "next" task when other threads are live.
- Stating a rule without its status.
- Package-relative paths that hide a nesting or a duplicate file.
- "Env not synced" without the exact command or the cross-repo (git-not-local) caveat.
