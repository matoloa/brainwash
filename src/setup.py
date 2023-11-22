import os
import sysconfig

from cx_Freeze import Executable, setup

platform = sysconfig.get_platform()
python_version = sysconfig.get_python_version()
#dir_name = f"zip.{platform}-{python_version}"
#build_exe_dir = os.path.join("build", dir_name)
build_exe_dir = f"brainwash-{platform}-{python_version}"
# Include the path to the Python script you want to freeze.
script_path = "main.py"
# Additional files/directories that should be included in the distribution.
# You may need to add other dependencies or data files here.
include_files = ["lib/"]
# Create an executable.

options = {
    "build_exe": {
        "build_exe": build_exe_dir,
        "packages": ["pyabf", "neo", "tqdm", "sklearn"],
        "include_files": include_files
    }
}

executables = [
    Executable("main.py"),
]

setup(
    name="brainwash",
    version="0.5",
    description="Washes brains",
    executables=executables,
    options=options,
)
