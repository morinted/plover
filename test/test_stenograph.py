# -*- coding: utf-8 -*-
# Copyright (c) 2017 Open Steno Project
# See LICENSE.txt for details.

"""Tests for stenograph.py"""

import unittest

from plover.machine.stenograph import *


class StenographTestCase(unittest.TestCase):
    def test_sequence_number(self):
        # Test that sequence number iterates on creation and rollover after the 4 bytes
        # Reset to 0
        StenoPacket.sequence_number = 0
        sequence_number = StenoPacket.make_open_request().sequence_number
        assert sequence_number == 0
        assert StenoPacket.sequence_number == 1
        StenoPacket.sequence_number = 0xFFFFFFFD # second last sequence number
        sequence_number = StenoPacket.make_read_request().sequence_number
        assert sequence_number == 0xFFFFFFFD
        sequence_number = StenoPacket.make_read_request().sequence_number
        assert sequence_number == 0xFFFFFFFE
        sequence_number = StenoPacket.make_read_request().sequence_number
        assert sequence_number == 0

    def test_usb_packet_from_data(self):
        # Data -- 4 bytes of steno, 4 bytes of timestamp (ignored)
        raw_stroke_data = bytearray([ 0b11000001, 0b11000000, 0b11000000, 0b11000000, 255, 255, 255, 255, ])
        raw_packet = bytearray(
            [0x53, 0x47,  # SG
             0, 0, 0, 0,  # Sequence number
             StenoPacket.ID_READ, 0,  # Action (static)
             len(raw_stroke_data), 0, 0, 0,  # Data length
             1, 0, 0, 0,  # File offset
             0, 0x02, 0, 0,  # Requested byte count (static 512)
             0, 0, 0, 0,  # Parameter 3
             0, 0, 0, 0,  # Parameter 4
             0, 0, 0, 0,  # Parameter 5
             ]
        ) + raw_stroke_data
        stroke = StenoPacket.unpack(raw_packet)
        assert stroke.data_length == 8
        assert stroke.p2 == 512
        assert stroke.data == raw_stroke_data
        assert stroke.packet_id == StenoPacket.ID_READ
        assert stroke.strokes() == [['P-']]

        # Test conversion back into marshaled
        assert stroke.pack() == raw_packet

    def test_make_open_packet(self):
        open_packet = StenoPacket.make_open_request()
        assert open_packet.p1 == ord(b'A')
        assert open_packet.data == b'REALTIME.000'
        assert open_packet.data_length == 12

    def test_chords(self):
        packet = StenoPacket.make_read_request()
        packet.data = [
             255, 255, 255, 255, 0, 0, 0, 0,  # All keys
             0b11000000, 0b11000000, 0b11000000, 0b11000000, 0, 0, 0, 0,  # No keys
             0b11000001, 0b11000001, 0b11000001, 0b11000001, 0, 0, 0, 0,  # P*BZ
             0b11100000, 0b11100000, 0b11100000, 0b11100000, 0, 0, 0, 0,  # ^WEL
         ]
        packet.data_length = len(packet.data)
        assert packet.strokes() == [
            ['^', '#', 'S-', 'T-', 'K-', 'P-',
             'W-', 'H-', 'R-', 'A-', 'O-', '*',
             '-E', '-U', '-F', '-R', '-P', '-B',
             '-L', '-G', '-T', '-S', '-D', '-Z'],  # All keys
            # No keys
            ['P-', '*', '-B', '-Z' ],  # P*BZ
            ['^', 'W-', '-E', '-L' ],  # ^WEL
        ]
