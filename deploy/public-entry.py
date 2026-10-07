"""Installed at /opt/livelife/control/public-entry.py, used as SSH forced command."""
from livelife.manager import main
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('operation', nargs='?', choices=['recover'])
args = parser.parse_args()
main({'op': args.operation} if args.operation else None)
