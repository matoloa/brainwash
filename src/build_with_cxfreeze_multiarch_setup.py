# build_with_cxfreeze_multiarch_setup.py
import sys
import os
from setuptools import find_packages
from cx_Freeze import setup, Executable
import toml

# Load version from pyproject.toml (one level up)
pyproject = toml.load("../pyproject.toml")
version = pyproject["project"]["version"]

print(f"Building brainwash v{version} on {sys.platform}")

# GUI base: only use Win32GUI on Windows when not in console/debug mode
base = None
if sys.platform == "win32":
    # If running from terminal (has real stdout), keep console for debugging
    base = "Win32GUI" if not sys.stdout.isatty() else "Console"

# Your main script
script_path = "main.py"

# Files/folders to include
include_files = [
    ("../pyproject.toml", "lib/pyproject.toml"),
    "lib/",                      # entire lib folder
    "assets/",                   # if you have one
]

# Common build options
build_exe_options = {
    "packages": ["pyabf", "igor2", "tqdm", "sklearn", "numpy", "scipy", "seaborn", "matplotlib", "pandas"],
    "excludes": ["tkinter", "email", "pytest", "test", "unittest"],
    "include_files": include_files,
    "include_msvcr": True,                    # Critical: bundles VC++ runtime → works on clean Win11
    "optimize": 2,
}

# MSI-specific options (only used on Windows)
bdist_msi_options = {
    "upgrade_code": "{A1B2C3D4-5678-90AB-CDEF-1234567890AB}",  # Keep this forever!
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFiles64Folder]\BrainWash",
    "summary_data": {
        "author": "Your Name",
        "comments": "Electrophysiology analysis tool",
    },
}

# Executable definition
exe = Executable(
    script=script_path,
    base=base,
    icon="assets/icon.ico" if os.path.exists("assets/icon.ico") else None,
    target_name="BrainWash.exe",  # Nice clean name in Windows
)

# Final setup — cx_Freeze automatically picks the right targets from command line
setup(
    name="BrainWash",
    version=version,
    description="Advanced electrophysiology data analysis",
    author="Your Name",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,     # Used only on Windows
        "bdist_appimage": build_exe_options,  # Used only on Linux
    },
    executables=[exe],
)
