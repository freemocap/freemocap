# Reconstruction rotation outputs

The shared real-time/post hoc `reconstruct_skeleton` output boundary applies
these conventions before returning results to consumers. Solver state, roll
continuity, quaternion multiplication and anatomical joint definitions do not
change. These are output conventions, not a new motion filter.

* Segment orientations remain unit **wxyz** quaternions in the existing world
  and parent-relative coordinate frames. Choose positive w; at exactly zero w,
  choose the sign making the first nonzero x/y/z component positive. This is
  SciPy's canonical policy. Flip all four components together, never individually.
  Reject invalid outputs rather than silently normalizing arbitrary values
  [@scipyRotationQuaternion].
* Joint angles retain each joint's intrinsic Euler sequence, angle names and
  middle-angle range. The first and third angles use **(-pi, pi]**. Exact -pi
  is represented as +pi. Euler sequence and singularity handling remain Forge's
  responsibility [@scipyRotationEuler].
* To remove the observed float64 endpoint-roundoff discrepancy, outer angles
  within **32 * float64 epsilon * pi** (about 2.23e-14 radians) of either endpoint
  are snapped to +pi. This small rounding band is our explicit numerical policy,
  not a claim of a universal standard. It changes a single angle by at most
  that amount modulo a full turn; both outer angles together change the rotation
  by at most twice that bound plus arithmetic roundoff. Values outside the band
  are not snapped. Scientific comparison tolerances are unchanged.

Canonical output is not a promise of temporal continuity. In particular, no
positive-w rule is fed back into the temporal solver. Interpolation/derivatives
must respect equivalent quaternion signs; raw Euler differences are unsuitable
for angular velocity. Reconstruction currently does not compute angular velocity.
Keep rotation-aware parity checks alongside checks of definitions, missing masks
and output ranges [@scipyRotationMagnitude].

Implementation batches the numeric work across all supplied segments/joints;
dictionary packing is the only per-name conversion. Empty dictionaries stay empty.
This contract applies to newly computed reconstruction outputs, not a migration
or reinterpretation of previously saved files.
