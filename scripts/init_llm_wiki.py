#!/usr/bin/env python3
"""Backward-compatible initializer entrypoint."""
import sys
from wiki import main

if __name__ == "__main__":
    raise SystemExit(main(["init", *sys.argv[1:]]))
