# Quaternion rotation performance experiment

The installed scalar rotation performs two general NumPy cross products per
three-component vector. SkellyForge already exposes `rotate_vectors_batch`, but
its contract is **N quaternions times M vectors**, returning `(N, M, 3)`, rather
than pairing corresponding rows. Using it for paired rows and taking a diagonal
would unnecessarily compute N squared rotations [@skellyforgeQuaternionMath2026].

## Controlled arithmetic comparison

2026-10-11, local installed environment, float64, deterministic random unit
quaternions and vectors, five repetitions per paired method. Input generation and
quaternion construction excluded; scalar output collection included. These small
benchmarks indicate opportunities, not complete-pipeline speedups.

| Rotations | Existing scalar loop | Specialized scalar loop | Paired NumPy batch |
| --- | ---: | ---: | ---: |
| 64 | 1.8435 ms | 0.1297 ms | 0.0293 ms |
| 10,000 | 311.3247 ms | 22.1172 ms | 0.6432 ms |

The paired batch uses the original equation on arrays:

```python
cross_once = np.cross(quaternions[:, 1:], vectors)
rotated = vectors + 2.0 * (
    quaternions[:, :1] * cross_once
    + np.cross(quaternions[:, 1:], cross_once)
)
```

For these inputs paired batching matches exactly. Specialized scalar arithmetic
changes floating-point grouping: maximum absolute difference 8.89e-16.
The existing batch helper also passed a separate shared-vector comparison, which
is a different workload and not included in the paired-method timing table.

## Integration boundaries

- Independent rotations can be gathered into batches with explicit segment and
  landmark axes. Reuse the existing helper for its shared-vector contract.
- Temporal roll depends on previous frames and parent segments. Preserve those
  dependencies; batch only operations independent at that point in evaluation.
- Specialized scalar arithmetic offers a smaller change without changing graph
  scheduling, frame order, or allocation of work to threads.
- These are diagnostic candidates, not a production math implementation. An
  upstream change belongs in SkellyForge with its numerical edge-case tests and
  independent integration handoff. No installed dependency was edited.

Reproduction from this core worktree (the interpreter must import this checkout):

```powershell
../freemocap/.venv/Scripts/python.exe -B -c "from pathlib import Path; exec(compile(Path('.test-artifacts/performance/vector-math/probe.py').read_text(), 'vector_math_probe', 'exec'))"
```

Local ignored evidence: `.test-artifacts/performance/vector-math/micro.json`,
`probe.py`, and `reconstruction.json`. The scratch script requires the existing
sample managed-annotation output. Initial execution by script path resolved the
other core checkout and failed before reconstruction; the command above uses
this worktree as the import root without dependency overrides.

## Real recording reconstruction

The experiment reuses the sample recording's filtered points and original frozen
model fits. Each call constructs fresh temporal reconstruction state. Only
`RotationQuaternion.rotate_vector` is replaced inside this diagnostic process;
its original implementation is restored afterward. Fit, tracking, saving,
annotation and board reconstruction are outside this timing.

Every returned frame field is compared recursively, including world/local
quaternions, landmarks, segment origins, joint angles and centers of mass;
missing values, keys and shapes must agree. Numerical tolerance is absolute
1e-8 and relative 1e-10, with matching NaNs. Comparison time is excluded.

The diagnostic specialized method retains float64 coercion and shape validation,
but does not reproduce the original runtime type-checking decorator. Thus the
measured benefit includes any saved wrapper overhead, not only cross-product
arithmetic. A production change must retain the public validation contract.

Additional focused checks: 73 passed for identity, half turns, quaternion sign,
zero vectors, very small/large finite vectors, NaN propagation and invalid
shapes. These are exploratory checks, not the full upstream math regression suite.
The edge-check setup initially used integer values rejected by the installed
runtime type checker; it was corrected to the declared float64 contract.

| Run order | Method | Reconstruction seconds |
| --- | --- | ---: |
| 1 | Original | 30.735 |
| 2 | Specialized scalar | 21.272 |
| 3 | Specialized scalar | 20.712 |
| 4 | Original | 30.465 |

For 1,108 human-model frames, two-run medians are **30.600 s versus 20.992 s**:
**31.4% less reconstruction time (1.46 times throughput)**. Maximum absolute
output difference across comparisons was **2.274e-13**. No failed comparisons.
This is a reconstruction-component result, not a measured full-pipeline speedup.
Two repetitions per method on one dataset are preliminary evidence.

Recommended sequence: first optimize this scalar hot path upstream while retaining
validation and numerical edge-case contracts; then batch independent landmark
rotations within a solved pose. Preserve temporal roll and parent dependencies.
Only after upstream validation and human integration should the full recording
benchmark be rerun to measure end-to-end gains.
