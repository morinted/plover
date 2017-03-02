# coding: utf-8
from Quartz import (
    CFMachPortCreateRunLoopSource,
    CFMachPortInvalidate,
    CFRunLoopAddSource,
    CFRunLoopRemoveSource,
    CFRunLoopGetCurrent,
    CFRunLoopRun,
    CFRunLoopStop,
    CFRelease,
    CGEventCreateKeyboardEvent,
    CGEventGetFlags,
    CGEventGetIntegerValueField,
    CGEventKeyboardSetUnicodeString,
    CGEventMaskBit,
    CGEventPost,
    CGEventSetFlags,
    CGEventSourceCreate,
    CGEventTapCreate,
    CGEventTapEnable,
    kCFRunLoopCommonModes,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskNonCoalesced,
    kCGEventFlagMaskNumericPad,
    kCGEventFlagMaskSecondaryFn,
    kCGEventFlagMaskShift,
    kCGEventKeyDown,
    kCGEventKeyUp,
    kCGEventTapDisabledByTimeout,
    kCGEventTapOptionDefault,
    kCGHeadInsertEventTap,
    kCGKeyboardEventKeycode,
    kCGSessionEventTap,
    kCGEventSourceStateHIDSystemState,
    NSEvent,
    NSSystemDefined,
)
import Foundation
import threading
from time import time
import collections
from plover.oslayer import mac_keycode
import plover.log


BACK_SPACE = 51

NX_KEY_OFFSET = 65536

KEYNAME_TO_KEYCODE = collections.defaultdict(list, {
    'Fn': [63],

    'Alt_L': [58], 'Alt_R': [61], 'Control_L': [59], 'Control_R': [62],
    'Hyper_L': [], 'Hyper_R': [], 'Meta_L': [], 'Meta_R': [],
    'Shift_L': [56], 'Shift_R': [60], 'Super_L': [55], 'Super_R': [55],

    'Caps_Lock': [57], 'Scroll_Lock': [], 'Shift_Lock': [],

    'Return': [36], 'Tab': [48], 'BackSpace': [BACK_SPACE], 'Delete': [117],
    'Escape': [53], 'Break': [], 'Insert': [], 'Pause': [], 'Print': [],
    'Sys_Req': [],

    'Up': [126], 'Down': [125], 'Left': [123], 'Right': [124],
    'Page_Up': [116],
    'Page_Down': [121], 'Home': [115], 'End': [119],

    'F1': [122], 'F2': [120], 'F3': [99], 'F4': [118], 'F5': [96], 'F6': [97],
    'F7': [98], 'F8': [100], 'F9': [101], 'F10': [109], 'F11': [103],
    'F12': [111], 'F13': [105], 'F14': [107], 'F15': [113], 'F16': [106],
    'F17': [64], 'F18': [79], 'F19': [80], 'F20': [90], 'F21': [], 'F22': [],
    'F23': [], 'F24': [], 'F25': [], 'F26': [], 'F27': [], 'F28': [],
    'F29': [], 'F30': [], 'F31': [], 'F32': [], 'F33': [], 'F34': [],
    'F35': [],

    'L1': [], 'L2': [], 'L3': [], 'L4': [], 'L5': [], 'L6': [],
    'L7': [], 'L8': [], 'L9': [], 'L10': [],

    'R1': [], 'R2': [], 'R3': [], 'R4': [], 'R5': [], 'R6': [],
    'R7': [], 'R8': [], 'R9': [], 'R10': [], 'R11': [], 'R12': [],
    'R13': [], 'R14': [], 'R15': [],

    'KP_0': [82], 'KP_1': [83], 'KP_2': [84], 'KP_3': [85], 'KP_4': [86],
    'KP_5': [87], 'KP_6': [88], 'KP_7': [89], 'KP_8': [91], 'KP_9': [92],
    'KP_Add': [69], 'KP_Begin': [], 'KP_Decimal': [65], 'KP_Delete': [71],
    'KP_Divide': [75], 'KP_Down': [], 'KP_End': [], 'KP_Enter': [76],
    'KP_Equal': [81], 'KP_F1': [], 'KP_F2': [], 'KP_F3': [], 'KP_F4': [],
    'KP_Home': [], 'KP_Insert': [], 'KP_Left': [], 'KP_Multiply': [67],
    'KP_Next': [], 'KP_Page_Down': [], 'KP_Page_Up': [], 'KP_Prior': [],
    'KP_Right': [], 'KP_Separator': [], 'KP_Space': [], 'KP_Subtract': [78],
    'KP_Tab': [], 'KP_Up': [],

})

KEYNAME_TO_CHAR = {
    'ampersand': '&', 'apostrophe': '\'', 'asciitilde': '~',
    'asterisk': '*', 'at': '@', 'backslash': '\'',
    'braceleft': '{', 'braceright': '}', 'bracketleft': '[',
    'bracketright': ']', 'colon': ':', 'comma': ',', 'division': '÷',
    'dollar': '$', 'equal': '=', 'exclam': '!', 'greater': '>',
    'hyphen': '-', 'less': '<', 'minus': '-', 'multiply': '×',
    'numbersign': '#', 'parenleft': '(', 'parenright': ')',
    'percent': '%', 'period': '.', 'plus': '+',
    'question': '?', 'quotedbl': '"', 'quoteleft': '‘',
    'quoteright': '’', 'semicolon': ';', 'slash': '/', 'space': ' ',
    'underscore': '_',
    'grave': '`', 'asciicircum': '^',
    'bar': '|',
}


def down(seq):
    return [(x, True) for x in seq]


def up(seq):
    return [(x, False) for x in reversed(seq)]


def down_up(seq):
    return down(seq) + up(seq)

# Maps from literal characters to their key names.
LITERALS = collections.defaultdict(str, {
    '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6',
    '7': '7', '8': '8', '9': '9',

    'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd', 'e': 'e', 'f': 'f', 'g': 'g',
    'h': 'h', 'i': 'i', 'j': 'j', 'k': 'k', 'l': 'l', 'm': 'm', 'n': 'n',
    'o': 'o', 'p': 'p', 'q': 'q', 'r': 'r', 's': 's', 't': 't', 'u': 'u',
    'v': 'v', 'w': 'w', 'x': 'x', 'y': 'y', 'z': 'z',

    'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F', 'G': 'G',
    'H': 'H', 'I': 'I', 'J': 'J', 'K': 'K', 'L': 'L', 'M': 'M', 'N': 'N',
    'O': 'O', 'P': 'P', 'Q': 'Q', 'R': 'R', 'S': 'S', 'T': 'T', 'U': 'U',
    'V': 'V', 'W': 'W', 'X': 'X', 'Y': 'Y', 'Z': 'Z',

    '`': 'grave', '~': 'asciitilde', '!': 'exclam', '@': 'at',
    '#': 'numbersign', '$': 'dollar', '%': 'percent', '^': 'asciicircum',
    '&': 'ampersand', '*': 'asterisk', '(': 'parenleft', ')': 'parenright',
    '-': 'minus', '_': 'underscore', '=': 'equal', '+': 'plus',
    '[': 'bracketleft', ']': 'bracketright', '{': 'braceleft',
    '}': 'braceright', '\\': 'backslash', '|': 'bar', ';': 'semicolon',
    ':': 'colon', '\'': 'apostrophe', '"': 'quotedbl', ',': 'comma',
    '<': 'less', '.': 'period', '>': 'greater', '/': 'slash',
    '?': 'question', '\t': 'Tab', ' ': 'space'
})

NX_KEYS = {
    "AudioRaiseVolume": 0,
    "AudioLowerVolume": 1,
    "MonBrightnessUp": 2,
    "MonBrightnessDown": 3,
    "AudioMute": 7,
    "Num_Lock": 10,
    "Eject": 14,
    "AudioPause": 16,
    "AudioPlay": 16,
    "AudioNext": 17,
    "AudioPrev": 18,
    "AudioRewind": 20,
    "KbdBrightnessUp": 21,
    "KbdBrightnessDown": 22
}

# Maps from keycodes to corresponding event masks.
MODIFIER_KEYS_TO_MASKS = {
    58: kCGEventFlagMaskAlternate,
    61: kCGEventFlagMaskAlternate,
    59: kCGEventFlagMaskControl,
    62: kCGEventFlagMaskControl,
    56: kCGEventFlagMaskShift,
    60: kCGEventFlagMaskShift,
    55: kCGEventFlagMaskCommand,
    63: kCGEventFlagMaskSecondaryFn,
}

OUTPUT_SOURCE = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)

# For the purposes of this class, we're only watching these keys.
# We could calculate the keys, but our default layout would be misleading:
#
#     KEYCODE_TO_KEY = {keycode: mac_keycode.CharForKeycode(keycode) \
#             for keycode in range(127)}
KEYCODE_TO_KEY = {
    122: 'F1', 120: 'F2', 99: 'F3', 118: 'F4', 96: 'F5', 97: 'F6',
    98: 'F7', 100: 'F8', 101: 'F9', 109: 'F10', 103: 'F11', 111: 'F12',

    50: '`', 29: '0', 18: '1', 19: '2', 20: '3', 21: '4', 23: '5',
    22: '6', 26: '7', 28: '8', 25: '9', 27: '-', 24: '=',

    12: 'q', 13: 'w', 14: 'e', 15: 'r', 17: 't', 16: 'y',
    32: 'u', 34: 'i', 31: 'o',  35: 'p', 33: '[', 30: ']', 42: '\\',

    0: 'a', 1: 's', 2: 'd', 3: 'f', 5: 'g',
    4: 'h', 38: 'j', 40: 'k', 37: 'l', 41: ';', 39: '\'',

    6: 'z', 7: 'x', 8: 'c', 9: 'v', 11: 'b',
    45: 'n', 46: 'm', 43: ',', 47: '.', 44: '/',

    49: 'space', BACK_SPACE: "BackSpace",
    117: "Delete", 125: "Down", 119: "End",
    53: "Escape", 115: "Home", 123: "Left", 121: "Page_Down", 116: "Page_Up",
    36: "Return", 124: "Right", 48: "Tab", 126: "Up",
}


class KeyboardCapture(threading.Thread):
    """Implementation of KeyboardCapture for OSX."""

    _KEYBOARD_EVENTS = set([kCGEventKeyDown, kCGEventKeyUp])

    def __init__(self):
        threading.Thread.__init__(self)
        self._running_thread = None
        self._suppressed_keys = set()
        self.key_down = lambda key: None
        self.key_up = lambda key: None

        # Returning the event means that it is passed on
        # for further processing by others.
        #
        # Returning None means that the event is intercepted.
        #
        # Delaying too long in returning appears to cause the
        # system to ignore the tap forever after
        # (https://github.com/openstenoproject/plover/issues/484#issuecomment-214743466).
        #
        # This motivates pushing callbacks to the other side
        # of a queue of received events, so that we can return
        # from this callback as soon as possible.
        def callback(proxy, event_type, event, reference):
            SUPPRESS_EVENT = None
            PASS_EVENT_THROUGH = event

            # Don't pass on meta events meant for this event tap.
            is_unexpected_event = event_type not in self._KEYBOARD_EVENTS
            if is_unexpected_event:
                if event_type == kCGEventTapDisabledByTimeout:
                    # Re-enable the tap and hope we act faster next time
                    CGEventTapEnable(self._tap, True)
                    plover.log.warning(
                        "Keyboard event tap was disabled by timeout. " +
                        "Attempted to re-enable. Quit and relaunch Plover " +
                        "if translation does not resume.")
                return SUPPRESS_EVENT

            # Don't intercept the event if it has modifiers, allow
            # Fn and Numeric flags so we can suppress the arrow and
            # extended (home, end, etc...) keys.
            suppressible_modifiers = (kCGEventFlagMaskNumericPad |
                                      kCGEventFlagMaskSecondaryFn |
                                      kCGEventFlagMaskNonCoalesced)
            has_nonsupressible_modifiers = \
                CGEventGetFlags(event) & ~suppressible_modifiers
            if has_nonsupressible_modifiers:
                return PASS_EVENT_THROUGH

            keycode = CGEventGetIntegerValueField(
                event, kCGKeyboardEventKeycode)
            key = KEYCODE_TO_KEY.get(keycode)
            self._dispatch(key, event_type)
            if key in self._suppressed_keys:
                return SUPPRESS_EVENT
            return PASS_EVENT_THROUGH

        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            CGEventMaskBit(kCGEventKeyDown) | CGEventMaskBit(kCGEventKeyUp),
            callback, None)
        if self._tap is None:
            # Todo(hesky): See if there is a nice way to show the user what's
            # needed (or do it for them).
            raise Exception("Enable access for assistive devices.")
        self._source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CGEventTapEnable(self._tap, False)

    def run(self):
        self._running_thread = CFRunLoopGetCurrent()
        CFRunLoopAddSource(
            self._running_thread,
            self._source,
            kCFRunLoopCommonModes
        )
        CGEventTapEnable(self._tap, True)
        CFRunLoopRun()

    def cancel(self):
        CGEventTapEnable(self._tap, False)
        CFRunLoopRemoveSource(
            self._running_thread, self._source, kCFRunLoopCommonModes)
        CFRelease(self._source)
        self._source = None

        CFMachPortInvalidate(self._tap)
        CFRelease(self._tap)
        self._tap = None

        CFRunLoopStop(self._running_thread)
        self._running_thread = None

    def suppress_keyboard(self, suppressed_keys=()):
        self._suppressed_keys = set(suppressed_keys)

    def _dispatch(self, key, event_type):
        """
        Dispatches a key string in KEYCODE_TO_KEY.values() and a CGEventType
        to the appropriate KeyboardCapture callback.
        """
        if key is None:
            return

        handler = self.key_up if event_type == kCGEventKeyUp \
            else self.key_down
        # (jws/2016-05-07)TODO: Call this asynchronously!
        handler(key)


# "Narrow python" unicode objects store characters in UTF-16 so we
# can't iterate over characters in the standard way. This workaround
# let's us iterate over full characters in the string.
def characters(s):
    encoded = s.encode('utf-32-be')
    for i in xrange(len(encoded) / 4):
        start = i * 4
        end = start + 4
        character = encoded[start:end].decode('utf-32-be')
        yield character


class KeyboardEmulation(object):

    RAW_PRESS, STRING_PRESS = range(2)

    def __init__(self):
        pass

    @staticmethod
    def send_backspaces(number_of_backspaces):
        for _ in xrange(number_of_backspaces):
            backspace_down = CGEventCreateKeyboardEvent(
                OUTPUT_SOURCE, BACK_SPACE, True)
            backspace_up = CGEventCreateKeyboardEvent(
                OUTPUT_SOURCE, BACK_SPACE, False)
            CGEventPost(kCGSessionEventTap, backspace_down)
            CGEventPost(kCGSessionEventTap, backspace_up)

    def send_string(self, s):
        """

        Args:
            s: The string to emulate.

        We can send keys by keycodes or by SetUnicodeString.
        Setting the string is less ideal, but necessary for things like emoji.
        We want to try to group modifier presses, where convenient.
        So, a string like 'THIS dog [dog emoji]' might be processed like:
            'Raw: Shift down t h i s shift up,
            Raw: space d o g space,
            String: [dog emoji]'
        There are 3 groups, the shifted group, the spaces and dog string,
        and the emoji.
        """
        # Key plan will store the type of output
        # (raw keycodes versus setting string)
        # and the list of keycodes or the goal character.
        key_plan = []

        # apply_raw's properties are used to store
        # the current keycode sequence,
        # and add the sequence to the key plan when called as a function.
        def apply_raw():
            if hasattr(apply_raw, 'sequence') \
                    and len(apply_raw.sequence) is not 0:
                apply_raw.sequence.extend(apply_raw.release_modifiers)
                key_plan.append((self.RAW_PRESS, apply_raw.sequence))
            apply_raw.sequence = []
            apply_raw.release_modifiers = []
        apply_raw()

        last_modifier = None
        for c in characters(s):
            for keycode, modifier in mac_keycode.KeyCodeForChar(c):
                if keycode is not None:
                    if modifier is not last_modifier:
                        # Flush on modifier change.
                        apply_raw()
                        last_modifier = modifier
                        modifier_keycodes = self._modifier_to_keycodes(
                            modifier)
                        apply_raw.sequence.extend(down(modifier_keycodes))
                        apply_raw.release_modifiers.extend(
                            up(modifier_keycodes))
                    apply_raw.sequence.extend(down_up([keycode]))
                else:
                    # Flush on type change.
                    apply_raw()
                    key_plan.append((self.STRING_PRESS, c))
        # Flush after string is complete.
        apply_raw()

        # We have a key plan for the whole string, grouping modifiers.
        for press_type, sequence in key_plan:
            if press_type is self.STRING_PRESS:
                self._send_string_press(sequence)
            elif press_type is self.RAW_PRESS:
                self._send_sequence(sequence)

    @staticmethod
    def _send_string_press(c):
        event = CGEventCreateKeyboardEvent(OUTPUT_SOURCE, 0, True)
        KeyboardEmulation._set_event_string(event, c)
        CGEventPost(kCGSessionEventTap, event)
        event = CGEventCreateKeyboardEvent(OUTPUT_SOURCE, 0, False)
        KeyboardEmulation._set_event_string(event, c)
        CGEventPost(kCGSessionEventTap, event)

    def send_key_combination(self, combo_string):
        """Emulate a sequence of key combinations.

        Args:
            combo_string: A string representing a sequence of key
                combinations. Keys are represented by their names in the
                Xlib.XK module, without the 'XK_' prefix. For example, the
                left Alt key is represented by 'Alt_L'. Keys are either
                separated by a space or a left or right parenthesis.
                Parentheses must be properly formed in pairs and may be
                nested. A key immediately followed by a parenthetical
                indicates that the key is pressed down while all keys enclosed
                in the parenthetical are pressed and released in turn. For
                example, Alt_L(Tab) means to hold the left Alt key down, press
                and release the Tab key, and then release the left Alt key.

        """

        # Convert the argument into a sequence of keycode, event type pairs
        # that, if executed in order, would emulate the key combination
        # represented by the argument.
        def _keystring_to_sequence(keystring):
            if keystring in NX_KEYS:
                seq = [NX_KEYS[keystring] + NX_KEY_OFFSET]
            elif keystring in KEYNAME_TO_KEYCODE:
                seq = KEYNAME_TO_KEYCODE[keystring]
            else:
                # Convert potential key name to Unicode character
                if keystring in KEYNAME_TO_CHAR:
                    keystring = KEYNAME_TO_CHAR[keystring]
                seq = []
                for keycode, modifier in mac_keycode.KeyCodeForChar(keystring):
                    if keycode is not None:
                        seq.extend(self._modifier_to_keycodes(modifier))
                        seq.append(keycode)
            return seq

        keycode_events = []
        key_down_stack = []
        current_command = []
        for c in combo_string:
            if c in (' ', '(', ')'):
                keystring = ''.join(current_command)
                current_command = []
                seq = _keystring_to_sequence(keystring)

                if c == ' ':
                    # Record press and release for command's keys.
                    keycode_events.extend(down_up(seq))
                elif c == '(':
                    # Record press for command's key.
                    keycode_events.extend(down(seq))
                    key_down_stack.append(seq)
                elif c == ')':
                    # Record press and release for command's key and
                    # release previously held keys.
                    keycode_events.extend(down_up(seq))
                    if key_down_stack:
                        keycode_events.extend(up(key_down_stack.pop()))
            else:
                current_command.append(c)
        # Record final command key.
        if current_command:
            keystring = ''.join(current_command)
            seq = _keystring_to_sequence(keystring)
            keycode_events.extend(down_up(seq))

        # Release all keys.
        # Should this be legal in the dict (lack of closing parens)?
        for seq in key_down_stack:
            keycode_events.extend(up(seq))

        # Emulate the key combination by sending key events.
        self._send_sequence(keycode_events)

    @staticmethod
    def _modifier_to_keycodes(modifier):
        keycodes = []
        if modifier & 16:
            keycodes.extend(KEYNAME_TO_KEYCODE['Control_R'])
        if modifier & 8:
            keycodes.extend(KEYNAME_TO_KEYCODE['Alt_R'])
        if modifier & 2:
            keycodes.extend(KEYNAME_TO_KEYCODE['Shift_R'])
        if modifier & 1:
            keycodes.extend(KEYNAME_TO_KEYCODE['Super_R'])
        return keycodes

    @staticmethod
    def _set_event_string(event, s):
        buf = Foundation.NSString.stringWithString_(s)
        CGEventKeyboardSetUnicodeString(event, len(buf), buf)

    MODS_MASK = (
        kCGEventFlagMaskAlternate |
        kCGEventFlagMaskControl |
        kCGEventFlagMaskShift |
        kCGEventFlagMaskCommand |
        kCGEventFlagMaskSecondaryFn
    )

    @staticmethod
    def _get_media_event(key_id, key_down):
        # Credit: https://gist.github.com/fredrikw/4078034
        flags = 0xa00 if key_down else 0xb00
        return NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(  # nopep8: We can't make this line shorter!
            NSSystemDefined, (0, 0),
            flags,
            0, 0, 0, 8,
            (key_id << 16) | flags,
            -1
        ).CGEvent()

    @staticmethod
    def _send_sequence(sequence):
        # There is a bug in the event system that seems to cause inconsistent
        # modifiers on key events:
        # http://stackoverflow.com/questions/2008126/cgeventpost-possible-bug-when-simulating-keyboard-events
        # My solution is to manage the state myself.
        # I'm not sure how to deal with caps lock.
        # If mods_flags is not zero at the end then bad things might happen.
        mods_flags = 0

        for keycode, key_down in sequence:
            if keycode >= NX_KEY_OFFSET:
                # Handle media (NX) key.
                event = KeyboardEmulation._get_media_event(
                    keycode - NX_KEY_OFFSET, key_down)
            else:
                # Handle regular keycode.
                if not key_down and keycode in MODIFIER_KEYS_TO_MASKS:
                    mods_flags &= ~MODIFIER_KEYS_TO_MASKS[keycode]

                event = CGEventCreateKeyboardEvent(
                    OUTPUT_SOURCE, keycode, key_down)

                if key_down and keycode not in MODIFIER_KEYS_TO_MASKS:
                    event_flags = CGEventGetFlags(event)
                    # Add wanted flags, remove unwanted flags.
                    goal_flags = ((event_flags & ~KeyboardEmulation.MODS_MASK)
                                  | mods_flags)
                    if event_flags != goal_flags:
                        CGEventSetFlags(event, goal_flags)

                    # Half millisecond pause after key down.
                    deadline = time() + 0.0005
                    while time() < deadline:
                        pass
                if key_down and keycode in MODIFIER_KEYS_TO_MASKS:
                    mods_flags |= MODIFIER_KEYS_TO_MASKS[keycode]

            CGEventPost(kCGSessionEventTap, event)
