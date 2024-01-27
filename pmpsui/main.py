import argparse

import pydm
from .pmps import PMPS

def make_parser():
    parser = argparse.ArgumentParser(
        description='Display the PMPS diagnostic tool inside of PyDM.',
        prog='pydm pmps.py',
    )
    parser.add_argument(
        '--no-web',
        action='store_true',
        help='Disable the grafana web view tab.',
    )
    return parser


def main():
    parser = make_parser()
    args = parser.parse_args()

    app = PMPS(args=args)
