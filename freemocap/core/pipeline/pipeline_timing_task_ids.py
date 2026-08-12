"""Deterministic task IDs for pipeline timing events."""

CLOCK_DOMAIN_MONOTONIC = "monotonic"


def batch_task_id(
        *,
        frame_number: int,
        node_kind: str,
        stage: str,
) -> str:
    return f"{frame_number}:batch:{node_kind}:{stage}"
