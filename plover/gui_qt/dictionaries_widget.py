
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFileDialog,
    QTableWidgetItem,
    QWidget,
)

from plover.dictionary.base import dictionaries as dictionary_formats
from plover.oslayer.config import CONFIG_DIR

from plover.gui_qt.dictionaries_widget_ui import Ui_DictionariesWidget
from plover.gui_qt.dictionary_editor import DictionaryEditor
from plover.gui_qt.utils import ToolBar


class DictionariesWidget(QWidget, Ui_DictionariesWidget):

    def __init__(self, engine):
        super(DictionariesWidget, self).__init__()
        self.setupUi(self)
        self._engine = engine
        self._states = []
        self._dictionaries = []
        for action in (
            self.action_Undo,
            self.action_EditDictionaries,
            self.action_RemoveDictionaries,
        ):
            action.setEnabled(False)
        # Toolbar.
        self.layout().addWidget(ToolBar(
            self.action_Undo,
            self.action_EditDictionaries,
            self.action_RemoveDictionaries,
            self.action_AddDictionaries,
            self.action_AddTranslation,
        ))
        self.table.supportedDropActions = self._supported_drop_actions
        self.table.dragEnterEvent = self._drag_enter_event
        self.table.dragMoveEvent = self._drag_move_event
        self.table.dropEvent = self._drop_event

    @staticmethod
    def _display_filename(filename):
        config_dir = os.path.realpath(CONFIG_DIR)
        if not config_dir.endswith(os.sep):
            config_dir += os.sep
        if filename.startswith(config_dir):
            return filename[len(config_dir):]
        home_dir = os.path.expanduser('~/')
        if filename.startswith(home_dir):
            return '~/' + filename[len(home_dir):]
        return filename

    def _update_dictionaries(self, dictionaries,
                             record=True, save=True,
                             scroll=False):
        if dictionaries == self._dictionaries:
            return
        if save:
            self._engine.config = { 'dictionary_file_names': dictionaries }
        if record:
            self._states.append(self._dictionaries)
            self.action_Undo.setEnabled(True)
        self._dictionaries = dictionaries
        self.table.setRowCount(0)
        item = None
        for row, filename in enumerate(dictionaries):
            self.table.insertRow(row)
            item = QTableWidgetItem(self._display_filename(filename))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, item)
        if scroll and item is not None:
            self.table.setCurrentItem(item)

    def _supported_drop_actions(self):
        return Qt.CopyAction | Qt.LinkAction | Qt.MoveAction

    def is_accepted_drag_event(self, event):
        if event.source() == self.table:
            return True
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                # Only support local files.
                if not url.isLocalFile():
                    break
                # And only allow supported extensions.
                filename = url.toLocalFile()
                extension = os.path.splitext(filename)[1].lower()
                if not extension in dictionary_formats:
                    break
            else:
                return True
        return False

    def _drag_enter_event(self, event):
        if self.is_accepted_drag_event(event):
            event.accept()

    def _drag_move_event(self, event):
        if self.is_accepted_drag_event(event):
            event.accept()

    def _drop_event(self, event):
        if not self.is_accepted_drag_event(event):
            return
        dictionaries = list(self._dictionaries)
        dest_item = self.table.itemAt(event.pos())
        if dest_item is None:
            dest_index = self.table.rowCount()
        else:
            dest_index = dest_item.row()
        if event.source() == self.table:
            sources = [
                dictionaries[item.row()]
                for item in self.table.selectedItems()
            ]
        else:
            sources = [
                url.toLocalFile()
                for url in event.mimeData().urls()
            ]
        for filename in sources:
            try:
                source_index = dictionaries.index(filename)
            except ValueError:
                pass
            else:
                if source_index == dest_index:
                    dest_index += 1
                    continue
                del dictionaries[source_index]
                if source_index < dest_index:
                    dest_index -= 1
            dictionaries.insert(dest_index, filename)
            dest_index += 1
        self._update_dictionaries(dictionaries)

    def on_selection_changed(self):
        enabled = bool(self.table.selectedItems())
        for action in (
            self.action_RemoveDictionaries,
            self.action_EditDictionaries,
        ):
            action.setEnabled(enabled)

    def on_undo(self):
        assert self._states
        dictionaries = self._states.pop()
        self.action_Undo.setEnabled(bool(self._states))
        self._update_dictionaries(dictionaries, record=False)

    def _edit(self, dictionaries):
        editor = DictionaryEditor(self._engine, dictionaries, self)
        editor.exec_()

    def on_activate_cell(self, row, col):
        self._edit([self._dictionaries[row]])

    def on_edit_dictionaries(self):
        dictionaries = [self._dictionaries[item.row()]
                        for item in self.table.selectedItems()]
        assert dictionaries
        self._edit(dictionaries)

    def on_remove_dictionaries(self):
        selection = [item.row() for item in self.table.selectedItems()]
        assert selection
        dictionaries = list(self._dictionaries)
        for row in sorted(selection, reverse=True):
            del dictionaries[row]
        self._update_dictionaries(dictionaries)

    def on_add_dictionaries(self):
        filters = ['*' + ext for ext in dictionary_formats]
        new_filenames = QFileDialog.getOpenFileNames(
            self, _('Add dictionaries'), None,
            _('Dictionary Files') + ' (%s)' % ' '.join(filters),
        )[0]
        dictionaries = list(self._dictionaries)
        for filename in new_filenames:
            if filename not in dictionaries:
                dictionaries.append(filename)
        self._update_dictionaries(dictionaries)

    def on_add_translation(self):
        selection = [item.row() for item in self.table.selectedItems()]
        if selection:
            selection.sort()
            dictionary = self._dictionaries[selection[-1]]
        else:
            dictionary = None
        self._engine.command_add_translation.emit(dictionary)
