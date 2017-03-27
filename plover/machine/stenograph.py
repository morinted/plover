from itertools import compress
from struct import *
from time import sleep

import sys
from more_itertools import grouper
from plover.machine.base import ThreadedStenotypeBase
from plover import log

'''
Packet format:
--------------
Name:     Size:       Value Range:
----------------------------------
Sync          2 bytes "SG"
Sequence #    4 bytes 0 - 0xFFFFFFFF (will wrap from 0xFFFFFFFF to 0x00000000)
Packet ID     2 bytes As Defined (used as packet type)
Data Length   4 bytes 0 - size (limited in most writers to 65536 bytes)
Parameter 1   4 bytes As Defined
Parameter 2   4 bytes As Defined
Parameter 3   4 bytes As Defined
Parameter 4   4 bytes As Defined
Parameter 5   4 bytes As Defined

Command 0x13 Read Bytes
-----------------------

Request (from PC)
Description   Packet ID   Data Length       Param 1       Param 2     Param 3     Param 4     Param 5
------------------------------------------------------------------------------------------------------
Read Bytes   0x0013       00000000          File Offset   Byte Count  00000000    00000000    00000000

-Parameter 1 contains the file offset from which the Mira should start returning bytes (or stroke number * 8 since there are 8 bytes returned per stroke (see details of Response))
-Parameter 2 contains the maximum number of bytes the Host wants the Mira to send in response to this request
-The Mira will respond to this packet with a successful Read Bytes packet or an Error packet.

Response (from Mira)
Description   Packet ID   Data Length       Param 1       Param 2     Param 3     Param 4     Param 5
------------------------------------------------------------------------------------------------------
Read Bytes    0x0013      Number of Bytes   File Offset   00000000    00000000    00000000    00000000

-Parameter 1 contains the file offset from which the Mira is returning bytes
-For real-time the data is four bytes of steno and 4 bytes of timestamp - 8 bytes per stroke - repeating for the number of strokes returned.  
The format of the eight bytes will be:
-Byte 0: 11^#STKP
-Byte 1: 11WHRAO*
-Byte 2: 11EUFRPB
-Byte 3: 11LGTSDZ
-Bytes 4-7: 'timestamp'
-The steno is in the (very) old SmartWriter format where the top two bits of each of the four bytes are set to 1 and the bottom 6 bits as set according to the keys pressed.
-If the Data Length is zero that indicates there are no more bytes available (real-time).  
-If the file has been closed (on the writer) an Error packet (error: FileClosed) will be sent in response to Read Bytes.

Description   Packet ID   Data Length       Param 1       Param 2     Param 3     Param 4     Param 5
------------------------------------------------------------------------------------------------------
Open File     0x0012      Number of Bytes   Disk ID

- Parameter 1 is the disk ID that the file you wish to open is on (disk A for all intents and purposes)
- Data is the filename, probably 'REALTIME.000'
'''

# ^ is the "stenomark"
STENO_KEY_CHART = (
    ('^', '#', 'S-', 'T-', 'K-', 'P-'),
    ('W-', 'H-', 'R-', 'A-', 'O-', '*'),
    ('-E', '-U', '-F', '-R', '-P', '-B'),
    ('-L', '-G', '-T', '-S', '-D', '-Z'),
)

VENDOR_ID = 0x112b
MAX_READ = 0x200  # Arbitrary read limit


class StenoPacket(object):
    """
    Stenograph StenoPacket helper

    Can be used to create packets to send to the writer, as well as
    decode a packet from the writer.
    """
    _SYNC = b'SG'

    """
    Packet header format:
    'SG'     sequence number  packet ID  data length p1,p2,p3,p4,p5
    2 chars  4 bytes          2 bytes    4 bytes     4 bytes each
    """
    _STRUCT_FORMAT = '<2sIH6I'
    HEADER_SIZE = calcsize(_STRUCT_FORMAT)
    _STRUCT = Struct(_STRUCT_FORMAT)

    ID_ERROR = 0x6
    ID_OPEN = 0x12
    ID_READ = 0x13

    
    sequence_number = 0

    def __init__(self, sequence_number=None, packet_id=0, data_length=None, p1=0, p2=0, p3=0, p4=0, p5=0, data=b''):
        """Create a USB Packet

        sequence_number -- ideally unique, if not passed one will be assigned sequentially.

        packet_id -- type of packet.

        data_length -- length of the additional data, calculated if not provided.

        p1, p2, p3, p4, p5 -- 4 byte parameters that have different roles based on packet_id

        data -- data to be appended to the end of the packet, used for steno strokes from the writer.
        """
        if sequence_number is None:
            sequence_number = StenoPacket.sequence_number
            StenoPacket._increment_sequence_number()
        if data_length is None:
            data_length = len(data)
        self.sequence_number = sequence_number
        self.packet_id = packet_id
        self.data_length = data_length
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.p4 = p4
        self.p5 = p5
        self.data = data

    def __str__(self):
        return (
            'USBPacket(sequence_number=%s, '
            'packet_id=%s, data_length=%s, '
            'p1=%s, p2=%s, p3=%s, p4=%s, p5=%s, data=%s)'
            % (hex(self.sequence_number), hex(self.packet_id),
               self.data_length, hex(self.p1), hex(self.p2),
               hex(self.p3), hex(self.p4), hex(self.p5),
               self.data[:self.data_length])
        )

    def pack(self):
        """Convert this USB Packet into something that can be sent to the writer."""
        return self._STRUCT.pack(
            self._SYNC, self.sequence_number, self.packet_id, self.data_length,
            self.p1, self.p2, self.p3, self.p4, self.p5
        ) + (
            pack('%ss' % len(self.data), self.data)
        )

    @staticmethod
    def _increment_sequence_number():
        StenoPacket.sequence_number = (StenoPacket.sequence_number + 1) % 0xFFFFFFFF

    @staticmethod
    def unpack(usb_packet):
        """Create a USBPacket from raw data"""
        packet = StenoPacket(
            # Drop sync when unpacking.
            *StenoPacket._STRUCT.unpack(usb_packet[:StenoPacket.HEADER_SIZE])[1:]
        )
        if packet.data_length:
            packet.data, = unpack(
                '%ss' % packet.data_length,
                usb_packet[StenoPacket.HEADER_SIZE:StenoPacket.HEADER_SIZE + packet.data_length]
            )
        return packet

    @staticmethod
    def make_open_request(file_name=b'REALTIME.000', disk_id=b'A'):
        """Request to open a file on the writer, defaults to the realtime file."""
        return StenoPacket(
            packet_id=StenoPacket.ID_OPEN,
            p1=ord(disk_id),
            data=file_name,
        )

    @staticmethod
    def make_read_request(file_offset=1, byte_count=MAX_READ):
        """Request to read from the writer, defaults to settings required when reading from realtime file."""
        return StenoPacket(
            packet_id=StenoPacket.ID_READ,
            p1=file_offset,
            p2=byte_count,
        )

    def strokes(self):
        """Get list of strokes represented in this packet's data"""

        # Expecting 8-byte chords (4 bytes of steno, 4 of timestamp.)
        assert self.data_length % 8 == 0
        # Steno should only be present on ACTION_READ packets
        assert self.packet_id == self.ID_READ

        strokes = []
        for stroke_data in grouper(8, self.data, 0):
            stroke = []
            # Get 4 bytes of steno, ignore timestamp.
            for byte, byte_keys in zip(stroke_data[:4], STENO_KEY_CHART):
                if byte is None or byte < 0b11000000:
                    continue
                # Only interested in right 6 values
                key_mask = [int(i) for i in bin(byte)[-6:]]
                stroke.extend(compress(byte_keys, key_mask))
            if stroke:
                strokes.append(stroke)
        return strokes


if sys.platform.startswith('win32'):
    from ctypes import *
    from ctypes.wintypes import DWORD, HANDLE, BYTE
    import uuid

    class DeviceInterfaceData(Structure):
        _fields_ = [
            ('cbSize', DWORD),
            ('InterfaceClassGuid', BYTE * 16),
            ('Flags', DWORD),
            ('Reserved', POINTER(c_ulonglong))
        ]

    # Class GUID / UUID for Stenograph USB Writer
    USB_WRITER_GUID = uuid.UUID('{c5682e20-8059-604a-b761-77c4de9d5dbf}')

    # For Windows we directly call Windows API functions
    SetupDiGetClassDevs = windll.setupapi.SetupDiGetClassDevsA
    SetupDiEnumDeviceInterfaces = windll.setupapi.SetupDiEnumDeviceInterfaces
    SetupDiGetInterfaceDeviceDetail = (
        windll.setupapi.SetupDiGetDeviceInterfaceDetailA)
    CreateFile = windll.kernel32.CreateFileA
    ReadFile = windll.kernel32.ReadFile
    WriteFile = windll.kernel32.WriteFile
    CloseHandle = windll.kernel32.CloseHandle
    GetLastError = windll.kernel32.GetLastError

    # USB Writer 'defines'
    INVALID_HANDLE_VALUE = -1
    ERROR_INSUFFICIENT_BUFFER = 122
    USB_NO_RESPONSE = -9
    RT_FILE_ENDED_ON_WRITER = -8

    class StenographMachine(object):
        def __init__(self):
            self._connected = False
            self._usb_device = HANDLE(0)
            self._read_buffer = create_string_buffer(MAX_READ + StenoPacket.HEADER_SIZE)

        @staticmethod
        def _open_device_instance(device_info, guid):
            dev_interface_data = DeviceInterfaceData()
            dev_interface_data.cbSize=sizeof(dev_interface_data)

            status = SetupDiEnumDeviceInterfaces(
                device_info, None, guid.bytes, 0, byref(dev_interface_data))
            if status == 0:
                return INVALID_HANDLE_VALUE

            request_length = DWORD(0)
            # Call with None to see how big a buffer we need for detail data.
            SetupDiGetInterfaceDeviceDetail(
                device_info,
                byref(dev_interface_data),
                None,
                0,
                pointer(request_length),
                None
            )
            error = GetLastError()
            if error != ERROR_INSUFFICIENT_BUFFER:
                return INVALID_HANDLE_VALUE

            characters = request_length.value

            class DeviceDetailData(Structure):
                _fields_ = [('cbSize', DWORD),
                            ('DevicePath', c_char * characters)]
            dev_detail_data = DeviceDetailData()
            dev_detail_data.cbSize = 5  # DWORD + 4 byte pointer

            # Now put the actual detail data into the buffer
            status = SetupDiGetInterfaceDeviceDetail(
                device_info, byref(dev_interface_data), byref(dev_detail_data),
                characters, pointer(request_length), None
            )
            if not status:
                return INVALID_HANDLE_VALUE
            return CreateFile(
                dev_detail_data.DevicePath,
                0xC0000000, 0x3, 0, 0x3, 0x80, 0
            )

        @staticmethod
        def _open_device_by_class_interface_and_instance(classguid):
            device_info = SetupDiGetClassDevs(classguid.bytes, 0, 0, 0x12)
            if device_info == INVALID_HANDLE_VALUE:
                return INVALID_HANDLE_VALUE

            usb_device = StenographMachine._open_device_instance(
                device_info, classguid)
            return usb_device

        def _usb_write_packet(self, request):
            if self._usb_device == INVALID_HANDLE_VALUE:
                return 0

            bytes_written = DWORD(0)
            request_packet = request.pack()
            WriteFile(
                self._usb_device,
                request_packet,
                StenoPacket.HEADER_SIZE + request.data_length,
                byref(bytes_written),
                None
            )
            if bytes_written.value < StenoPacket.HEADER_SIZE:
                raise IOError('Machine read or write failed')

        def _usb_read_packet(self):
            assert self._usb_device != INVALID_HANDLE_VALUE, 'device not open'

            bytes_read = DWORD(0)
            ReadFile(
              self._usb_device,
              byref(self._read_buffer),
              MAX_READ + StenoPacket.HEADER_SIZE,
              byref(bytes_read),
              None
            )
            # Return None if not enough data was read.
            if bytes_read.value < StenoPacket.HEADER_SIZE:
                raise IOError('Machine read or write failed')

            writer_packet = StenoPacket.unpack(self._read_buffer)
            return writer_packet

        def disconnect(self):
            CloseHandle(self._usb_device)
            self._usb_device = INVALID_HANDLE_VALUE

        def connect(self):
            # If already connected, disconnect first.
            if self._usb_device != INVALID_HANDLE_VALUE:
                self.disconnect()
            self._usb_device = (
                self._open_device_by_class_interface_and_instance(
                    USB_WRITER_GUID))
            return self._usb_device != INVALID_HANDLE_VALUE

        def send_receive(self, request):
            self._usb_write_packet(request)
            writer_packet = self._usb_read_packet()
            if writer_packet.sequence_number == request.sequence_number:
                return writer_packet
            return None
else:
    from usb import core, util

    class StenographMachine(object):

        def __init__(self):
            super(StenographMachine, self).__init__()
            self._usb_device = None
            self._endpoint_in = None
            self._endpoint_out = None
            self._connected = False

        def connect(self):
            """Attempt to and return connection"""
            # Disconnect device if it's already connected.
            if self._connected:
                self.disconnect()

            # Find the device by the vendor ID.
            usb_device = core.find(idVendor=VENDOR_ID)
            if not usb_device:  # Device not found
                return self._connected

            # Copy the default configuration.
            usb_device.set_configuration()
            config = usb_device.get_active_configuration()
            interface = config[(0, 0)]

            # Get the write endpoint.
            endpoint_out = util.find_descriptor(
                interface,
                custom_match=lambda e:
                    util.endpoint_direction(e.bEndpointAddress) ==
                    util.ENDPOINT_OUT
            )
            assert endpoint_out is not None, 'cannot find write endpoint'

            # Get the read endpoint.
            endpoint_in = util.find_descriptor(
                interface,
                custom_match=lambda e:
                    util.endpoint_direction(e.bEndpointAddress) ==
                    util.ENDPOINT_IN
            )
            assert endpoint_in is not None, 'cannot find read endpoint'

            self._usb_device = usb_device
            self._endpoint_in = endpoint_in
            self._endpoint_out = endpoint_out
            self._connected = True
            return self._connected

        def disconnect(self):
            self._connected = False
            util.dispose_resources(self._usb_device)
            self._usb_device = None
            self._endpoint_in = None
            self._endpoint_out = None

        def send_receive(self, request):
            assert self._connected, 'cannot read from machine if not connected'
            try:
                self._endpoint_out.write(request.pack())
                response = self._endpoint_in.read(
                    MAX_READ + StenoPacket.HEADER_SIZE, 3000)
            except core.USBError:
                raise IOError('Machine read or write failed')
            else:
                if response and len(response) >= StenoPacket.HEADER_SIZE:
                    writer_packet = StenoPacket.unpack(response)
                    # Ignore data if sequence numbers don't match.
                    if writer_packet.sequence_number == request.sequence_number:
                        return writer_packet
                return None


class Stenograph(ThreadedStenotypeBase):

    KEYS_LAYOUT = '''
        #  #  #  #  #  #  #  #  #  #
        S- T- P- H- * -F -P -L -T -D
        S- K- W- R- * -R -B -G -S -Z
              A- O-   -E -U
        ^
    '''
    KEYMAP_MACHINE_TYPE = 'Stentura'

    def __init__(self, params):
        super(Stenograph, self).__init__()
        self._machine = StenographMachine()

    def _on_stroke(self, keys):
        steno_keys = self.keymap.keys_to_actions(keys)
        if steno_keys:
            self._notify(steno_keys)

    def start_capture(self):
        self.finished.clear()
        self._initializing()
        """Begin listening for output from the stenotype machine."""
        if not self._connect_machine():
            log.warning('Stenograph machine is not connected')
            self._error()
        else:
            self._ready()
            self.start()

    def _connect_machine(self):
        connected = False
        try:
            connected = self._machine.connect()
        except ValueError:
            log.warning('Libusb must be installed.')
            self._error()
        except AssertionError as e:
            log.warning('Error connecting: %s', str(e))
            self._error()
        finally:
            return connected

    def _reconnect(self):
        self._initializing()
        connected = False
        while not self.finished.isSet() and not connected:
            sleep(0.25)
            connected = self._connect_machine()
        return connected

    def run(self):
        # Open realtime file
        response = self._machine.send_receive(StenoPacket.make_open_request())
        print('OPEN response from writer:', response)
        while not self.finished.isSet():
            try:
                response = self._machine.send_receive(StenoPacket.make_read_request())
                print('got READ response:', response)
            except IOError as e:
                log.warning(u'Stenograph machine disconnected, reconnecting…')
                log.debug('Stenograph exception: %s', str(e))
                if self._reconnect():
                    log.warning('Stenograph reconnected.')
                    self._ready()
            else:
                if response is None:
                    continue
                # Check for error packet
                if response.packet_id == StenoPacket.ID_ERROR:
                    error_number = response.p1
                    # Unable to perform request
                    if error_number == 3:
                        pass
                    # File not available
                    if error_number == 7:
                        pass
                    # No realtime file
                    if error_number == 8:
                        # Realtime file should appear once user starts writing.
                        # TODO: wrap this in try catch or move it somewhere better.
                        self._machine.send_receive(StenoPacket.make_open_request())
                    # Finished reading closed file
                    if error_number == 9:
                        pass
                elif response.packet_id == StenoPacket.ID_READ and response.data_length:
                    chords = response.strokes()
                    for keys in chords:
                        if keys:
                            self._on_stroke(keys)
        self._machine.disconnect()

    def stop_capture(self):
        """Stop listening for output from the stenotype machine."""
        super(Stenograph, self).stop_capture()
        self._machine = None
        self._stopped()


