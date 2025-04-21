import sys
import os
from setuptools import find_packages
from cx_Freeze import setup, Executable
import toml  # for reading pyproject.toml


pyproject = toml.load("../pyproject.toml")
version = pyproject['project']['version']

# base="Win32GUI" should be used only for Windows GUI app
print(f"sys.platform: {sys.platform}")
base = "Win32GUI" if sys.platform == "win32" else None


# Include the path to the Python script you want to freeze.
script_path = "main.py"
# Find the vcomp140.dll file in the system
#vcomp140_dll_path = os.path.join(os.environ['windir'], 'System32', 'vcomp140.dll')
#print(f"vcomp140_dll_path: {vcomp140_dll_path}, exists: {os.path.exists(vcomp140_dll_path)}")

# Additional files/directories that should be included in the distribution.
# You may need to add other dependencies or data files here.
include_files = []
#include_files = [f"{vcomp140_dll_path}", "lib/", ("../pyproject.toml", "lib/pyproject.toml")]
		 #("/home/jonathan/mambaforge/envs/brainwash/lib/libcblas.so", "lib/libcblas.so"), ("/home/jonathan/mambaforge/envs/brainwash/lib/libcblas.so.3", "lib/libcblas.so.3")]
# Create an executable.
exe = Executable(
    script=script_path,
    #base=base,
    #targetName="hello.exe"  # The name of the output executable.
)

# Setup cx_Freeze options.
options = {
    "build_exe": {
        "includes": [],
        "excludes": [],
        "packages": ["pyabf", "igor2", "tqdm", "sklearn", "scipy", "seaborn"],
        "include_files": include_files
    },
    "bdist_appimage": {"compression": "gzip"}
}


# Call the setup function.
setup(
    name="brainwash",
    version=version,
    description="",
    #packages=find_packages(where="src"),
    #package_dir={"": "src"},
    #include_package_data=True,
    options=options,
    executables=[exe],
    base=base
)

