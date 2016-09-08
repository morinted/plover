# -*- coding: utf-8 -*-
# Copyright (c) 2016 Ted Morin
# See LICENSE.txt for details.

"Thread-based monitoring of the stenograph machine."

import sys
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

if sys.platform.startswith('win32'):
    from ctypes import *
    from ctypes.wintypes import DWORD, HANDLE, WORD, BYTE
    import uuid

    class GUID(Structure):
        _fields_ = [("Data1", DWORD),
                    ("Data2", WORD),
                    ("Data3", WORD),
                    ("Data4", BYTE * 8)]


    class SP_DEVICE_INTERFACE_DATA(Structure):
      _fields_ = [('cbSize',DWORD),
      ('InterfaceClassGuid', BYTE * 16),
      ('Flags', DWORD),
      ('Reserved', POINTER(c_ulonglong))]

    class USB_Packet(Structure):
        _fields_ = [
            # Hack to pack structure correctly (without importing 'struct')
            ("SyncSeqType", c_ubyte * 8),
            ("uiDataLen", DWORD),
            ("uiFileOffset", DWORD),
            ("uiByteCount", DWORD),
            ("uiParam3", DWORD),
            ("uiParam4", DWORD),
            ("uiParam5", DWORD),
            ("data", c_ubyte * 1024)
        ]  # limiting data to 1024 bytes (should only ask for 512 at a time)

    # Class GUID / UUID for Stenograph USB Writer
    USB_WRITER_GUID = uuid.UUID('{c5682e20-8059-604a-b761-77c4de9d5dbf}')

    # For Windows we directly call Windows API functions
    SetupDiGetClassDevs=windll.setupapi.SetupDiGetClassDevsA
    SetupDiEnumDeviceInterfaces=windll.setupapi.SetupDiEnumDeviceInterfaces
    SetupDiGetInterfaceDeviceDetail=windll.setupapi.SetupDiGetDeviceInterfaceDetailA
    CreateFile = windll.kernel32.CreateFileA
    ReadFile = windll.kernel32.ReadFile
    WriteFile = windll.kernel32.WriteFile
    GetLastError = windll.kernel32.GetLastError

    # USB Writer 'defines'
    INVALID_HANDLE_VALUE = -1
    ERROR_INSUFFICIENT_BUFFER = 122
    c_pktError  = 0x06
    c_pktReadBytes = 0x13
    USB_NO_RESPONSE = -9
    RT_FILE_ENDED_ON_WRITER = -8

    class WindowsStenographMachine(object):
        def __init__(self):
            # Allocate memory for sending and receiving USB data
            self._host_packet = USB_Packet()
            self._writer_packet = USB_Packet()

            self._sequence_number = 0
            self._file_offset = 0
            self._usb_device = HANDLE(0)

        @staticmethod
        def _open_device_instance(hdevinfo, guid):  #returns a handle to the writer opened with CreateFile
            dev_interface_data = SP_DEVICE_INTERFACE_DATA()
            dev_interface_data.cbSize=sizeof(dev_interface_data)

            status = SetupDiEnumDeviceInterfaces(hdevinfo, None, guid.bytes, 0, byref(dev_interface_data))
            if status == 0:
                return INVALID_HANDLE_VALUE

            reqlength = DWORD(0)
            # Call once with None to see how big a buffer we need for the detail data
            SetupDiGetInterfaceDeviceDetail(
                hdevinfo,
                byref(dev_interface_data),
                None,
                0,
                pointer(reqlength),
                None
            )
            error = GetLastError()
            if error != ERROR_INSUFFICIENT_BUFFER:
                return INVALID_HANDLE_VALUE

            req = reqlength.value

            class PSP_INTERFACE_DEVICE_DETAIL_DATA(Structure):
                _fields_ = [('cbSize', DWORD), ('DevicePath', c_char * req)]
            dev_detail_data = PSP_INTERFACE_DEVICE_DETAIL_DATA()
            dev_detail_data.cbSize = 5  # DWORD + 4 byte pointer

            # Now put the actual detail data into the buffer
            status = SetupDiGetInterfaceDeviceDetail(
                hdevinfo, byref(dev_interface_data), byref(dev_detail_data), req,
                pointer(reqlength), None
            )

            if not status:
                return INVALID_HANDLE_VALUE

            hdevhandle = CreateFile(
                dev_detail_data.DevicePath,
                0xC0000000, 0x3, 0, 0x3, 0x80, 0
            )
            return hdevhandle

        @staticmethod
        def _open_device_by_class_interface_and_instance(classguid): #returns a handle to the writer opened with CreateFile
            # SetupDiGetClassDevs(pClassGuid, NULL, NULL, DIGCF_DEVICEINTERFACE | DIGCF_PRESENT);
            hdevinfo = SetupDiGetClassDevs(classguid.bytes, 0, 0, 0x12)
            if hdevinfo == INVALID_HANDLE_VALUE:
                return INVALID_HANDLE_VALUE

            usb_device = WindowsStenographMachine._open_device_instance(hdevinfo, classguid)
            return usb_device

        def _usb_write_packet(self):
            self._host_packet.SyncSeqType[0] = ord('S')
            self._host_packet.SyncSeqType[1] = ord('G')
            self._host_packet.SyncSeqType[2] = self._sequence_number % 255
            self._host_packet.SyncSeqType[6] = c_pktReadBytes
            if self._usb_device == INVALID_HANDLE_VALUE:  # device not opened yet
                return 0
            bytes_written = DWORD(0)

            write_result = WriteFile(
                self._usb_device,
                byref(self._host_packet),
                32 + self._host_packet.uiDataLen,
                byref(bytes_written),
                None
            )
            if write_result == 0:
                write_result = GetLastError()
            # if bytes_written == 0:  #unable to write any bytes, has the Writer been disconnected?
              # the writer has probably been disconnected

            return bytes_written.value

        def _usb_read_packet(self): # //this is a "give me everything you have" kind of function - the header will tell us how much is valid
          if self._usb_device == INVALID_HANDLE_VALUE: # device not opened yet
            # print "NoWriter"
            return 0

          bytes_read = DWORD(0)

          # Always read this maximum amount.
          # The header will tell me how much to pay attention to.
          ReadFile(
              self._usb_device,
              byref(self._writer_packet),
              32 + 1024,
              byref(bytes_read),
              None
          )
          if bytes_read.value == 0:
            return 0
          if bytes_read.value < 32:  # returned without a full packet
            return 0
          return 32 + self._writer_packet.uiDataLen

        def _read_steno(self):
            self._host_packet.SyncSeqType[6] = c_pktReadBytes
            self._host_packet.uiDataLen = 0
            self._host_packet.uiParam3 = 0
            self._host_packet.uiParam4 = 0
            self._host_packet.uiParam5 = 0
            self._host_packet.uiFileOffset = self._file_offset
            self._host_packet.uiByteCount = 512
            if self._usb_write_packet() == 0:
                return USB_NO_RESPONSE  # I couldn't write any bytes to the writer - is the USB still connected?

            # listen for response
            amount_read = self._usb_read_packet()

            if amount_read > 0:
                amount_read -= 32 # remove the header portion so I know how much data there is
            else:
                return USB_NO_RESPONSE  # No bytes, is it still connected?

            # If the sequence number is not the same it is junk
            if self._writer_packet.SyncSeqType[2] == self._host_packet.SyncSeqType[2]:
                self._sequence_number += 1

                if self._writer_packet.SyncSeqType[6] == c_pktReadBytes:
                    return self._writer_packet.uiDataLen
                else:
                    # Could check the error code for more specific errors here
                    if self._writer_packet.SyncSeqType[6] == c_pktError:
                        return RT_FILE_ENDED_ON_WRITER
            else:
                self._usb_read_packet() # toss out any junk
                return USB_NO_RESPONSE  # I couldn't read any bytes from the writer - is the USB still connected?

        def connect(self):
            self._file_offset = 0
            self._usb_device = self._open_device_by_class_interface_and_instance(USB_WRITER_GUID)
            return self._usb_device != INVALID_HANDLE_VALUE

        def read(self):
            result = self._read_steno()
            if result > 0:  # Got one or more steno strokes
                self._file_offset += result
                # Data can be many strokes -- we will just send the latest one.
                # This is all that is useful in realtime.
                # If we want to support reading back files, then don't do this:
                return self._writer_packet.data[-8:-4]
            elif not result:
                return None
            elif result == RT_FILE_ENDED_ON_WRITER:
                print('Realtime Ended')  # TODO: handle realtime ended
            elif result == USB_NO_RESPONSE:
                print('No response :(')
                # No USB communiucation with the writer.
                # We should assume that it has only gone away temporarily.
                pass
    StenographMachine = WindowsStenographMachine
else:
    class LibUSBStenographMachine(object):
        def __init__(self):
            self._endpoint_in = None
            self._endpoint_out = None
            self._file_offset = 0
            self._sequence_number = 0
            self._packet = bytearray(
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
            self._connected = False

        def connect(self):
            self._connected = False
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
                self._connected = True
            except ValueError:
                log.warning('libusb must be installed for Plover to interface with Stenograph machines.')
            return self._connected

        def read(self):
            if not self._connected:
                IOError('Can\' read: Stenograph not connected')
            self._sequence_number = (self._sequence_number + 1) % MAX_OFFSET
            for i in range(4):
                self._packet[2 + i] = self._sequence_number >> 8 * i & 255
            for i in range(4):
                self._packet[12 + i] = self._file_offset >> 8 * i & 255
            self._endpoint_out.write(self._packet)
            response = self._endpoint_in.read(128, 3000)
            if response and len(response) > HEADER_BYTES:
                self._file_offset += len(response) - HEADER_BYTES
            return response
    StenographMachine = LibUSBStenographMachine

class Stenograph(ThreadedStenotypeBase):

    KEYS_LAYOUT = '''
        #  #  #  #  #  #  #  #  #  #
        S- T- P- H- * -F -P -L -T -D
        S- K- W- R- * -R -B -G -S -Z
              A- O-   -E -U
        ^
    '''

    def __init__(self):
        super(Stenograph, self).__init__()
        self._machine = StenographMachine()

    def _on_stroke(self, keys):
        steno_keys = self.keymap.keys_to_actions(keys)
        if steno_keys:
            self._notify(steno_keys)

    def start_capture(self):
        """Begin listening for output from the stenotype machine."""
        if not self._machine.connect():
            log.warning('Stenograph machine is not connected')
            self._error()
            return
        super(Stenograph, self).start_capture()

    def _reconnect(self):
        self._initializing()
        connected = self._machine.connect()
        # Reconnect loop
        while not self.finished.isSet() and not connected:
            sleep(0.5)
            connected = self._machine.connect()
        return connected

    def run(self):
        self._ready()
        realtime = False

        while not self.finished.isSet():
            try:
                response = self._machine.read()
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
                    keys = Stenograph.process_steno_packet(
                        response[HEADER_BYTES:HEADER_BYTES + 4]
                    )
                    if keys:
                        self._on_stroke(keys)

    def stop_capture(self):
        """Stop listening for output from the stenotype machine."""
        super(Stenograph, self).stop_capture()
        self._machine = None
        self._stopped()

    @staticmethod
    def process_steno_packet(self, steno):
        keys = []
        for byte_number, byte in enumerate(steno):
            byte_keys = STENO_KEY_CHART[byte_number]
            for i in range(6):
                if (byte >> i) & 1:
                    key = byte_keys[-i + 5]
                    if key:
                        keys.append(key)
        return keys