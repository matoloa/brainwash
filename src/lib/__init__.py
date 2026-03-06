"""
Trickery with sys.path to allow absolute importing from scripts higher in tree without intermediate folders.
This is to allow intra package importing within folders, while making it look like absolute importing.
This is a workaround to allow imports from modules on the same level, and tests.
We have concluded that __init__ only runs once, even if we import several modules from its folder.
"""

# print(f"lib/__init__.py was just run")
import sys
from pathlib import Path

folder_path = str(Path(__file__).parent)
sys.path.append(folder_path)
