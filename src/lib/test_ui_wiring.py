"""Minimal pytest-qt smoke tests (offscreen; no full UIsub)."""

from PyQt5 import QtCore, QtWidgets


def test_qt_application_and_label(qtbot):
    label = QtWidgets.QLabel("brainwash")
    qtbot.addWidget(label)
    assert label.text() == "brainwash"


def test_radio_group_updates_checked_button(qtbot):
    group = QtWidgets.QButtonGroup()
    box = QtWidgets.QWidget()
    qtbot.addWidget(box)
    r1 = QtWidgets.QRadioButton("time")
    r2 = QtWidgets.QRadioButton("io")
    group.addButton(r1)
    group.addButton(r2)
    r2.setChecked(True)
    qtbot.wait(10)
    assert group.checkedButton() is r2
    assert r2.isChecked()