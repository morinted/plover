from PyQt5.QtCore import QAbstractTableModel, Qt
from PyQt5.QtWidgets import (
    QDialog,
)

from plover.gui_qt.conversion_failure_dialog_ui import Ui_ConversionFailure
from plover.gui_qt.utils import WindowState

class FailureModel(QAbstractTableModel):

    def __init__(self, failures=[()]):
        super(QAbstractTableModel, self).__init__()
        self.failures = failures

    def columnCount(self, parent=None, *args, **kwargs):
        return len(self.failures[0])

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self.failures)

    def headerData(self, section, orientation, role):
        if orientation != Qt.Horizontal or role != Qt.DisplayRole:
            return None
        if section == 0:
            return _('Steno')
        if section == 1:
            return _('Translation')
        if section == 2:
            return _('Message')

    def data(self, index, role):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        return self.failures[index.row()][index.column()]


class ConversionFailureDialog(QDialog, Ui_ConversionFailure, WindowState):

    def __init__(self, failures, parent=None):
        # Failures is list of tuples
        # (steno, translation, message)
        super(ConversionFailureDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self._model = FailureModel(failures)
        self.tableView.setModel(self._model)
        self.tableView.horizontalHeader().setStretchLastSection(True)
        self.tableView.resizeColumnsToContents()

