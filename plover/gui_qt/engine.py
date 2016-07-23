# Python 2/3 compatibility.
from __future__ import print_function

from collections import namedtuple
from functools import wraps
import threading

# Python 2/3 compatibility.
from six import PY3
# Note: six.move is not used as it confuses py2app...
if PY3:
    from queue import Queue
else:
    from Queue import Queue

from PyQt5 import QtCore

from plover.app import StenoEngine, init_engine, update_engine
from plover.oslayer.keyboardcontrol import KeyboardEmulation
from plover.config import copy_default_dictionaries
from plover.machine.registry import machine_registry
from plover import log


StartingStrokeState = namedtuple('StartingStrokeState',
                                 'attach capitalize')


def with_lock(func):
    # To keep __doc__/__name__ attributes of the initial function.
    @wraps(func)
    def _with_lock(self, *args, **kwargs):
        with self._lock:
            return func(self, *args, **kwargs)
    return _with_lock


class Engine(QtCore.QThread):

    # Signals.
    command_add_translation = QtCore.pyqtSignal()
    command_configure = QtCore.pyqtSignal()
    command_lookup = QtCore.pyqtSignal()
    stroke = QtCore.pyqtSignal(QtCore.QVariant)
    translation = QtCore.pyqtSignal(QtCore.QVariant, QtCore.QVariant)
    machine_state_changed = QtCore.pyqtSignal(str, str)
    output_changed = QtCore.pyqtSignal(bool)
    config_changed = QtCore.pyqtSignal(QtCore.QVariant)

    def __init__(self, config):
        super(Engine, self).__init__()
        self._config = config
        self._is_running = False
        self._machine_state = None
        self._queue = Queue()
        self._lock = threading.RLock()
        self._engine = StenoEngine(thread_hook=self._same_thread_hook)
        self._engine.set_output(self)
        self._engine.add_callback(self._state_callback)
        self._keyboard_control = KeyboardEmulation()

    def __enter__(self):
        self._lock.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._lock.__exit__(exc_type, exc_value, traceback)

    def _in_engine_thread(self):
        return self.currentThread() == self

    def _same_thread_hook(self, func, *args, **kwargs):
        if self._in_engine_thread():
            func(*args, **kwargs)
        else:
            self._queue.put((func, args, kwargs))

    def quit(self):
        self._same_thread_hook(self._quit)

    def run(self):
        while True:
            func, args, kwargs = self._queue.get()
            try:
                with self._lock:
                    if func(*args, **kwargs):
                        break
            except Exception:
                log.error('engine %s failed', func.__name__[1:], exc_info=True)
        self._engine.destroy()

    def _start(self):
        copy_default_dictionaries(self._config)
        init_engine(self._engine, self._config)
        self.config_changed.emit(self._config.as_dict())

    def _update_config(self, **kwargs):
        original_config = self._config.as_dict()
        self._config.update(**kwargs)
        new_config = self._config.as_dict()
        config_update = {
            option: value
            for option, value in new_config.items()
            if value != original_config[option]
        }
        update_engine(self._engine, self._config)
        self.config_changed.emit(config_update)

    def _reset_machine(self):
        update_engine(self._engine, self._config, reset_machine=True)

    def _quit(self):
        return True

    def _toggle_output(self):
        self._engine.set_is_running(not self._is_running)

    def _set_output(self, enabled):
        self._engine.set_is_running(enabled)

    @with_lock
    def _state_callback(self, machine_state):
        is_running = self._engine.is_running
        if machine_state is not None and machine_state != self._machine_state:
            self._machine_state = machine_state
            machine_type = self._config.get_machine_type()
            self.machine_state_changed.emit(machine_type, machine_state)
        if self._is_running != is_running:
            if is_running:
                self._engine.add_stroke_listener(self._stroke_callback)
                self._engine.formatter.add_listener(self._translation_callback)
            else:
                self._engine.remove_stroke_listener(self._stroke_callback)
                self._engine.formatter.remove_listener(self._translation_callback)
            self._is_running = is_running
            self.output_changed.emit(is_running)

    def _consume_engine_command(self, command):
        # The first commands can be used whether plover has output enabled or not.
        if command == 'RESUME':
            self._engine.set_is_running(True)
            return True
        elif command == 'TOGGLE':
            self._engine.set_is_running(not self._engine.is_running)
            return True
        elif command == 'QUIT':
            QtCore.QCoreApplication.quit()
            return True
        if not self._engine.is_running:
            return False
        # These commands can only be run when plover has output enabled.
        if command == 'SUSPEND':
            self._engine.set_is_running(False)
        elif command == 'CONFIGURE':
            self.command_configure.emit()
        elif command == 'FOCUS':
            print('focus')
        elif command == 'ADD_TRANSLATION':
            self.command_add_translation.emit()
        elif command == 'LOOKUP':
            self.command_lookup.emit()
        return False

    def send_backspaces(self, b):
        self._keyboard_control.send_backspaces(b)

    def send_string(self, s):
        self._keyboard_control.send_string(s)

    def send_key_combination(self, c):
        self._keyboard_control.send_key_combination(c)

    def send_engine_command(self, command):
        suppress = not self._engine.is_running
        suppress &= self._consume_engine_command(command)
        if suppress:
            self._engine.machine.suppress_last_stroke(self.send_backspaces)

    def _stroke_callback(self, stroke):
        self.stroke.emit(stroke)

    def _translation_callback(self, old, new):
        self.translation.emit(old, new)

    def toggle_output(self):
        self._same_thread_hook(self._toggle_output)

    def set_output(self, enabled):
        self._same_thread_hook(self._set_output, enabled)

    @property
    @with_lock
    def machine_state(self):
        return self._machine_state

    @property
    def output(self):
        return self._is_running

    @output.setter
    def output(self, enabled):
        self._same_thread_hook(self._engine.set_is_running, enabled)

    @property
    @with_lock
    def config(self):
        return self._config.as_dict()

    @config.setter
    @with_lock
    def config(self, update):
        self._same_thread_hook(self._update_config, **update)

    def reset_machine(self):
        self._same_thread_hook(self._reset_machine)

    def start(self):
        try:
            with open(self._config.target_file, 'rb') as f:
                self._config.load(f)
        except Exception:
            log.error('loading configuration failed, reseting to default', exc_info=True)
            self._config.clear()
            self.command_configure.emit()
        super(Engine, self).start()
        self._same_thread_hook(self._start)

    @property
    @with_lock
    def machines(self):
        return sorted(machine_registry.get_all_names())

    @with_lock
    def machine_specific_options(self, machine_type):
        return self._config.get_machine_specific_options(machine_type)

    @with_lock
    def system_keymap(self, machine_type):
        return self._config.get_system_keymap(machine_type)

    @with_lock
    def lookup(self, translation):
        return self._engine.get_dictionary().lookup(translation)

    @with_lock
    def raw_lookup(self, translation):
        return self._engine.get_dictionary().raw_lookup(translation)

    @with_lock
    def reverse_lookup(self, translation):
        matches = self._engine.get_dictionary().reverse_lookup(translation)
        return [] if matches is None else matches

    @with_lock
    def casereverse_lookup(self, translation):
        matches = self._engine.get_dictionary().casereverse_lookup(translation)
        return set() if matches is None else matches

    @with_lock
    def add_dictionary_filter(self, filter):
        self._engine.get_dictionary().add_filter(filter)

    @with_lock
    def remove_dictionary_filter(self, filter):
        self._engine.get_dictionary().remove_filter(filter)

    @with_lock
    def get_suggestions(self, translation):
        return self._engine.get_suggestions(translation)

    @property
    @with_lock
    def translator_state(self):
        return self._engine.translator.get_state()

    @translator_state.setter
    @with_lock
    def translator_state(self, state):
        if state is None:
            self._engine.translator.clear_state()
        else:
            self._engine.translator.set_state(state)

    @property
    @with_lock
    def starting_stroke_state(self):
        return StartingStrokeState(self._engine.formatter.start_attached,
                                   self._engine.formatter.start_capitalized)

    @starting_stroke_state.setter
    @with_lock
    def starting_stroke_state(self, state):
        self._engine.set_starting_stroke_state(**state._asdict())

    @with_lock
    def add_translation(self, strokes, translation):
        dictionary = self._engine.get_dictionary()
        dictionary.set(strokes, translation)
        dictionary.save(path_list=(dictionary.dicts[0].get_path(),))

    @property
    @with_lock
    def dictionary(self):
        return self._engine.get_dictionary()
