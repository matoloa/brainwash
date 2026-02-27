import sys

import toml  # for reading pyproject.toml
from cx_Freeze import Executable, setup

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
# windows build
# Find the vcomp140.dll file in the system
# vcomp140_dll_path = os.path.join(os.environ['windir'], 'System32', 'vcomp140.dll')
# print(f"vcomp140_dll_path: {vcomp140_dll_path}, exists: {os.path.exists(vcomp140_dll_path)}")
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
        "zip_include_packages": ["*"],
        "no_compress": False,
        "include_msvcr": True,
        "excludes": ["tkinter", "email", "pytest", "pyarrow"],
        "packages": [
            "pyabf",
            "igor2",
            "tqdm",
            "joblib",
            "sklearn",
            "numpy",
            "numpy.core",
            "scipy",
            "scipy.linalg",
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
