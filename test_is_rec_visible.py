import sys
with open("src/lib/ui.py") as f:
    if "def _is_rec_visible" in f.read():
        print("Found")
