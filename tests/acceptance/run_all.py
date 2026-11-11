#!/usr/bin/env python3
"""Every acceptance test, each in its own process. Exit 1 if any is red."""
import glob
import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
red = []
for f in sorted(glob.glob(os.path.join(here, "test_*.py"))):
    print(f"--- {os.path.basename(f)}")
    if subprocess.run([sys.executable, f]).returncode:
        red.append(os.path.basename(f))
print("\nred: " + (", ".join(red) or "none"))
sys.exit(bool(red))
