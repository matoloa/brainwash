# ui_widgets.py
# Extracted custom Qt widgets, dialogs, models, threads, and helper classes
# from ui.py (Phase 0 of ui mixin extraction plan).
#
# These are mostly UI building blocks used by UIsub and some mixins.
# Threads receive uistate/uiplot via constructor; mixins import widgets directly.

from __future__ import annotations

import logging
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

import pandas as pd
import toml
from PyQt5 import QtCore, QtGui, QtWidgets

# Matplotlib (only for MplCanvas)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

# brainwash
import parse
from project_schema import df_projectTemplate

logger = logging.getLogger(__name__)


class StimUaItemDelegate(QtWidgets.QStyledItemDelegate):
    """µA column editor: select-all on open; Enter commits and requests next row."""

    enter_pressed = QtCore.pyqtSignal(int)  # row that was edited

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QtWidgets.QLineEdit):
            # No QDoubleValidator: it can swallow intermediate keystrokes.
            editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        # Select existing value once before the editor is shown so the first
        # key replaces it. Do NOT selectAll on a timer — that races after the
        # first typed digit and makes "20" become "0".
        if isinstance(editor, QtWidgets.QLineEdit) and editor.text():
            editor.selectAll()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress and isinstance(obj, QtWidgets.QLineEdit):
            key = event.key()
            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                # Find model index for this editor via parent table
                table = obj.parent()
                while table is not None and not isinstance(table, QtWidgets.QTableWidget):
                    table = table.parent()
                row = -1
                if table is not None:
                    idx = table.currentIndex()
                    if idx.isValid():
                        row = idx.row()
                self.commitData.emit(obj)
                self.closeEditor.emit(obj, QtWidgets.QAbstractItemDelegate.NoHint)
                if row >= 0:
                    self.enter_pressed.emit(row)
                return True
        return super().eventFilter(obj, event)


class StimTableShortcutFilter(QtCore.QObject):
    """QObject event filter: block group digit shortcuts while stim µA table is focused.

    Must be a real QObject — UIsub (mixin stack) is not a valid installEventFilter target.
    """

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.ShortcutOverride:
            key = event.key()
            if (QtCore.Qt.Key_0 <= key <= QtCore.Qt.Key_9) or key in (
                QtCore.Qt.Key_Period,
                QtCore.Qt.Key_Comma,
                QtCore.Qt.Key_Minus,
            ):
                event.accept()
                return True
        return False


####################################################################
#                             Globals                              #
####################################################################


class Config:
    def __init__(self):
        self.dev_mode = not getattr(sys, "frozen", False) or os.getenv("BRAINWASH_DEBUG", "0") == "1"
        print("\n" * 3 + f"{'Development' if self.dev_mode else 'Deploy'} mode - {time.strftime('%H:%M:%S')}")

        clear = False  # Clear all caches and temporary files at launch
        self.clear_project_folder = clear  # Remove current project folder (datafiles) at launch
        self.clear_cache = clear
        self.clear_timepoints = clear
        self.force_cfg_reset = clear

        self.transient = False  # Block persisting of files

        self.verbose = self.dev_mode  # Now tied to --debug
        self.talkback = not self.dev_mode
        self.hide_experimental = not self.dev_mode
        self.track_widget_focus = False
        self.terminal_space = 372 if self.dev_mode else 100  # pixels reserved for viewing prints
        self.work_space = 646 if self.dev_mode else 0  # pixels reserved for working area

        # get project_name and version number from pyproject.toml
        #
        # _find_file is READONLY-ONLY: used for pyproject.toml (version) and
        # initial probe of bw_cfg.yaml.  The final *writable* bw_cfg_yaml for
        # frozen/AppImage builds is computed below (never inside squashfs).
        #
        # Search order (most-specific first):
        #   1. Frozen build: exe dir — pyproject.toml is copied next to the binary
        #      and under lib/ (not brainwash/, which collides with the Linux
        #      executable name "brainwash").
        #   2. Development: relative paths from source / repo root.
        #   3. Fallback: walk every entry in sys.path (AppImage, editable installs).
        def _find_file(filename: str) -> Path | None:
            # 1. Relative to the executable (frozen) or this source file (dev)
            anchors: list[Path] = []
            if getattr(sys, "frozen", False):
                anchors.append(Path(sys.executable).parent)
            anchors.append(Path(__file__).parent)  # src/brainwash/
            anchors.append(Path(__file__).parent.parent)  # src/
            anchors.append(Path(__file__).parent.parent.parent)  # repo root

            for anchor in anchors:
                for rel in [filename, "lib/" + filename, "brainwash/" + filename]:
                    candidate = anchor / rel
                    if candidate.is_file():
                        return candidate

            # 2. sys.path fallback (AppImage / unusual layouts)
            for entry in sys.path:
                candidate = Path(entry) / filename
                if candidate.is_file():
                    return candidate

            return None

        toml_path = _find_file("pyproject.toml")
        if toml_path is None:
            raise FileNotFoundError("pyproject.toml not found. Searched relative to executable, source file, and all sys.path entries.")
        logger.debug("Config: loading pyproject.toml from %s", toml_path)

        bwcfg_path = _find_file("bw_cfg.yaml")
        if bwcfg_path is None:
            # File doesn't exist yet — place it next to pyproject.toml so it
            # will be found on the next launch (dev/normal case).
            bwcfg_path = toml_path.parent / "bw_cfg.yaml"
            logger.debug("Config: bw_cfg.yaml not found, will create at %s", bwcfg_path)
        else:
            logger.debug("Config: bw_cfg.yaml found at %s", bwcfg_path)

        # Final writable path. For frozen/AppImage: NEVER write inside the
        # read-only squashfs. Priority order matches AppImage spec + XDG:
        #   1. Portable: <AppImage>.config/ sibling directory (if it exists).
        #   2. XDG: ~/.config/brainwash/ (or $XDG_CONFIG_HOME/brainwash/).
        # Non-frozen/dev keeps the _find_file / toml_path.parent location.
        if getattr(sys, "frozen", False):
            appimage_exe = Path(sys.executable)
            portable_dir = appimage_exe.with_name(appimage_exe.name + ".config")
            if portable_dir.is_dir():
                cfg_dir = portable_dir
                logger.info("Config: using portable .config sibling: %s", cfg_dir)
            else:
                xdg_base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
                cfg_dir = xdg_base / "brainwash"
                logger.info("Config: using XDG config dir (will create on write): %s", cfg_dir)
            bwcfg_path = cfg_dir / "bw_cfg.yaml"
            logger.debug("Config: frozen – final writable bw_cfg_yaml=%s", bwcfg_path)
        # else: dev/normal keeps existing location (unchanged)

        pyproject = toml.load(toml_path)
        self.bw_cfg_yaml = str(bwcfg_path)
        self.program_name = pyproject["project"]["name"]
        self.version = pyproject["project"]["version"]


####################################################################
#                       Custom sub-classes                         #
####################################################################


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data=None):
        super(TableModel, self).__init__()
        self._data = data
        # Last user-chosen sort; reapplied in setData so tableUpdate keeps order.
        self._sort_column = None
        self._sort_order = QtCore.Qt.AscendingOrder
        # Optional: fn(column: int, order: Qt.SortOrder) after user/API sort.
        self._sort_changed_callback = None

    def data(self, index, role=None):  # dataCell
        if role is None:
            value = self._data.iloc[index.row(), index.column()]
            return value
        if role == QtCore.Qt.DisplayRole:
            value = self._data.iloc[index.row(), index.column()]
            return str(value)

    def dataRow(self, index, role=None):
        # TODO: return entire selected row
        if role is None:
            value = self._data.iloc[index.row(), :]
            return value

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return str(self._data.columns[section])

            if orientation == QtCore.Qt.Vertical:
                return str(self._data.index[section])

    def _apply_remembered_sort(self) -> None:
        if self._sort_column is None:
            return
        if self._data is None or getattr(self._data, "empty", True):
            return
        if not (0 <= self._sort_column < self._data.shape[1]):
            return
        col = self._data.columns[self._sort_column]
        ascending = self._sort_order == QtCore.Qt.AscendingOrder
        self._data = self._data.sort_values(col, ascending=ascending)

    def setData(self, data: pd.DataFrame = None):
        self.beginResetModel()
        if data is None:
            self._data = pd.DataFrame()
        elif isinstance(data, pd.DataFrame):
            self._data = data
        else:
            return False
        try:
            self._apply_remembered_sort()
        except Exception as e:
            print(f"Error reapplying table sort: {e}")
        self.endResetModel()
        return True

    def sort(self, column, order):
        try:
            self._sort_column = column
            self._sort_order = order
            self.layoutAboutToBeChanged.emit()
            self._apply_remembered_sort()
            self.layoutChanged.emit()
            if self._sort_changed_callback is not None:
                self._sort_changed_callback(column, order)
        except Exception as e:
            print(f"Error sorting table: {e}")


class FileTreeSelectorModel(QtWidgets.QFileSystemModel):  # Paired with a FileTreeSelectorView
    paths_selected = QtCore.pyqtSignal(list)

    def __init__(self, parent=None, root_path="."):
        QtWidgets.QFileSystemModel.__init__(self, None)
        self.root_path = root_path
        self.checks = {}
        self.nodestack = []
        self.parent_index = self.setRootPath(self.root_path)
        self.root_index = self.index(self.root_path)

        self.setFilter(QtCore.QDir.AllEntries | QtCore.QDir.NoDotAndDotDot)
        self.sort(0, QtCore.Qt.SortOrder.AscendingOrder)
        self.directoryLoaded.connect(self._loaded)

    def _loaded(self, path):
        logger.debug("_loaded %s rowCount=%s", self.root_path, self.rowCount(self.parent_index))
        print("_loaded", self.root_path, self.rowCount(self.parent_index))

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role != QtCore.Qt.CheckStateRole:
            return QtWidgets.QFileSystemModel.data(self, index, role)
        else:
            if index.column() == 0:
                return self.checkState(index)

    def flags(self, index):
        return QtWidgets.QFileSystemModel.flags(self, index) | QtCore.Qt.ItemIsUserCheckable

    def checkState(self, index):
        if index in self.checks:
            return self.checks[index]
        else:
            return QtCore.Qt.Unchecked

    def getCheckedPaths(self):
        paths = []
        for k, v in self.checks.items():
            if v == 2:  # Checked
                paths.append(format(self.filePath(k)))
        self.paths_selected.emit(paths)

    def setData(self, index, value, role):
        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            self.checks[index] = value
            logger.debug("setData(): %s", value)
            print("setData(): {}".format(value))
            return True
        return QtWidgets.QFileSystemModel.setData(self, index, value, role)

    def traverseDirectory(self, parentindex, callback=None):
        logger.debug("traverseDirectory()")
        callback(parentindex)
        if self.hasChildren(parentindex):
            path = self.filePath(parentindex)
            it = QtCore.QDirIterator(path, self.filter() | QtCore.QDir.NoDotAndDotDot)
            while it.hasNext():
                childIndex = self.index(it.next())
                self.traverseDirectory(childIndex, callback=callback)
        else:
            print("no children")

    def printIndex(self, index):
        print("model printIndex(): {}".format(self.filePath(index)))


class FileTreeSelectorDialog(QtWidgets.QWidget):
    def __init__(self, parent=None, root_path="."):
        super().__init__(parent)

    def delayedInitForRootPath(self, root_path):
        self.root_path = str(root_path)

        # Model
        self.model = FileTreeSelectorModel(root_path=self.root_path)
        # self.model          = QtWidgets.QFileSystemModel()

        # view
        self.view = QtWidgets.QTreeView()

        self.view.setObjectName("treeView_fileTreeSelector")
        self.view.setWindowTitle("Dir View")  # TODO:  Which title?
        self.view.setSortingEnabled(False)

        # Attach Model to View
        self.view.setModel(self.model)
        self.view.setRootIndex(self.model.parent_index)
        self.view.setAnimated(False)
        self.view.setIndentation(20)
        self.view.setColumnWidth(0, 250)
        self.view.setColumnWidth(1, 100)
        self.view.setColumnWidth(2, 50)
        self.view.setColumnHidden(3, True)

        # Misc
        self.node_stack = []

        # GUI
        windowlayout = QtWidgets.QVBoxLayout()
        windowlayout.addWidget(self.view)
        self.setLayout(windowlayout)

        # QtCore.QMetaObject.connectSlotsByName(self)

    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def on_treeView_fileTreeSelector_clicked(self, index):
        self.model.getCheckedPaths()


class MplCanvas(FigureCanvasQTAgg):
    # graph window, setting parent to None to make it standalone
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
        self.setParent(parent)


class CustomCheckBox(QtWidgets.QCheckBox):
    # Custom checkbox to allow right-click to rename group
    rightClicked = QtCore.pyqtSignal(int)  # Define a new signal that carries an integer

    def __init__(self, group_ID, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_ID = group_ID  # int 1-9

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.rightClicked.emit(self.group_ID)
        else:
            super().mousePressEvent(event)


class GroupRemoveButton(QtWidgets.QToolButton):
    """Far-right × on a group row: double-click removes; hover drives red statusbar."""

    removeRequested = QtCore.pyqtSignal(int)
    hoverEntered = QtCore.pyqtSignal(int, str)  # group_ID, group_name
    hoverLeft = QtCore.pyqtSignal()

    def __init__(self, group_ID: int, group_name: str, parent=None):
        super().__init__(parent)
        self.group_ID = int(group_ID)
        self.group_name = str(group_name)
        self.setObjectName(f"group_remove_{self.group_ID}")
        self.setText("×")
        self.setAutoRaise(True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedSize(22, 22)
        self.setStyleSheet(
            "QToolButton { font-weight: bold; font-size: 14px; padding: 0; border: none; }"
            "QToolButton:hover { color: #d35400; }"  # matches statusbar attention chrome
        )

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.removeRequested.emit(self.group_ID)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        self.hoverEntered.emit(self.group_ID, self.group_name)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hoverLeft.emit()
        super().leaveEvent(event)


class ProgressBarManager:
    def __init__(self, progressBar, total):
        self.progressBar = progressBar
        self.total = total
        print(f"*** Progressbar start: {self.progressBar.value()}")
        print(f"*** Progressbar total: {total}")

    def __enter__(self):
        self.progressBar.setValue(0)
        self.progressBar.setFormat("")
        self.progressBar.setVisible(True)
        self._outer_text = ""
        self._sub_text = ""
        return self

    def __exit__(self, type, value, traceback):
        self.total = 0
        self.progressBar.setFormat("")
        self.progressBar.setVisible(False)

    def update(self, i, task_description):
        if self.total == 0:
            print(
                "*** ERROR: Update request for non-existent task."
            )  # TODO: This scenario should have been prevented by the callers - why isn't it? Related to __exit__ setting it to 0?
            return
        percentage = int((i) * 100 / self.total)
        self.progressBar.setValue(percentage)
        self._outer_text = f"{task_description} {i + 1} / {self.total}:   %p% complete"
        self._sub_text = ""
        self.progressBar.setFormat(self._outer_text)

    def update_sub(self, idx, total):
        """Amend the progress bar format string with sub-step progress (e.g. .ibw file index).
        Does not change the bar value — that is owned by the outer recording-level update()."""
        sub = f"  (reading file {idx + 1} / {total})"
        self.progressBar.setFormat(self._outer_text + sub)

    def set_status(self, text):
        """Append a freeform status string to the outer label without touching the bar value."""
        self.progressBar.setFormat(self._outer_text + f"  ({text})")


class ParseDataThread(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    sub_progress = QtCore.pyqtSignal(int, int)  # (current_file_idx, total_files) within one ibw folder
    status_update = QtCore.pyqtSignal(str)  # freeform status text for post-read phases
    finished = QtCore.pyqtSignal()  # custom signal, decoupled from QThread.finished

    def __init__(self, df_p_to_update, dict_folders, uisub):
        super().__init__()
        self.df_p_to_update = df_p_to_update
        self.dict_folders = dict_folders
        self.uisub = uisub
        self.rows = []
        self.total = len(df_p_to_update)

    def run(self):
        """Parse data from files, persist them as bw parquet:s, and update df_p"""
        try:
            for i, (_, df_proj_row) in enumerate(self.df_p_to_update.iterrows()):
                recording_name = df_proj_row["recording_name"]
                source_path = df_proj_row["path"]
                self.progress.emit(i)
                split_odd_even = self.uisub.uistate.project.checkBox.get("splitOddEven", False)
                split_at_time = self.uisub.uistate.project.lineEdit.get("split_at_time", 0) or None

                def _sub_progress_callback(idx, total):
                    self.sub_progress.emit(idx, total)

                def _status_callback(text):
                    self.status_update.emit(text)

                dict_dfs_raw = parse.source2dfs(
                    source=source_path,
                    gain=self.uisub.uistate.project.lineEdit["import_gain"],
                    split_odd_even=split_odd_even,
                    split_at_time=split_at_time,
                    progress_callback=_sub_progress_callback,
                )
                if not dict_dfs_raw:
                    print(f"Failed to read source file at: {source_path}")
                    continue
                # Keys are either plain channel ints {ch: df} or split tuples {(ch, label): df}.
                # Normalise both into recording_name:df, appending _ch / _label suffixes as needed.
                first_key = next(iter(dict_dfs_raw))
                split_keys = isinstance(first_key, tuple)
                n_channels = len({k[0] for k in dict_dfs_raw} if split_keys else dict_dfs_raw)
                dict_name_df = {}
                for key, df in dict_dfs_raw.items():
                    if split_keys:
                        channel, label = key
                        ch_suffix = f"_ch{channel}" if n_channels > 1 else ""
                        dict_name_df[f"{recording_name}{ch_suffix}_{label}"] = df
                    else:
                        channel = key
                        ch_suffix = f"_ch{channel}" if n_channels > 1 else ""
                        dict_name_df[f"{recording_name}{ch_suffix}"] = df
                for rec, df_raw in dict_name_df.items():
                    logger.debug("ParseDataThread: %s", rec)
                    print(f"ParseDataThread: {rec}")
                    df_proj_new_row = self.uisub.create_recording(df_proj_row, rec, df_raw, status_callback=_status_callback)
                    self.rows.append(df_proj_new_row)
        except Exception as e:
            logger.exception(f"ParseDataThread.run: EXCEPTION: {e}\n{traceback.format_exc()}")
        finally:
            self.finished.emit()


class graphPreloadThread(QtCore.QThread):
    finished = QtCore.pyqtSignal()
    progress = QtCore.pyqtSignal(int)

    def __init__(self, uistate, uiplot, uisub):
        super().__init__()
        self.rows = []
        self.uistate = uistate
        self.uiplot = uiplot
        self.uisub = uisub
        self.df_p = self.uisub.get_df_project()
        self.i = 0

    def run(self):
        try:
            print(f"graphPreloadThread.run: entered, {len(self.uistate.project.list_idx_recs2preload)} recordings")
            df_p = self.df_p.loc[self.uistate.project.list_idx_recs2preload]
            self.uistate.project.list_idx_recs2preload = []
            self.i = 0
            for i, p_row in df_p.iterrows():
                print(f"graphPreloadThread.run: processing {p_row['recording_name']}")
                print("graphPreloadThread.run: calling get_dft")
                dft = self.uisub.get_dft(row=p_row)
                print(f"graphPreloadThread.run: get_dft returned {type(dft)}")
                if dft is None:
                    print(f"graphPreloadThread.run: dft is None for {p_row['recording_name']} (no stims detected), skipping")
                    continue
                print("graphPreloadThread.run: calling get_dfmean")
                dfmean = self.uisub.get_dfmean(row=p_row)
                print("graphPreloadThread.run: calling get_dffilter")
                _ = self.uisub.get_dffilter(row=p_row)
                print("graphPreloadThread.run: calling get_dfoutput")
                is_pp = self.uistate.experiment.experiment_type == "PP"
                if self.uistate.project.checkBox["paired_stims"] and not is_pp:
                    dfoutput = self.uisub.get_dfdiff(row=p_row)
                else:
                    dfoutput = self.uisub.get_dfoutput(row=p_row)
                print(f"graphPreloadThread.run: get_dfoutput returned {type(dfoutput)}")
                if dfoutput is None:
                    print(f"graphPreloadThread.run: dfoutput is None, skipping this recording")
                    continue
                print(f"graphPreloadThread, {p_row['recording_name']} calls uiplot.addRow() dfoutput columns: {dfoutput.columns}")
                self.uiplot.addRow(p_row=p_row.to_dict(), dft=dft, dfmean=dfmean, dfoutput=self.uisub.V2mV(dfoutput))
                self.progress.emit(i)
                self.i += 1
                print(f"Preloaded {p_row['recording_name']}")
        except Exception as e:
            logger.exception(f"graphPreloadThread.run: EXCEPTION: {e}\n{traceback.format_exc()}")
        finally:
            self.finished.emit()


################################################################
#        Dialog and table classes                              #
################################################################


class Ui_Dialog(QtWidgets.QWidget):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(1105, 525)
        self.buttonBox = QtWidgets.QDialogButtonBox(Dialog)
        self.buttonBox.setGeometry(QtCore.QRect(930, 480, 161, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.widget = FileTreeSelectorDialog(Dialog)
        self.widget.setGeometry(QtCore.QRect(10, 10, 451, 501))
        self.widget.setObjectName("widget")
        self.tableView = QtWidgets.QTableView(Dialog)
        self.tableView.setGeometry(QtCore.QRect(570, 10, 521, 461))
        self.tableView.setObjectName("tableView")

        self.retranslateUi(Dialog)
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Dialog"))


class InputDialogPopup(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.input = QtWidgets.QLineEdit(self)
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.input)
        layout.addWidget(self.buttonBox)

    def showInputDialog(self, title, query):
        self.setWindowTitle(title)
        self.input.setPlaceholderText(query)
        self.setFixedSize(300, 150)  # Set the fixed width and height of the dialog
        result = self.exec_()
        text = self.input.text()
        if result == QtWidgets.QDialog.Accepted:
            print(f"You entered: {text}")
            return text


class ConfirmDialog(QtWidgets.QDialog):
    """Confirmation dialog with OK and Cancel buttons.
    Usage:
        dlg = ConfirmDialog(title='Confirm', message='Are you sure?')
        ok = dlg.showConfirmDialog()
        # ok is True when user pressed OK, False otherwise
    """

    def __init__(self, title: str = "Confirm", message: str = "Are you sure?"):
        super().__init__()
        self.setWindowTitle(title)
        self.label = QtWidgets.QLabel(message, self)
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.buttonBox)

    def showConfirmDialog(self, title: str | None = None, message: str | None = None) -> bool:
        """Show the dialog modally. Returns True for OK, False for Cancel."""
        if title is not None:
            self.setWindowTitle(title)
        if message is not None:
            self.label.setText(message)
        result = self.exec_()
        return result == QtWidgets.QDialog.Accepted


def confirm(title: str = "Confirm", message: str = "Are you sure?") -> bool:
    """Convenience function: show confirmation dialog and return bool result."""
    dlg = ConfirmDialog(title=title, message=message)
    return dlg.showConfirmDialog()


class TableProjSub(QtWidgets.QTableView):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            file_urls = [url.toLocalFile() for url in event.mimeData().urls()]
            print("Files dropped:", file_urls)
            # Handle the dropped files here
            dfAdd = df_projectTemplate()
            dfAdd["path"] = file_urls  # needs to be first, as it sets the number of rows
            dfAdd["host"] = str(self.parent.fqdn)
            dfAdd["filter"] = "voltage"
            # NTH: more intelligent default naming; lowest level unique name?
            # For now, use name + lowest level folder
            names = []
            duplicates = []  # remove these from dfAdd
            df_p_paths = self.parent.get_df_project()["path"].values if hasattr(self.parent, "get_df_project") else self.parent.df_project["path"].values
            for i in file_urls:
                # check if file is already in df_project
                if i in df_p_paths:
                    print(f"File {i} already in df_project")
                    duplicates.append(i)
                else:
                    names.append(os.path.basename(os.path.dirname(i)) + "_" + os.path.basename(i))
            if not names:
                print("No new files to add.")
                return
            dfAdd = dfAdd.drop(dfAdd[dfAdd["path"].isin(duplicates)].index)
            dfAdd["recording_name"] = names
            # v0.16_n: _migrate_hierarchy called inside parent.addData() -> set_df_project()
            self.parent.addData(dfAdd)
            event.acceptProposedAction()
        else:
            event.ignore()


class Filetreesub(Ui_Dialog):
    def __init__(self, dialog, parent=None, folder="."):
        super(Filetreesub, self).__init__()
        self.setupUi(dialog)
        self.parent = parent
        logger.debug("Filetreesub init")
        print(" - Filetreesub init")

        self.ftree = self.widget
        # set root_path for file tree model
        self.ftree.delayedInitForRootPath(folder)
        # self.ftree.model.parent_index   = self.ftree.model.setRootPath(projects_folder)
        # self.ftree.model.root_index     = self.ftree.model.index(projects_folder)

        # Dataframe to add
        self.names = []
        self.dfAdd = df_projectTemplate()

        self.buttonBoxAddGroup = QtWidgets.QDialogButtonBox(dialog)
        self.buttonBoxAddGroup.setGeometry(QtCore.QRect(470, 20, 91, 491))
        self.buttonBoxAddGroup.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.buttonBoxAddGroup.setOrientation(QtCore.Qt.Vertical)
        self.buttonBoxAddGroup.setStandardButtons(QtWidgets.QDialogButtonBox.NoButton)
        self.buttonBoxAddGroup.setObjectName("buttonBoxAddGroup")

        self.ftree.view.clicked.connect(self.widget.on_treeView_fileTreeSelector_clicked)
        self.ftree.model.paths_selected.connect(self.pathsSelectedUpdateTable)
        self.buttonBox.accepted.connect(self.addDf)

        self.tablemodel = TableModel(self.dfAdd)
        self.tableView.setModel(self.tablemodel)

    def addDf(self):
        self.parent.slotAddDfData(self.dfAdd)

    def pathsSelectedUpdateTable(self, paths):
        # TODO: Extract host and group
        dfAdd = df_projectTemplate()
        dfAdd["path"] = paths
        dfAdd["host"] = str(self.parent.fqdn)
        dfAdd["filter"] = "voltage"
        self.tablemodel.setData(dfAdd)
        # NTH: more intelligent default naming; lowest level unique name?
        # For now, use name + lowest level folder
        names = []
        for i in paths:
            names.append(os.path.basename(os.path.dirname(i)) + "_" + os.path.basename(i))
        dfAdd["recording_name"] = names
        # v0.16_n note: hierarchy migration happens downstream in set_df_project() via addData
        self.dfAdd = dfAdd
        # TODO: Add a loop that prevents duplicate names by adding a number until it becomes unique
        # format tableView
        header = self.tableView.horizontalHeader()
        self.tableView.setColumnHidden(0, True)  # host
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # path
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)  # name
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)  # group
        self.tableView.update()
