import os
import sys

import toml  # for reading pyproject.toml
from cx_Freeze import Executable, setup

pyproject = toml.load("../pyproject.toml")
version = pyproject["project"]["version"]

print(f"sys.platform: {sys.platform}")

# "gui" is the modern cx_Freeze 7+ name for Win32GUI; works on all platforms
base = "gui" if sys.platform == "win32" else None

script_path = "main.py"

# ---------------------------------------------------------------------------
# Locate the venv site-packages so we can reference package directories for
# manual include_files entries (needed for packages whose DLLs / data live
# outside the package directory itself, e.g. pyarrow.libs).
# ---------------------------------------------------------------------------
_venv_site = None
for _p in sys.path:
    if "site-packages" in _p and os.path.isdir(_p):
        _venv_site = _p
        break
if _venv_site is None:
    raise RuntimeError("Could not locate site-packages in sys.path")

print(f"site-packages: {_venv_site}")

# pyproject.toml is read at runtime by ui.py (Config.__init__) to get the
# version string.  It is placed at lib/pyproject.toml so the existing search
# list in ui.py ("lib" entry) finds it without any code changes.
# "lib/" copies the whole src/lib directory into build/exe.*/lib/.
include_files = [
    ("../pyproject.toml", "lib/pyproject.toml"),
    "lib/",
]

# ---------------------------------------------------------------------------
# pyarrow ships its Arrow C++ DLLs inside pyarrow/ itself on Windows (they
# are resolved via os.add_dll_directory in pyarrow/__init__.py).  cx_Freeze
# copies the whole package directory, so those DLLs are already included.
#
# However pyarrow also has a sibling directory "pyarrow.libs" that may
# contain MSVC runtime DLLs (msvcp140.dll etc.).  We copy it next to the
# pyarrow package directory so the relative path in __init__.py still works.
# ---------------------------------------------------------------------------
_pyarrow_libs_src = os.path.join(_venv_site, "pyarrow.libs")
if os.path.isdir(_pyarrow_libs_src):
    # In the frozen layout packages end up under  lib/<pkg>/  so pyarrow.libs
    # must land at  lib/pyarrow.libs/  to satisfy the  ../pyarrow.libs  lookup
    # in pyarrow/__init__.py.
    include_files.append((_pyarrow_libs_src, "lib/pyarrow.libs"))
    print(f"Including pyarrow.libs from: {_pyarrow_libs_src}")
else:
    print("pyarrow.libs not found – skipping (DLLs assumed to be inside pyarrow/)")

exe = Executable(
    script=script_path,
    base=base,
    target_name="brainwash",
)

options = {
    "build_exe": {
        # ------------------------------------------------------------------ #
        # includes: individual modules cx_Freeze may miss via static analysis #
        # ------------------------------------------------------------------ #
        "includes": [
            # matplotlib backends / font machinery
            "matplotlib.backends.backend_qt5agg",
            "matplotlib.backends.backend_agg",
            "matplotlib.figure",
            "matplotlib.font_manager",
            "matplotlib.ticker",
            "matplotlib.colors",
            "matplotlib.lines",
            "matplotlib.style",
            # scipy sub-modules used directly
            "scipy.signal",
            "scipy.stats",
            "scipy.linalg",
            "scipy.sparse",
            "scipy.optimize",
            # sklearn internals that are loaded dynamically
            "sklearn.utils._cython_blas",
            "sklearn.utils._typedefs",
            "sklearn.neighbors._quad_tree",
            "sklearn.tree._utils",
            # PyQt5 extras
            "PyQt5.sip",
            # standard-library modules used at runtime
            "pickle",
            "socket",
            "uuid",
            "importlib",
            # xml / defusedxml: pulled in eagerly by matplotlib and pandas.io
            # at import time — must NOT be excluded.
            "xml.etree.ElementTree",
            "xml.parsers.expat",
            "defusedxml",
            "defusedxml.ElementTree",
        ],
        # ------------------------------------------------------------------ #
        # packages: whole packages — all submodules are pulled in             #
        # ------------------------------------------------------------------ #
        "packages": [
            # Qt
            "PyQt5",
            # numeric / scientific
            "numpy",
            "scipy",
            "scipy_openblas64",  # scipy's bundled OpenBLAS — required at runtime
            "sklearn",
            # plotting
            "matplotlib",
            "seaborn",
            # data
            "pandas",
            "pyarrow",  # pandas uses it for Parquet I/O and Arrow-backed dtypes
            # xml safety wrapper — pandas.io.xml imports it eagerly
            "defusedxml",
            # I/O helpers
            "pyabf",
            "igor2",
            # parallelism / progress
            "joblib",
            "tqdm",
            # config / serialisation
            "toml",
            "yaml",  # PyYAML
            "requests",
        ],
        # ------------------------------------------------------------------ #
        # excludes: only things that are genuinely never needed               #
        # ------------------------------------------------------------------ #
        # NOTE: do NOT exclude "xml" or "xmlrpc" here.
        #   • xml.etree.ElementTree is pulled in at import time by matplotlib
        #     and by pandas.io (via pandas.io.xml / defusedxml).
        #   • xmlrpc is pulled in by some stdlib modules at init time.
        # Excluding them causes an immediate ModuleNotFoundError on startup.
        "excludes": [
            # tkinter: desktop GUI toolkit, never used
            "tkinter",
            # pytest: test runner, not needed at runtime
            "pytest",
            # doctest: pulled in by nothing we ship
            "doctest",
            # network protocol modules that nothing in our stack imports:
            "ftplib",
            "imaplib",
            "mailbox",
            "nntplib",
            "poplib",
            "smtplib",
            "telnetlib",
            # NOTE: do NOT exclude any of the following — they are pulled in
            # eagerly at import time by scipy, requests, or other packages:
            #   unittest  — scipy._lib._testutils imports it unconditionally
            #   email     — scipy / requests pull it in at import time
            #   http      — requests pulls http.client / http.cookiejar
            #   pydoc     — scipy._lib._docscrape imports it
            #   difflib   — scipy._lib._docscrape imports it
        ],
        # ------------------------------------------------------------------ #
        # path_excludes / zip_exclude_packages                                #
        # Trim test suites and heavyweight unused Qt sub-libraries to keep    #
        # the artefact closer to the previous ~340 MB baseline.               #
        # ------------------------------------------------------------------ #
        # cx_Freeze copies whole package trees; we strip known-large test
        # directories by post-processing them in the build hook below.
        "include_files": include_files,
        "include_msvcr": True,
    }
}

setup(
    name="brainwash",
    version=version,
    description="",
    options=options,
    executables=[exe],
)

# ---------------------------------------------------------------------------
# Post-build: remove test / benchmark / example directories and other bloat
# that cx_Freeze copies verbatim from site-packages.
# Run automatically when this script is executed as   python setup.py build
# (cx_Freeze calls setup(), which triggers the build and then returns here).
# ---------------------------------------------------------------------------
import glob as _glob
import shutil


def _remove_bloat(build_root: str) -> None:
    """
    Delete known-unnecessary subdirectories from a cx_Freeze build tree to
    reduce the final artefact size.

    Targets:
      • */tests/ and */test/ directories inside every copied package
      • PyQt5 bindings stubs directory (not needed at runtime)
      • Unused heavy Qt5 DLLs (Qt5Quick*, Qt5Location, Qt5Bluetooth, …)
    """
    removed_bytes = 0

    def _rm(path: str) -> None:
        nonlocal removed_bytes
        if not os.path.exists(path):
            return
        sz = sum(
            os.path.getsize(os.path.join(r, f))
            for r, _, fs in os.walk(path)
            for f in fs
        )
        shutil.rmtree(path, ignore_errors=True)
        removed_bytes += sz
        print(f"  removed {sz / 1e6:.1f} MB  {os.path.relpath(path, build_root)}")

    # ---- test directories -----------------------------------------------
    for pattern in ("tests", "test", "_test", "benchmarks", "examples"):
        for match in _glob.glob(
            os.path.join(build_root, "**", pattern), recursive=True
        ):
            if os.path.isdir(match):
                _rm(match)

    # ---- PyQt5 bindings stubs (needed only for PyQt5 tooling, not runtime) -
    for match in _glob.glob(
        os.path.join(build_root, "**", "PyQt5", "bindings"), recursive=True
    ):
        _rm(match)

    # ---- Unused Qt5 DLLs ------------------------------------------------
    # We use: Core, Gui, Widgets, PrintSupport, Svg, Xml, OpenGL, WinExtras
    # Everything below is safe to drop for a desktop data-analysis app.
    _unused_qt_dlls = {
        "Qt5Bluetooth.dll",
        "Qt5DBus.dll",
        "Qt5Designer.dll",
        "Qt5Help.dll",
        "Qt5Location.dll",
        "Qt5Multimedia.dll",
        "Qt5MultimediaWidgets.dll",
        "Qt5Nfc.dll",
        "Qt5Positioning.dll",
        "Qt5PositioningQuick.dll",
        "Qt5Qml.dll",
        "Qt5QmlModels.dll",
        "Qt5QmlWorkerScript.dll",
        "Qt5Quick.dll",
        "Qt5Quick3D.dll",
        "Qt5Quick3DAssetImport.dll",
        "Qt5Quick3DRender.dll",
        "Qt5Quick3DRuntimeRender.dll",
        "Qt5Quick3DUtils.dll",
        "Qt5QuickControls2.dll",
        "Qt5QuickParticles.dll",
        "Qt5QuickShapes.dll",
        "Qt5QuickTemplates2.dll",
        "Qt5QuickTest.dll",
        "Qt5QuickWidgets.dll",
        "Qt5RemoteObjects.dll",
        "Qt5Sensors.dll",
        "Qt5SerialPort.dll",
        "Qt5Sql.dll",
        "Qt5Test.dll",
        "Qt5TextToSpeech.dll",
        "Qt5WebChannel.dll",
        "Qt5WebSockets.dll",
        "Qt5WebView.dll",
        "Qt5XmlPatterns.dll",
    }
    qt5_bin = os.path.join(build_root, "lib", "PyQt5", "Qt5", "bin")
    if not os.path.isdir(qt5_bin):
        # cx_Freeze sometimes flattens everything into the exe dir
        qt5_bin = os.path.join(build_root, "PyQt5", "Qt5", "bin")
    for dll in _unused_qt_dlls:
        p = os.path.join(qt5_bin, dll)
        if os.path.isfile(p):
            sz = os.path.getsize(p)
            os.remove(p)
            removed_bytes += sz
            print(f"  removed {sz / 1e6:.1f} MB  PyQt5/Qt5/bin/{dll}")

    print(f"Post-build cleanup freed {removed_bytes / 1e6:.1f} MB total.")


# Detect the build output directory (cx_Freeze writes to build/exe.<platform>/)
_build_base = os.path.join(os.path.dirname(__file__), "..", "build")
if os.path.isdir(_build_base):
    _candidates = sorted(
        [
            d
            for d in os.listdir(_build_base)
            if d.startswith("exe.") and os.path.isdir(os.path.join(_build_base, d))
        ],
        reverse=True,  # newest first if multiple exist
    )
    if _candidates:
        _build_dir = os.path.join(_build_base, _candidates[0])
        print(f"\nPost-build cleanup in: {_build_dir}")
        _remove_bloat(_build_dir)
    else:
        print("No exe.* build directory found — skipping post-build cleanup.")
else:
    print("No build/ directory found — skipping post-build cleanup.")
