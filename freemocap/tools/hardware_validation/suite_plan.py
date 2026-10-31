"""Finite repeatable suites; exhaustive matrix generation remains a separate command."""
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class SuiteCase:
    case_name: str
    camera_ids: tuple[str, ...]
    requested_ids: tuple[str, ...] = ()
    control_name: str = ''


def selected_cases(camera_ids: tuple[str, ...], suite_name: str) -> list[SuiteCase]:
    identities = tuple(sorted(camera_ids))
    if not identities or suite_name not in ('quick', 'extended'):
        raise ValueError('A nonempty camera inventory and quick/extended suite are required')
    subsets = [identities[:count] for count in range(1, len(identities) + 1)]
    if suite_name == 'extended':
        subsets = [selection for count in range(1, len(identities) + 1) for selection in combinations(identities, count)]
    cases = [SuiteCase('record-' + '-'.join(selection), selection) for selection in subsets]
    if len(identities) > 1:
        cases.extend((SuiteCase('add-camera', identities[:1], identities[:2]),
                      SuiteCase('remove-camera', identities[:2], identities[:1])))
    cases.extend((SuiteCase('pause-resume', identities), SuiteCase('close-during-recording', identities),
                  SuiteCase('repeat-apply', identities), SuiteCase('change-backend', identities),
                  SuiteCase('disconnect-reconnect-stream', identities)))
    controls = ('exposure', 'rotation', 'exposure-auto', 'exposure-recommend', 'resolution')
    targets = identities if suite_name == 'extended' else identities[:1]
    cases.extend(SuiteCase(f'{control}-{target}', identities, (target,), control)
                 for target in targets for control in controls)
    if suite_name == 'extended':
        cases.extend((SuiteCase('repeat-record-start', identities), SuiteCase('stop-without-recording', identities),
                      SuiteCase('pause-during-recording', identities)))
    return cases
