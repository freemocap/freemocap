#!/usr/bin/env python

'''Convert a C3D file to CSV (text) format.'''

from __future__ import print_function

import c3d
import sys
import argparse

parser = argparse.ArgumentParser(description='Convert a C3D file to CSV (text) format.')
parser.add_argument('-a', '--include-analog', action='store_true', help='output analog values after point positions')
parser.add_argument('-c', '--include-camera', action='store_true', help='output camera count with each point position')
parser.add_argument('-r', '--include-error', action='store_true', help='output error value with each point position')
parser.add_argument('-e', '--end', default='\\n', metavar='K', help='write K between records')
parser.add_argument('-s', '--sep', default=',', metavar='C', help='write C between fields in a record')
parser.add_argument('input', default='-', metavar='FILE', nargs='+', help='process data from this input FILE')


def convert(filename, args, sep, end):
    input = sys.stdin
    output = sys.stdout
    open_file_streams = filename != '-'
    if open_file_streams:
        input = open(filename, 'rb')
        output = open(filename.replace('.c3d', '.csv'), 'w')
    try:
        for frame_no, points, analog in c3d.Reader(input).read_frames(copy=False):
            fields = [frame_no]
            for x, y, z, err, cam in points:
                fields.append(str(x))
                fields.append(str(y))
                fields.append(str(z))
                if args.include_error:
                    fields.append(str(err))
                if args.include_camera:
                    fields.append(str(cam))
            if args.include_analog:
                fields.extend(str(x) for x in analog.flatten())
            print(*fields, sep=sep, end=end, file=output)
    finally:
        if open_file_streams:
            input.close()
            output.close()


def main():
    args = parser.parse_args()
    sep = args.sep.replace('\\t', '\t').replace('TAB', '\t')
    end = args.end.replace(
        '\\r', '\r').replace('CR', '\r').replace(
        '\\n', '\n').replace('NL', '\n')
    for filename in args.input:
        convert(filename, args, sep, end)

if __name__ == '__main__':
    main()
