#!/usr/bin/env python3
"""Backward-compatible validator entrypoint."""
import sys
from wiki import main

if __name__ == "__main__":
    raise SystemExit(main(["check", *sys.argv[1:]]))
