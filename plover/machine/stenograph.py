# -*- coding: utf-8 -*-
# Copyright (c) 2016 Ted Morin
# See LICENSE.txt for details.

"Thread-based monitoring of the stenograph machine."

from usb import core, util
from time import sleep
from plover import log
from plover.machine.base import ThreadedStenotypeBase

# ^ is the "stenomark"
STENO_KEY_CHART = (('^', '#', 'S-', 'T-', 'K-', 'P-'),
                   ('W-', 'H-', 'R-', 'A-', 'O-', '*'),
                   ('-E', '-U', '-F', '-R', '-P', '-B'),
                   ('-L', '-G', '-T', '-S', '-D', '-Z'),
                  )

VENDOR_ID = 0x112b
MAX_OFFSET = 0xFFFFFFFF
HEADER_BYTES = 32


class Stenograph(ThreadedStenotypeBase):

    KEYS_LAYOUT = '''
        #  #  #  #  #  #  #  #  #  #
        S- T- P- H- * -F -P -L -T -D
        S- K- W- R- * -R -B -G -S -Z
              A- O-   -E -U
        ^
    '''

    def __init__(self, params):
        super(Stenograph, self).__init__()
        self._endpoint_in = None
        self._endpoint_out = None

    def _on_stroke(self, keys):
        steno_keys = self.keymap.keys_to_actions(keys)
        if steno_keys:
            self._notify(steno_keys)

    def _connect(self):
        connected = False
        try:
            dev = core.find(idVendor=VENDOR_ID)
            if dev is None:
                raise ValueError('Device not found')
            dev.set_configuration()
            # get an endpoint instance
            cfg = dev.get_active_configuration()
            intf = cfg[(0, 0)]

            self._endpoint_out = util.find_descriptor(
                intf,
                custom_match=lambda e:
                    util.endpoint_direction(e.bEndpointAddress) ==
                        util.ENDPOINT_OUT)
            assert self._endpoint_out is not None

            self._endpoint_in = util.find_descriptor(
                intf,
                custom_match=lambda e:
                    util.endpoint_direction(e.bEndpointAddress) ==
                        util.ENDPOINT_IN)
            assert self._endpoint_in is not None

            connected = True
        except ValueError:
            log.warning('libusb must be installed for Plover to interface with Stenograph machines.')
        return connected

    def start_capture(self):
        """Begin listening for output from the stenotype machine."""
        if not self._connect():
            log.warning('Stenograph machine is not connected')
            self._error()
            return
        super(Stenograph, self).start_capture()

    def _reconnect(self):
        self._endpoint_in = None
        self._endpoint_out = None
        self._initializing()

        connected = self._connect()
        # Reconnect loop
        while not self.finished.isSet() and not connected:
            sleep(0.5)
            connected = self._connect()
        return connected

    def run(self):
        self._ready()
        file_offset = 0
        sequence_number = 0
        realtime = False
        packet = bytearray(
            [0x53, 0x47,  # SG → sync (static)
             0, 0, 0, 0,  # Sequence number
             0x13, 0,  # Action (static)
             0, 0, 0, 0,  # Data length
             0, 0, 0, 0,  # File offset
             0x08, 0, 0, 0,  # Requested byte count (static)
             0, 0, 0, 0,  # Parameter 3
             0, 0, 0, 0,  # Parameter 4
             0, 0, 0, 0,  # Parameter 5
             ]
        )

        while not self.finished.isSet():
            sequence_number = (sequence_number + 1) % MAX_OFFSET
            for i in range(4):
                packet[2 + i] = sequence_number >> 8 * i & 255
            for i in range(4):
                packet[12 + i] = file_offset >> 8 * i & 255
            try:
                self._endpoint_out.write(packet)
                response = self._endpoint_in.read(128, 3000)
            except core.USBError as e:
                if e.errno == 19:
                    log.warning(u'Stenograph machine disconnected, reconnecting…')
                    if self._reconnect():
                        log.warning('Stenograph reconnected.')
            else:
                if response is None:
                    pass
                response_size = len(response)
                steno_size = response_size - HEADER_BYTES
                if not realtime and steno_size <= 0:
                    # Wait for a packet with no data before we are realtime.
                    realtime = True
                elif realtime and steno_size > 0:
                    self._process_response(response)
                file_offset += steno_size

    def _process_response(self, packet):
        steno = packet[HEADER_BYTES:HEADER_BYTES + 4]
        keys = []
        for byte_number, byte in enumerate(steno):
            byte_keys = STENO_KEY_CHART[byte_number]
            for i in range(6):
                if (byte >> i) & 1:
                    key = byte_keys[-i + 5]
                    if key:
                        keys.append(key)
        self._on_stroke(keys)

    def stop_capture(self):
        """Stop listening for output from the stenotype machine."""
        super(Stenograph, self).stop_capture()
        self._endpoint_in = None
        self._endpoint_out = None
        self._stopped()
