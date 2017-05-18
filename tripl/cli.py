#!/usr/bin/env python

import argparse
#from tripy import trip


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input')
    parser.add_argument('-o', '--output')
    return parser.parse_args()

# planned subcommand structure:
# trip
#   merge
#   diff
#   pull

def _main(args):
    print "Greetings, human"


def main():
    args = get_args()
    return _main(args)


if __name__ == '__main__':
    main()

