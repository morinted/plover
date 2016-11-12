
from collections import namedtuple

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import (
    QDialog,
    QWidget)

from plover.misc import expand_path, shorten_path
from plover.steno import normalize_steno
from plover.engine import StartingStrokeState
from plover.translation import escape_translation, unescape_translation

from plover.gui_qt.add_translation_widget_ui import Ui_AddTranslationWidget


class AddTranslationWidget(QWidget, Ui_AddTranslationWidget):

    EngineState = namedtuple('EngineState', 'dictionary_filter translator starting_stroke')

    def __init__(self, engine, dictionary=None):
        super(AddTranslationWidget, self).__init__()
        self.setupUi(self)
        self._engine = engine
        dictionaries = [d.get_path() for d in engine.dictionaries.dicts]
        self.dictionary.addItems(shorten_path(d) for d in dictionaries)

        self.strokes.installEventFilter(self)
        self.translation.installEventFilter(self)

        if dictionary is None:
            self.dictionary.setCurrentIndex(0)
        else:
            assert dictionary in dictionaries
            self.dictionary.setCurrentIndex(dictionaries.index(dictionary))

        with engine:
            self._original_state = self.EngineState(None,
                                                    engine.translator_state,
                                                    engine.starting_stroke_state)
            engine.clear_translator_state()
            self._strokes_state = self.EngineState(self._dictionary_filter,
                                                   engine.translator_state,
                                                   StartingStrokeState(True, False))
            engine.clear_translator_state()
            self._translations_state = self.EngineState(None,
                                                        engine.translator_state,
                                                        StartingStrokeState(True, False))

        self._engine_state = self._original_state
        self._focus = None
        self._dictionaries = dictionaries
        engine.signal_connect('config_changed', self.on_config_changed)

    def on_config_changed(self, config_update):
        # The dictionary list may change.
        if 'dictionary_file_names' in config_update:
            dictionaries = config_update['dictionary_file_names']
            if dictionaries == self._dictionaries:
                return
            # Grab the user's previous selection.
            selected_dictionary = self.dictionary.currentText()
            # Repopulate the combobox.
            self.dictionary.clear()
            self.dictionary.addItems(
                shorten_path(d) for d in reversed(dictionaries))
            # If the previously-selected dictionary is still in the list,
            # select it.
            goal_index = self.dictionary.findText(selected_dictionary)
            if goal_index >= 0:
                self.dictionary.setCurrentIndex(goal_index)

    def eventFilter(self, watched, event):
        if event.type() != QEvent.FocusIn:
            return False
        if watched == self.strokes:
            self.focus_strokes()
        elif watched == self.translation:
            self.focus_translation()
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
    def _dictionary_filter(key, value):
        # Only allow translations with special entries. Do this by looking for
        # braces but take into account escaped braces and slashes.
        escaped = value.replace('\\\\', '').replace('\\{', '')
        special = '{#'  in escaped or '{PLOVER:' in escaped
        return not special

    def unfocus(self):
        self._unfocus_strokes()
        self._unfocus_translation()

    def focus_strokes(self):
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

    def focus_translation(self):
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

    def save_entry(self):
        self.unfocus()
        strokes = self._strokes()
        translation = self._translation()
        if strokes and translation:
            dictionary = expand_path(self.dictionary.currentText())
            old_translation = (
                self._engine.dictionaries.get_by_path(dictionary)
                    .pop(strokes, None)
            )
            self._engine.add_translation(strokes, translation,
                                         dictionary=dictionary)
            return (dictionary, strokes, (old_translation, translation))

    def reject(self):
        self.unfocus()
        self._set_engine_state(self._original_state)
