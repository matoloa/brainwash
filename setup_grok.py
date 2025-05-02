import sys
import os
import toml
from cx_Freeze import setup, Executable


pyproject = toml.load("pyproject.toml")
version = pyproject['project']['version']
description = pyproject['project']['description']
# Base setting for GUI applications (hides console on Windows)
base = "Win32GUI" if sys.platform == "win32" else None

# Define the main executable
executables = [
    Executable(
        script="src/main.py",
        base=base,
        target_name="MyApp",
        icon="icon.ico" if sys.platform == "win32" else None  # Optional: Add an .ico file for Windows
    )
]

# Packages to include (ensure all dependencies are bundled)
packages = [
    "PyQt5",
    "pandas",
    "sklearn",
    "seaborn",
    "numpy",
    "scipy",
    "matplotlib",
]

# Include additional files (e.g., Qt plugins, resources)
include_files = [("README.md", "README.md"), ("pyproject.toml", "pyproject.toml"), "src/lib/"]

try:
    from cx_Freeze.hooks import get_qt_plugins_paths
except ImportError:
    get_qt_plugins_paths = None

get_qt_plugins_paths = None
if get_qt_plugins_paths:
    # Inclusion of extra plugins (since cx_Freeze 6.8b2)
    # cx_Freeze automatically imports the following plugins depending on the
    # module used, but suppose we need the following:
    include_files += get_qt_plugins_paths("PyQt5", "multimedia")


if sys.platform == "win32":
    # Include PyQt5 plugins and DLLs for Windows
    from PyQt5.QtCore import QLibraryInfo
    qt_plugins_path = QLibraryInfo.location(QLibraryInfo.PluginsPath)
    include_files.extend([
        (os.path.join(qt_plugins_path, "styles"), "styles"),
        (os.path.join(qt_plugins_path, "imageformats"), "imageformats"),
        (os.path.join(qt_plugins_path, "platforms"), "platforms"),
    ])
elif sys.platform == "darwin":
    # Include PyQt5 frameworks for macOS
    include_files.append(("PyQt5/Qt/plugins", "PyQt5/Qt/plugins"))

# Build options for cx_Freeze
build_exe_options = {
    "packages": packages,
    "include_files": include_files,
    "excludes": ["tkinter", "unittest", "email", "http", "xml", "pydoc"],  # Exclude unnecessary packages to reduce size
    "include_msvcr": True if sys.platform == "win32" else False,  # Include MSVC runtime for Windows
    "optimize": 2,  # Optimize bytecode
}

# MSI options for Windows installer
bdist_msi_options = {
    "upgrade_code": "{YOUR-UPGRADE-CODE-GUID}",  # Generate a unique GUID for your app
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFilesFolder]\MyApp",
}

# macOS app bundle options
bdist_mac_options = {
    "iconfile": "icon.icns",  # Optional: Add an .icns file for macOS
    "bundle_name": "MyApp",
}

# Setup configuration
setup(
    name="brainwash",
    version=version,
    description=description,
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
        "bdist_mac": bdist_mac_options,
    },
    executables=executables,
)