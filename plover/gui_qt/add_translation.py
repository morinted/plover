
from collections import namedtuple

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import (
    QDialog,
)

from plover.steno import normalize_steno
from plover.translation import escape_translation, unescape_translation

from plover.gui_qt.add_translation_ui import Ui_AddTranslation
from plover.gui_qt.engine import StartingStrokeState
from plover.gui_qt.utils import WindowState


class AddTranslation(QDialog, Ui_AddTranslation, WindowState):

    ROLE = 'add_translation'

    EngineState = namedtuple('EngineState', 'dictionary_filter translator starting_stroke')

    def __init__(self, engine):
        super(AddTranslation, self).__init__()
        self.setupUi(self)
        self._engine = engine
        engine.config_changed.connect(self.on_config_changed)
        self.on_config_changed(engine.config)
        self.installEventFilter(self)
        self.strokes.installEventFilter(self)
        self.translation.installEventFilter(self)
        with engine:
            self._original_state = self.EngineState(None,
                                                    engine.translator_state,
                                                    engine.starting_stroke_state)
            engine.translator_state = None
            self._strokes_state = self.EngineState(self._strokes_dictionary_filter,
                                                   engine.translator_state,
                                                   StartingStrokeState(True, False))
            engine.translator_state = None
            self._translations_state = self.EngineState(None,
                                                        engine.translator_state,
                                                        StartingStrokeState(True, False))
        self._engine_state = self._original_state
        self._focus = None
        self.restore_state()
        self.finished.connect(self.save_state)

    def eventFilter(self, watched, event):
        if watched == self and event.type() == QEvent.ActivationChange:
            if not self.isActiveWindow():
                self._unfocus_strokes()
                self._unfocus_translation()
            return False
        if event.type() != QEvent.FocusIn:
            return False
        if watched == self.strokes:
            self._focus_strokes()
        elif watched == self.translation:
            self._focus_translation()
        return False

    def _set_engine_state(self, state):
        with self._engine as engine:
            prev_state = self._engine_state
            if prev_state is not None and prev_state.dictionary_filter is not None:
                engine.remove_dictionary_filter(prev_state.dictionary_filter)
            engine.translator_state = state.translator
            engine.starting_stroke_state = state.starting_stroke
            if state.dictionary_filter is not None:
                engine.add_dictionary_filter(state.dictionary_filter)
            self._engine_state = state

    @staticmethod
    def _strokes_dictionary_filter(key, value):
        # Only allow translations with special entries. Do this by looking for
        # braces but take into account escaped braces and slashes.
        escaped = value.replace('\\\\', '').replace('\\{', '')
        special = '{#'  in escaped or '{PLOVER:' in escaped
        return not special

    def _focus_strokes(self):
        if self._focus == 'strokes':
            return
        self._unfocus_translation()
        self._set_engine_state(self._strokes_state)
        self._focus = 'strokes'

    def _unfocus_strokes(self):
        if self._focus != 'strokes':
            return
        self._set_engine_state(self._original_state)
        self._focus = None

    def _focus_translation(self):
        if self._focus == 'translation':
            return
        self._unfocus_strokes()
        self._set_engine_state(self._translations_state)
        self._focus = 'translation'

    def _unfocus_translation(self):
        if self._focus != 'translation':
            return
        self._set_engine_state(self._original_state)
        self._focus = None

    def _strokes(self):
        strokes = self.strokes.text().replace('/', ' ').split()
        if not strokes:
            return ()
        return normalize_steno('/'.join(strokes))

    def _translation(self):
        translation = self.translation.text().strip()
        return unescape_translation(translation)

    def on_config_changed(self, config_update):
        opacity = config_update.get('translation_frame_opacity')
        if opacity is None:
            return
        assert 0 <= opacity <= 100
        self.setWindowOpacity(opacity / 100.0)

    def on_strokes_edited(self):
        strokes = self._strokes()
        if strokes:
            translation = self._engine.raw_lookup(strokes)
            strokes = '/'.join(strokes)
            if translation is not None:
                fmt = _('{strokes} maps to "{translation}"')
                translation = escape_translation(translation)
            else:
                fmt = _('{strokes} is not in the dictionary')
            info = fmt.format(strokes=strokes, translation=translation)
        else:
            info = ''
        self.strokes_info.setText(info)

    def on_translation_edited(self):
        translation = self._translation()
        if translation:
            strokes = self._engine.reverse_lookup(translation)
            translation = escape_translation(translation)
            if strokes:
                fmt = _('"{translation}" is mapped from {strokes}')
                strokes = ', '.join('/'.join(x) for x in strokes)
            else:
                fmt = _('"{translation}" is not in the dictionary')
            info = fmt.format(strokes=strokes, translation=translation)
        else:
            info = ''
        self.translation_info.setText(info)

    def accept(self):
        strokes = self._strokes()
        translation = self._translation()
        if strokes and translation:
            self._engine.add_translation(strokes, translation)
        super(AddTranslation, self).accept()

    def reject(self):
        self._set_engine_state(self._original_state)
        super(AddTranslation, self).reject()
