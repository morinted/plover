
from collections import namedtuple

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import (
    QDialog,
)


from plover.gui_qt.add_translation_widget import AddTranslationWidget
from plover.gui_qt.add_translation_dialog_ui import Ui_AddTranslationDialog
from plover.gui_qt.utils import WindowState

class AddTranslationDialog(QDialog, Ui_AddTranslationDialog, WindowState):

    ROLE = 'add_translation'

    def __init__(self, engine, dictionary=None):
        super(AddTranslationDialog, self).__init__()
        self.setupUi(self)

        add_translation = AddTranslationWidget(engine, dictionary)
        self.layout().replaceWidget(self.add_translation, add_translation)
        self.add_translation = add_translation
        add_translation.strokes.setFocus()

        self.installEventFilter(self)

        engine.signal_connect('config_changed', self.on_config_changed)
        self.on_config_changed(engine.config)

        self.finished.connect(self.save_state)
        self.restore_state()

    def eventFilter(self, watched, event):
        if watched == self and event.type() == QEvent.ActivationChange:
            if not self.isActiveWindow():
                self.add_translation.unfocus()
        return False

    def on_config_changed(self, config_update):
        opacity = config_update.get('translation_frame_opacity')
        if opacity is None:
            return
        assert 0 <= opacity <= 100
        self.setWindowOpacity(opacity / 100.0)

    def accept(self):
        self.add_translation.save_entry()
        super(AddTranslationDialog, self).accept()

    def reject(self):
        self.add_translation.reject()
        super(AddTranslationDialog, self).reject()
