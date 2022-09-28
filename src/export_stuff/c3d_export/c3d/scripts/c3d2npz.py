#!/usr/bin/env python

'''Convert a C3D file to NPZ (numpy binary) format.'''

from __future__ import print_function

import c3d
import argparse
import logging
import gzip
import numpy as np
import sys
from tempfile import TemporaryFile

parser = argparse.ArgumentParser(description='Convert a C3D file to NPZ (numpy binary) format.')
parser.add_argument('input', default='-', metavar='FILE', nargs='+', help='process data from this input FILE')
parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")

def convert(filename, args):
    input = sys.stdin
    outname = '-'
    if filename != '-':
        input = open(filename, 'rb')
        outname = filename.replace('.c3d', '.npz')
        
    points = []
    analog = []
    for i, (_, p, a) in enumerate(c3d.Reader(input).read_frames()):
        points.append(p)
        analog.append(a)
        if not i % 10000 and i:
            logging.debug('%s: extracted %d point frames', outname, len(points))

    np.savez(outname, points=points, analog=analog)
    print(outname + ': saved', len(points), "x", str(points[0].shape), "points,", 
        len(analog), analog[0].shape, 'analog' if len(analog) else ()
    )
    
    if filename != '-':
        input.close()


def main():
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    for filename in args.input:
        convert(filename, args)


if __name__ == '__main__':
    main()
