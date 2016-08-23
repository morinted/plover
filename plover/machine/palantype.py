# -*- coding: utf-8 -*-
# Copyright (c) 2016 Ted Morin
# See LICENSE.txt for details.

"Thread-based monitoring of a Palantype machine."

# Python 2/3 compatibility.
from six import iterbytes
from time import sleep
import plover.machine.base

STENO_KEY_CHART = (
    ('M-', '+2-', '+1-', 'H-', 'T-', 'P-', 'S-', 'C-'),
    ('-A', 'E-', 'O-', 'Y-', 'L-', 'N-', 'R-', 'F-'),
    ('-M', '-C', '-L', '-N', '-^2', '-^1', 'I', '-U'),
    ('', '-S', '-H', '-+', '-T', '-P', '-R', '-F'),
)

REALTIME_COMMANDS = [0x81, 0x91, 0x90, 0x93, 0xAA]
REQUEST_READ = bytearray(0x80)
END = bytearray(0x95)


class Palantype(plover.machine.base.SerialStenotypeBase):
    """Palantype interface.

    This class implements the three methods necessary for a standard
    stenotype interface: start_capture, stop_capture, and
    add_callback.

    """

    KEYS_LAYOUT = '''
           P- M- N-         -N -M -P
        C- T- F- L-         -L -F -T -H
        S- H- R- Y- O- I -A -C -R -+ -S
          +1-  +2-  E- I -U  -^1  -^2
    '''

    def __init__(self, params):
        super(Palantype, self).__init__(params)

    def run(self):
        """Overrides base class run method. Do not call directly."""
        settings = self.serial_port.getSettingsDict()
        settings['timeout'] = 0.01
        self.serial_port.applySettingsDict(settings)
        for command in REALTIME_COMMANDS:
            self.serial_port.write(bytearray(command))
            sleep(0.5)
        self._ready()
        while not self.finished.isSet():
            if not self.serial_port.inWaiting():
                self.serial_port.write(REQUEST_READ)
                sleep(0.2)  # Request a read 5 times a second

            raw = self.serial_port.read(self.serial_port.inWaiting())
            # Every stroke is 5 bytes and we drop the first one.
            for i in range(len(raw)/5):
                keys = self._parse_packet(raw[i*5+1:(i+1)*5])
                steno_keys = self.keymap.keys_to_actions(keys)
                if steno_keys:
                    self._notify(steno_keys)

        if self.serial_port:
            self.serial_port.write(END)

    @staticmethod
    def _parse_packet(packet):
        keys = []
        # Packet is a byte array with 4 bytes of data
        for i, byte in enumerate(iterbytes(packet)):
            map = STENO_KEY_CHART[i]
            for i in range(8):
                if not byte >> i & 1:
                    key = map[-i + 7]
                    if key:
                        keys.append(key)
        return keys
