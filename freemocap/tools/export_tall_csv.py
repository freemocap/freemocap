"""Export one saved recording run, without detection or reconstruction."""

import argparse
from pathlib import Path

from freemocap.core.recording.exports.tall_csv import TallCsvRequest, export_tall_csv, recover_tall_export
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    parser.add_argument('--run-id', type=int)
    parser.add_argument('--keep', action='store_true')
    parser.add_argument('--expected-revision')
    parser.add_argument('--recover', action='store_true', help='Finish an interrupted export publication')
    args = parser.parse_args()
    folder = args.recording.resolve()
    structure = RecordingStructure(base_directory=folder.parent, recording_name=folder.name)
    if args.recover:
        if args.keep and args.run_id is None:
            parser.error('--recover --keep requires --run-id')
        recover_tall_export(structure=structure, retained_run_id=args.run_id if args.keep else None)
        print('Export publication recovered')
    else:
        result = export_tall_csv(structure=structure, request=TallCsvRequest(
            run_id=args.run_id, keep=args.keep, expected_revision=args.expected_revision))
        print(result.model_dump_json(indent=2))


if __name__ == '__main__':
    main()
