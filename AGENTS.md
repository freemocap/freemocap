# Core repository guidance

Follow the containing workspace's ownership and review rules. Leave changes
unstaged and uncommitted for human review.

Tracker owns detector recipes, crop rules, keypoint assembly, schemas/connections,
and preset-specific mapping selection. Import its public preset/profile interfaces;
do not define equivalent detector trees or keypoint-selection rules in Core.
Core translates application settings and coordinates cameras, Tracker, Forge,
recording and transport. Distinguish detector keypoints, Tracker mapping rules,
and Forge anatomical landmarks when naming code and describing responsibilities.

When external research, documentation, tutorials or source code informs a change,
follow [CITATIONS.md](CITATIONS.md): register the source in root `references.bib`,
cite its stable key beside the supported claim, and record review scope honestly.
Run the bibliography validator and its tests before handoff. Preserve useful
background references even when they have no current inline citation.
