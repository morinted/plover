
import os
import unittest
from contextlib import contextmanager
from functools import partial

import mock

from plover import system
from plover.config import DEFAULT_SYSTEM_NAME
from plover.engine import StenoEngine
from plover.registry import Registry
from plover.machine.base import StenotypeBase


class FakeConfig(object):

    DEFAULTS = {
        'auto_start'                : False,
        'machine_type'              : 'Fake',
        'machine_specific_options'  : {},
        'system_name'               : DEFAULT_SYSTEM_NAME,
        'system_keymap'             : [(k, k) for k in system.KEYS],
        'dictionaries'              : {},
        'log_file_name'             : os.devnull,
        'enable_stroke_logging'     : False,
        'enable_translation_logging': False,
        'space_placement'           : 'Before Output',
        'undo_levels'               : 10,
        'start_capitalized'         : True,
        'start_attached'            : False,
        'enabled_extensions'        : set(),
    }

    def __init__(self, **kwargs):
        self._options = {}
        for name, default in self.DEFAULTS.items():
            value = kwargs.get(name, default)
            self._options[name] = value
            self.__dict__['get_%s' % name] = partial(lambda v, *a: v, value)
        self.target_file = os.devnull

    def load(self, fp):
        pass

    def as_dict(self):
        return dict(self._options)

    def update(self, **kwargs):
        self._options.update(kwargs)


class FakeMachine(StenotypeBase):

    instance = None

    def __init__(self, options):
        super(FakeMachine, self).__init__()
        self.options = options

    @classmethod
    def get_keys(cls):
        return system.KEYS

    def start_capture(self):
        assert FakeMachine.instance is None
        FakeMachine.instance = self
        self._initializing()
        self._ready()

    def stop_capture(self):
        FakeMachine.instance = None
        self._stopped()


class FakeKeyboardEmulation(object):

    def start(self):
        pass

    def cancel(self):
        pass

    def send_backspaces(self, b):
        pass

    def send_string(self, s):
        pass

    def send_key_combination(self, c):
        pass

class FakeEngine(StenoEngine):

    def _in_engine_thread(self):
        return True

    def start(self):
        StenoEngine.start(self)


class EngineTestCase(unittest.TestCase):

    @contextmanager
    def _setup(self, **kwargs):
        FakeMachine.instance = None
        self.reg = Registry()
        self.reg.register_plugin('machine', 'Fake', FakeMachine)
        self.cfg = FakeConfig(**kwargs)
        self.events = []
        self.engine = FakeEngine(self.cfg, FakeKeyboardEmulation)
        def hook_callback(hook, *args, **kwargs):
            self.events.append((hook, args, kwargs))
        for hook in self.engine.HOOKS:
            self.engine.hook_connect(hook, partial(hook_callback, hook))
        try:
            with mock.patch('plover.engine.registry', self.reg):
                yield
        finally:
            del self.reg
            del self.cfg
            del self.engine
            del self.events

    def test_engine(self):
        with self._setup():
            # Config load.
            self.assertEqual(self.engine.load_config(), True)
            self.assertEqual(self.events, [])
            # Startup.
            self.engine.start()
            self.assertEqual(self.events, [
                ('config_changed', (self.cfg.as_dict(),), {}),
            ])
            self.assertIsNone(FakeMachine.instance)
            # Output enabled.
            self.events = []
            self.engine.output = True
            self.assertEqual(self.events, [
                ('machine_state_changed', ('Fake', 'initializing'), {}),
                ('machine_state_changed', ('Fake', 'connected'), {}),
                ('output_changed', (True,), {}),
            ])
            self.assertIsNotNone(FakeMachine.instance)
            # Machine reconnection.
            self.events = []
            self.engine.reset_machine()
            self.assertEqual(self.events, [
                ('machine_state_changed', ('Fake', 'stopped'), {}),
                ('machine_state_changed', ('Fake', 'initializing'), {}),
                ('machine_state_changed', ('Fake', 'connected'), {}),
            ])
            self.assertIsNotNone(FakeMachine.instance)
            # Output disabled
            self.events = []
            self.engine.output = False
            self.assertEqual(self.events, [
                ('machine_state_changed', ('Fake', 'stopped'), {}),
                ('output_changed', (False,), {}),
            ])
            self.assertIsNone(FakeMachine.instance)
            # Stopped.
            self.events = []
            self.engine.quit()
            self.assertEqual(self.events, [
            ])
