import os
import platform
import sys

import toml  # for reading pyproject.toml
from cx_Freeze import Executable, setup
from sklearn import __path__ as sklearn_path

pyproject = toml.load("../pyproject.toml")
version = pyproject["project"]["version"]
# base="Win32GUI" should be used only for Windows GUI app
print(f"sys.platform: {sys.platform}")
base = "Win32GUI" if sys.platform == "win32" else None
# Include the path to the Python script you want to freeze.
script_path = "main.py"
# include paths files
include_files = [
    ("../pyproject.toml", "lib/pyproject.toml"),
    "lib/",
]

# Automatically add DLLs from sklearn/.libs if on Windows
if sys.platform == "win32":
    sklearn_path = sklearn_path[0]
    libs_dir = os.path.join(sklearn_path, ".libs")
    if os.path.isdir(libs_dir):
        for filename in os.listdir(libs_dir):
            if filename.endswith(".dll"):
                include_files.append((os.path.join(libs_dir, filename), filename))

# windows build
# Find the vcomp140.dll file in the system
vcomp140_dll_path = os.path.join(os.environ["windir"], "System32", "vcomp140.dll")
print(
    f"vcomp140_dll_path: {vcomp140_dll_path}, exists: {os.path.exists(vcomp140_dll_path)}"
)
# Also add msvcp140.dll (common for OpenMP/MSVC runtime)
msvcp140_dll_path = os.path.join(os.environ["windir"], "System32", "msvcp140.dll")
if os.path.exists(vcomp140_dll_path):
    include_files.append((vcomp140_dll_path, "vcomp140.dll"))
if os.path.exists(msvcp140_dll_path):
    include_files.append((msvcp140_dll_path, "msvcp140.dll"))

# Linux: commented for now. No signs of malfunction. If needed, change to proper paths. We dropped conda in Linux for pip and venv.
# ("/home/jonathan/mambaforge/envs/brainwash/lib/libcblas.so", "lib/libcblas.so"), ("/home/jonathan/mambaforge/envs/brainwash/lib/libcblas.so.3", "lib/libcblas.so.3")]
# Create an executable.
exe = Executable(
    script=script_path,
    base=base,
    target_name="brainwash",  # Name of output exe/AppImage
)
# Setup cx_Freeze options.
options = {
    "build_exe": {
        "includes": [],
        "zip_include_packages": ["sklearn", "joblib", "scipy", "numpy"],
        "include_msvcr": True,
        "excludes": ["tkinter", "email", "pytest"],
        "packages": [
            "pyabf",
            "igor2",
            "tqdm",
            "joblib",
            "sklearn",
            "numpy",
            "scipy",
            "seaborn",
        ],
        "include_files": include_files,
    }
}
# Call the setup function.
setup(
    name="brainwash",
    version=version,
    description="",
    # packages=find_packages(where="src"),
    # package_dir={"": "src"},
    # include_package_data=True,
    options=options,
    executables=[exe],
)

# Post-build step: Overwrite sklearn/_distributor_init.py in the build dir to handle frozen correctly
if sys.platform == "win32":
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    arch = "amd64" if "64" in platform.architecture()[0] else "win32"
    build_dir = f"build/exe.win-{arch}-{python_version}"  # Dynamically compute for matrix compatibility
    sklearn_dir = os.path.join(build_dir, "lib", "sklearn")
    if os.path.exists(sklearn_dir):
        distributor_file = os.path.join(sklearn_dir, "_distributor_init.py")
        with open(distributor_file, "w") as f:
            f.write('''
"""Helper to preload windows dlls to prevent dll not found errors."""

import os
import sys

if os.name == 'nt':
    from ctypes import WinDLL
    libs_path = os.path.join(os.path.dirname(__file__), '.libs')
    if '.zip' in __file__:
        # Handle zipped package
        zip_path = __file__.split('.zip', 1)[0] + '.zip'
        libs_path = os.path.join(os.path.dirname(zip_path), 'sklearn', '.libs')
    if hasattr(sys, 'frozen'):
        libs_path = os.path.dirname(sys.executable)
    if os.path.isdir(libs_path):
        old_cwd = os.getcwd()
        os.chdir(libs_path)
        for filename in os.listdir(libs_path):
            if filename.endswith('.dll'):
                try:
                    WinDLL(filename)
                except:
                    pass
        os.chdir(old_cwd)
''')
