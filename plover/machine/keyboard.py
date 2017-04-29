# Copyright (c) 2010 Joshua Harlan Lifton.
# See LICENSE.txt for details.

"For use with a computer keyboard (preferably NKRO) as a steno machine."

from plover.machine.base import StenotypeBase
from plover.oslayer.keyboardcontrol import KeyboardCapture


class Keyboard(StenotypeBase):
    """Standard stenotype interface for a computer keyboard.

    This class implements the three methods necessary for a standard
    stenotype interface: start_capture, stop_capture, and
    add_callback.

    """

    KEYS_LAYOUT = '''
    Escape  F1 F2 F3 F4  F5 F6 F7 F8  F9 F10 F11 F12

      `  1  2  3  4  5  6  7  8  9  0  -  =  \\ BackSpace  Insert Home Page_Up
     Tab  q  w  e  r  t  y  u  i  o  p  [  ]               Delete End  Page_Down
           a  s  d  f  g  h  j  k  l  ;  '      Return
            z  x  c  v  b  n  m  ,  .  /                          Up
                     space                                   Left Down Right
    '''
    ACTIONS = ('arpeggiate',)

    def __init__(self, params):
        """Monitor the keyboard's events."""
        super(Keyboard, self).__init__()
        self._arpeggiate = params['arpeggiate']
        self._bindings = {}
        self._down_keys = set()
        self._released_keys = set()
        self._keyboard_capture = None
        self._update_bindings()

    def _grab(self):
        if self._keyboard_capture is None:
            return
        self._keyboard_capture.grab_keys(self._bindings.keys())

    def _update_bindings(self):
        self._bindings = dict(self.keymap.get_bindings())
        for key, mapping in list(self._bindings.items()):
            if 'no-op' == mapping:
                self._bindings[key] = None
            elif 'arpeggiate' == mapping:
                if self._arpeggiate:
                    self._bindings[key] = None
                    self._arpeggiate_key = key
                else:
                    # Don't grab arpeggiate key if it's not used.
                    del self._bindings[key]
        self._grab()

    def set_keymap(self, keymap):
        super(Keyboard, self).set_keymap(keymap)
        self._update_bindings()

    def start_capture(self):
        """Begin listening for output from the stenotype machine."""
        self._released_keys.clear()
        self._initializing()
        try:
            self._keyboard_capture = KeyboardCapture()
            self._keyboard_capture.set_machine_instance(self._keyboard_capture)
            self._keyboard_capture.key_down = self._key_down
            self._keyboard_capture.key_up = self._key_up
            self._grab()
            self._keyboard_capture.start()
        except:
            self._error()
            raise
        self._ready()

    def stop_capture(self):
        """Stop listening for output from the stenotype machine."""
        if self._keyboard_capture is not None:
            self._grab()
            self._keyboard_capture.set_machine_instance(None)
            self._keyboard_capture.cancel()
            self._keyboard_capture = None
        self._stopped()

    def _key_down(self, key):
        """Called when a key is pressed."""
        assert key is not None
        steno_key = self._bindings.get(key)
        if steno_key is not None:
            self._down_keys.add(steno_key)

    def _key_up(self, key):
        """Called when a key is released."""
        assert key is not None
        steno_key = self._bindings.get(key)
        if steno_key is not None:
            # Process the newly released key.
            self._released_keys.add(steno_key)
            # Remove invalid released keys.
            self._released_keys = self._released_keys.intersection(self._down_keys)

        # A stroke is complete if all pressed keys have been released.
        # If we are in arpeggiate mode then only send stroke when spacebar is pressed.
        send_strokes = bool(self._down_keys and
                            self._down_keys == self._released_keys)
        if self._arpeggiate:
            send_strokes &= key == self._arpeggiate_key
        if send_strokes:
            steno_keys = list(self._down_keys)
            self._down_keys.clear()
            self._released_keys.clear()
            self._notify(steno_keys)

    @classmethod
    def get_option_info(cls):
        bool_converter = lambda s: s == 'True'
        return {
            'arpeggiate': (False, bool_converter),
        }
