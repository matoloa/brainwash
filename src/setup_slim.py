import sys
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
# Additional files/directories that should be included in the distribution.
# You may need to add other dependencies or data files here.
include_files = ["lib/", ("../pyproject.toml", "lib/pyproject.toml")]
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
        "excludes": ["statsmodels", "jedi", "fonttools"],  # unsure about statsmodels
        "packages": ["pyabf", "igor2", "tqdm", "joblib", "scipy", "sklearn"],
        "include_files": include_files,
        "zip_include_packages": ["scipy", "sklearn", "pandas"],
        "bin_excludes": ["libstdc++.so", "libcrypto.so"],  # removing some big qt5 files that are probably not used by app. suspect this if qt fails
    }
}


# Call the setup function.
setup(
    name="Brainwash",
    version=version,
    description="",
    #packages=find_packages(where="src"),
    #package_dir={"": "src"},
    #include_package_data=True,
    options=options,
    executables=[exe],
    base=base
)

