import sys
from setuptools import find_packages
from cx_Freeze import setup, Executable

# base="Win32GUI" should be used only for Windows GUI app
print(f"sys.platform: {sys.platform}")
base = "Win32GUI" if sys.platform == "win32" else None


# Include the path to the Python script you want to freeze.
script_path = "main.py"
# Additional files/directories that should be included in the distribution.
# You may need to add other dependencies or data files here.
include_files = ["lib/", "pyproject.toml"]
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
        "packages": ["pyabf", "igor2", "seaborn", "tqdm", "sklearn"],
        "include_files": include_files
    }
}


# Call the setup function.
setup(
    name="Brainwash",
    version="0.6.3", # also update in pyproject.toml
    description="",
    #packages=find_packages(where="src"),
    #package_dir={"": "src"},
    #include_package_data=True,
    options=options,
    executables=[exe],
    base=base
)

