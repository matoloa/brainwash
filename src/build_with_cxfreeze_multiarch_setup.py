import sys

import toml  # for reading pyproject.toml
from cx_Freeze import Executable, setup

pyproject = toml.load("../pyproject.toml")
version = pyproject["project"]["version"]

print(f"sys.platform: {sys.platform}")

# "gui" is the modern cx_Freeze 7+ name for Win32GUI; works on all platforms
base = "gui" if sys.platform == "win32" else None

script_path = "main.py"

# pyproject.toml is read at runtime by ui.py (Config.__init__) to get the
# version string.  It is placed at lib/pyproject.toml so the existing search
# list in ui.py ("lib" entry) finds it without any code changes.
# "lib/" copies the whole src/lib directory into build/exe.*/lib/.
include_files = [
    ("../pyproject.toml", "lib/pyproject.toml"),
    "lib/",
]

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
            "sklearn.neighbors.typedefs",
            "sklearn.neighbors.quad_tree",
            "sklearn.tree._utils",
            # PyQt5 extras
            "PyQt5.sip",
            # standard-library modules used at runtime
            "pickle",
            "socket",
            "uuid",
            "importlib",
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
            "pyarrow",  # pandas uses it for Arrow-backed dtypes
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
        "excludes": [
            "tkinter",
            "unittest",
            "pytest",
            "email",
            "http",
            "xml",
            "pydoc",
            "doctest",
            "difflib",
            "ftplib",
            "imaplib",
            "mailbox",
            "nntplib",
            "poplib",
            "smtplib",
            "telnetlib",
            "xmlrpc",
        ],
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
