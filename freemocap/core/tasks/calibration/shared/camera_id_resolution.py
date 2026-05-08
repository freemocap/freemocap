"""Resolve a query camera_id against a candidate set with the same fallback
ladder used by SkellyCam's video filename parser.

Used wherever two camera-keyed surfaces have to agree (runtime frame metadata
vs calibration TOML, calibration TOML vs pin-target id, etc.). Exact-string
equality is the happy path; if that fails, both sides are run through the
heuristic index extractor (cam-prefix / trailing-int / digit) and matched on
the extracted index. If neither pass produces a hit, callers should treat that
as a hard error — silent skip is exactly the failure mode this module exists
to eliminate.
"""

from skellycam.core.recorders.videos.parse_video_filename import try_extract_camera_info


class CameraIdMismatchError(KeyError):
    """A camera_id could not be resolved against the candidate set."""


def _heuristic_index(camera_id: str) -> int | None:
    """Best-effort integer-index extraction from a camera_id string.

    Mirrors the SkellyCam filename parser's ladder: cam-prefix > trailing-int >
    opaque digit. Returns None when the string carries no recoverable index.
    """
    if camera_id.isdigit() and int(camera_id) <= 20:
        return int(camera_id)
    _, idx, _ = try_extract_camera_info(camera_id)
    return idx


def resolve_camera_id(query: str, candidates: list[str]) -> str | None:
    """Match `query` to one of `candidates` using the fallback ladder.

    1. Exact equality.
    2. Heuristic index extraction on both sides; match by extracted index.

    Returns the matched candidate, or None if no match is found.
    """
    if query in candidates:
        return query

    query_idx = _heuristic_index(query)
    if query_idx is None:
        return None

    for cand in candidates:
        cand_idx = _heuristic_index(cand)
        if cand_idx is not None and cand_idx == query_idx:
            return cand
    return None


def resolve_camera_id_or_raise(
    query: str,
    candidates: list[str],
    *,
    context: str = "",
) -> str:
    """Like `resolve_camera_id`, but raises `CameraIdMismatchError` on miss.

    `context` is interpolated into the error message to help the operator
    locate the mismatch (e.g. "runtime frame vs calibration TOML").
    """
    matched = resolve_camera_id(query, candidates)
    if matched is None:
        ctx = f" [{context}]" if context else ""
        raise CameraIdMismatchError(
            f"Could not resolve camera_id {query!r} against {candidates}{ctx}. "
            f"Tried exact match then heuristic index extraction "
            f"(cam-prefix / trailing-int / digit). Verify that the camera_ids "
            f"on both sides agree exactly, or share a common cam-prefix or "
            f"trailing-integer pattern."
        )
    return matched
