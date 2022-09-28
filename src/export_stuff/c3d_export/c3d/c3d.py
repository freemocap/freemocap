'''A Python module for reading and writing C3D files.'''

from __future__ import unicode_literals

import sys
import io
import copy
import numpy as np
import struct
import warnings
import codecs


print("hello Mac from c3d.py")

PROCESSOR_INTEL = 84
PROCESSOR_DEC = 85
PROCESSOR_MIPS = 86

class DataTypes(object):
    ''' Container defining different data types used for reading file data.
        Data types depend on the processor format the file is stored in.
    '''
    def __init__(self, proc_type=PROCESSOR_INTEL):
        self._proc_type = proc_type
        self._little_endian_sys = sys.byteorder == 'little'
        self._native = ((self.is_ieee or self.is_dec) and self.little_endian_sys) or \
                       (self.is_mips and self.big_endian_sys)
        if self.big_endian_sys:
            warnings.warn('Systems with native byte order of big-endian are not supported.')

        if self._proc_type == PROCESSOR_MIPS:
            # Big-Endian (SGI/MIPS format)
            self.float32 = np.dtype(np.float32).newbyteorder('>')
            self.float64 = np.dtype(np.float64).newbyteorder('>')
            self.uint8 = np.uint8
            self.uint16 = np.dtype(np.uint16).newbyteorder('>')
            self.uint32 = np.dtype(np.uint32).newbyteorder('>')
            self.uint64 = np.dtype(np.uint64).newbyteorder('>')
            self.int8 = np.int8
            self.int16 = np.dtype(np.int16).newbyteorder('>')
            self.int32 = np.dtype(np.int32).newbyteorder('>')
            self.int64 = np.dtype(np.int64).newbyteorder('>')
        else:
            # Little-Endian format (Intel or DEC format)
            self.float32 = np.float32
            self.float64 = np.float64
            self.uint8 = np.uint8
            self.uint16 = np.uint16
            self.uint32 = np.uint32
            self.uint64 = np.uint64
            self.int8 = np.int8
            self.int16 = np.int16
            self.int32 = np.int32
            self.int64 = np.int64

    @property
    def is_ieee(self):
        ''' True if the associated file is in the Intel format.
        '''
        return self._proc_type == PROCESSOR_INTEL

    @property
    def is_dec(self):
        ''' True if the associated file is in the DEC format.
        '''
        return self._proc_type == PROCESSOR_DEC

    @property
    def is_mips(self):
        ''' True if the associated file is in the SGI/MIPS format.
        '''
        return self._proc_type == PROCESSOR_MIPS

    @property
    def proc_type(self):
        ''' Get the processory type associated with the data format in the file.
        '''
        processor_type = ['INTEL', 'DEC', 'MIPS']
        return processor_type[self._proc_type - PROCESSOR_INTEL]

    @property
    def native(self):
        ''' True if the native (system) byte order matches the file byte order.
        '''
        return self._native

    @property
    def little_endian_sys(self):
        ''' True if native byte order is little-endian.
        '''
        return self._little_endian_sys

    @property
    def big_endian_sys(self):
        ''' True if native byte order is big-endian.
        '''
        return not self._little_endian_sys

    def decode_string(self, bytes):
        ''' Decode a byte array to a string.
        '''
        # Attempt to decode using different decoders
        decoders = ['utf-8', 'latin-1']
        for dec in decoders:
            try:
                return codecs.decode(bytes, dec)
            except UnicodeDecodeError:
                continue
        # Revert to using default decoder but replace characters
        return codecs.decode(bytes, decoders[0], 'replace')

class Decorator(object):
    '''Base class for extending (decotrating) a python object.
    '''
    def __init__(self, decoratee):
        self._decoratee = decoratee
    def __getattr__(self, name):
        return getattr(self._decoratee, name)

def UNPACK_FLOAT_IEEE(uint_32):
    '''Unpacks a single 32 bit unsigned int to a IEEE float representation
    '''
    return struct.unpack('f', struct.pack("<I", uint_32))[0]


def UNPACK_FLOAT_MIPS(uint_32):
    '''Unpacks a single 32 bit unsigned int to a IEEE float representation
    '''
    return struct.unpack('f', struct.pack(">I", uint_32))[0]


def DEC_to_IEEE(uint_32):
    '''Convert the 32 bit representation of a DEC float to IEEE format.

    Params:
    ----
    uint_32 : 32 bit unsigned integer containing the DEC single precision float point bits.
    Returns : IEEE formated floating point of the same shape as the input.
    '''
    # Follows the bit pattern found:
    # 	http://home.fnal.gov/~yang/Notes/ieee_vs_dec_float.txt
    # Further formating descriptions can be found:
    # 	http://www.irig106.org/docs/106-07/appendixO.pdf
    # In accodance with the first ref. first & second 16 bit words are placed
    # in a big endian 16 bit word representation, and needs to be inverted.
    # Second reference describe the DEC->IEEE conversion.

    # Warning! Unsure if NaN numbers are managed appropriately.

    # Shuffle the first two bit words from DEC bit representation to an ordered representation.
    # Note that the most significant fraction bits are placed in the first 7 bits.
    #
    # Below are the DEC layout in accordance with the references:
    # ___________________________________________________________________________________
    # |		Mantissa (16:0)		|	SIGN	|	Exponent (8:0)	|	Mantissa (23:17)	|
    # ___________________________________________________________________________________
    # |32-					  -16|	 15	   |14-				  -7|6-					  -0|
    #
    # Legend:
    # _______________________________________________________
    # | Part (left bit of segment : right bit) | Part | ..
    # _______________________________________________________
    # |Bit adress -     ..       - Bit adress | Bit adress - ..
    ####

    # Swap the first and last 16  bits for a consistent alignment of the fraction
    reshuffled = ((uint_32 & 0xFFFF0000) >> 16) | ((uint_32 & 0x0000FFFF) << 16)
    # After the shuffle each part are in little-endian and ordered as: SIGN-Exponent-Fraction
    exp_bits = ((reshuffled & 0xFF000000) - 1) & 0xFF000000
    reshuffled = (reshuffled & 0x00FFFFFF) | exp_bits
    return UNPACK_FLOAT_IEEE(reshuffled)


def DEC_to_IEEE_BYTES(bytes):
    '''Convert byte array containing 32 bit DEC floats to IEEE format.

    Params:
    ----
    bytes : Byte array where every 4 bytes represent a single precision DEC float.
    Returns : IEEE formated floating point of the same shape as the input.
    '''

    # See comments in DEC_to_IEEE() for DEC format definition

    # Reshuffle
    byte_type = np.dtype('B')
    bytes = np.frombuffer(bytes, dtype=byte_type) #  == memoryview(bytes)
    reshuffled = np.empty(len(bytes), dtype=byte_type)
    reshuffled[0::4] = bytes[2::4]
    reshuffled[1::4] = bytes[3::4]
    reshuffled[2::4] = bytes[0::4]
    # Decrement exponent by 2, if exp. > 1
    reshuffled[3::4] = bytes[1::4] + (np.bitwise_and(bytes[1::4], 0x7f) == 0) - 1

    # There are different ways to adjust for differences in DEC/IEEE representation
    # after reshuffle. Two simple methods are:
    # 1) Decrement exponent bits by 2, then convert to IEEE.
    # 2) Convert to IEEE directly and divide by four.
    # 3) Handle edge cases, expensive in python...
    # However these are simple methods, and do not accurately convert when:
    # 1) Exponent < 2 (without bias), impossible to decrement exponent without adjusting fraction/mantissa.
    # 2) Exponent == 0, DEC numbers are then 0 or undefined while IEEE is not. NaN are produced when exponent == 255.
    # Here method 1) is used, which mean that only small numbers will be represented incorrectly.

    return np.frombuffer(reshuffled.tobytes(),
                         dtype=np.float32,
                         count=int(len(bytes) / 4))

def is_integer(value):
    '''Check if value input is integer.'''
    return isinstance(value, (int, np.int32, np.int64))

def is_iterable(value):
    '''Check if value is iterable.'''
    return hasattr(value, '__iter__')

def type_npy2struct(dtype):
    ''' Convert numpy dtype format to a struct package format string.
    '''
    return dtype.byteorder + dtype.char

class Header(object):
    '''Header information from a C3D file.

    Attributes
    ----------
    event_block : int
        Index of the 512-byte block where labels (metadata) are found.
    parameter_block : int
        Index of the 512-byte block where parameters (metadata) are found.
    data_block : int
        Index of the 512-byte block where data starts.
    point_count : int
        Number of motion capture channels recorded in this file.
    analog_count : int
        Number of analog values recorded per frame of 3D point data.
    first_frame : int
        Index of the first frame of data.
    last_frame : int
        Index of the last frame of data.
    analog_per_frame : int
        Number of analog frames per frame of 3D point data. The analog frame
        rate (ANALOG:RATE) is equivalent to the point frame rate (POINT:RATE)
        times the analog per frame value.
    frame_rate : float
        The frame rate of the recording, in frames per second.
    scale_factor : float
        Multiply values in the file by this scale parameter.
    long_event_labels : bool
    max_gap : int

    .. note::
        The ``scale_factor`` attribute is not used in Phasespace C3D files;
        instead, use the POINT.SCALE parameter.

    .. note::
        The ``first_frame`` and ``last_frame`` header attributes are not used in
        C3D files generated by Phasespace. Instead, the first and last
        frame numbers are stored in the POINTS:ACTUAL_START_FIELD and
        POINTS:ACTUAL_END_FIELD parameters.
    '''

    # Read/Write header formats, read values as unsigned ints rather then floats.
    BINARY_FORMAT_WRITE = '<BBHHHHHfHHf274sHHH164s44s'
    BINARY_FORMAT_READ = '<BBHHHHHIHHI274sHHH164s44s'
    BINARY_FORMAT_READ_BIG_ENDIAN = '>BBHHHHHIHHI274sHHH164s44s'

    def __init__(self, handle=None):
        '''Create a new Header object.

        Parameters
        ----------
        handle : file handle, optional
            If given, initialize attributes for the Header from this file
            handle. The handle must be seek-able and readable. If `handle` is
            not given, Header attributes are initialized with default values.
        '''
        self.parameter_block = 2
        self.data_block = 3

        self.point_count = 50
        self.analog_count = 0

        self.first_frame = 1
        self.last_frame = 1
        self.analog_per_frame = 0
        self.frame_rate = 60.0

        self.max_gap = 0
        self.scale_factor = -1.0
        self.long_event_labels = False
        self.event_count = 0

        self.event_block = b''
        self.event_timings = np.zeros(0, dtype=np.float32)
        self.event_disp_flags = np.zeros(0, dtype=np.bool)
        self.event_labels = []

        if handle:
            self.read(handle)

    def write(self, handle):
        '''Write binary header data to a file handle.

        This method writes exactly 512 bytes to the beginning of the given file
        handle.

        Parameters
        ----------
        handle : file handle
            The given handle will be reset to 0 using `seek` and then 512 bytes
            will be written to describe the parameters in this Header. The
            handle must be writeable.
        '''
        handle.seek(0)
        handle.write(struct.pack(self.BINARY_FORMAT_WRITE,
                                 # Pack vars:
                                 self.parameter_block,
                                 0x50,
                                 self.point_count,
                                 self.analog_count,
                                 self.first_frame,
                                 self.last_frame,
                                 self.max_gap,
                                 self.scale_factor,
                                 self.data_block,
                                 self.analog_per_frame,
                                 self.frame_rate,
                                 b'',
                                 self.long_event_labels and 0x3039 or 0x0,  # If True write long_event_key else 0
                                 self.event_count,
                                 0x0,
                                 self.event_block,
                                 b''))

    def __str__(self):
        '''Return a string representation of this Header's attributes.'''
        return '''\
                  parameter_block: {0.parameter_block}
                      point_count: {0.point_count}
                     analog_count: {0.analog_count}
                      first_frame: {0.first_frame}
                       last_frame: {0.last_frame}
                          max_gap: {0.max_gap}
                     scale_factor: {0.scale_factor}
                       data_block: {0.data_block}
                 analog_per_frame: {0.analog_per_frame}
                       frame_rate: {0.frame_rate}
                long_event_labels: {0.long_event_labels}
                      event_block: {0.event_block}'''.format(self)

    def read(self, handle, fmt=BINARY_FORMAT_READ):
        '''Read and parse binary header data from a file handle.

        This method reads exactly 512 bytes from the beginning of the given file
        handle.

        Parameters
        ----------
        handle : file handle
            The given handle will be reset to 0 using `seek` and then 512 bytes
            will be read to initialize the attributes in this Header. The handle
            must be readable.

        fmt : Formating string used to read the header.

        Raises
        ------
        AssertionError
            If the magic byte from the header is not 80 (the C3D magic value).
        '''
        handle.seek(0)
        raw = handle.read(512)

        (self.parameter_block,
         magic,
         self.point_count,
         self.analog_count,
         self.first_frame,
         self.last_frame,
         self.max_gap,
         self.scale_factor,
         self.data_block,
         self.analog_per_frame,
         self.frame_rate,
         _,
         self.long_event_labels,
         self.event_count,
         __,
         self.event_block,
         _) = struct.unpack(fmt, raw)

        # Check magic number
        assert magic == 80, 'C3D magic {} != 80 !'.format(magic)

        # Check long event key
        self.long_event_labels = self.long_event_labels == 0x3039

    def _processor_convert(self, dtypes, handle):
        ''' Function interpreting the header once a processor type has been determined.
        '''

        if dtypes.is_dec:
            self.scale_factor = DEC_to_IEEE(self.scale_factor)
            self.frame_rate = DEC_to_IEEE(self.frame_rate)
            float_unpack = DEC_to_IEEE
        elif dtypes.is_ieee:
            self.scale_factor = UNPACK_FLOAT_IEEE(self.scale_factor)
            self.frame_rate = UNPACK_FLOAT_IEEE(self.frame_rate)
            float_unpack = UNPACK_FLOAT_IEEE
        elif dtypes.is_mips:
            # Re-read header in big-endian
            self.read(handle, Header.BINARY_FORMAT_READ_BIG_ENDIAN)
            # Then unpack
            self.scale_factor = UNPACK_FLOAT_IEEE(self.scale_factor)
            self.frame_rate = UNPACK_FLOAT_IEEE(self.frame_rate)
            float_unpack = UNPACK_FLOAT_IEEE

        self._parse_events(dtypes, float_unpack)

    def _parse_events(self, dtypes, float_unpack):
        ''' Parse the event section of the header.
        '''

        # Event section byte blocks
        time_bytes = self.event_block[:72]
        disp_bytes = self.event_block[72:90]
        label_bytes = self.event_block[92:]

        if dtypes.is_mips:
            unpack_fmt = '>I'
        else:
            unpack_fmt = '<I'

        read_count = self.event_count
        self.event_timings = np.zeros(read_count, dtype=np.float32)
        self.event_disp_flags = np.zeros(read_count, dtype=np.bool)
        self.event_labels = np.empty(read_count, dtype=object)
        for i in range(read_count):
            ilong = i * 4
            # Unpack
            self.event_disp_flags[i] = disp_bytes[i] > 0
            self.event_timings[i] = float_unpack(struct.unpack(unpack_fmt, time_bytes[ilong:ilong + 4])[0])
            self.event_labels[i] = dtypes.decode_string(label_bytes[ilong:ilong + 4])

    @property
    def events(self):
        ''' Get an iterable over displayed events defined in the header. Iterable items are on form (timing, label).

            Note*:
            Time as defined by the 'timing' is relative to frame 1 and not the 'first_frame' parameter.
            Frame 1 therefor has the time 0.0 in relation to the event timing.
        '''
        return zip(self.event_timings[self.event_disp_flags], self.event_labels[self.event_disp_flags])

    def encode_events(self, events):
        ''' Encode event data in the event block.

        Parameters
        ----------
        events : [(float, str), ...]
            Event data, iterable of touples containing the event timing and a 4 character label string.
             Event timings should be calculated relative to sample 1 with the timing 0.0s, and should
             not be relative to the first_frame header parameter.
        '''
        endian = '<'
        if sys.byteorder == 'big':
            endian = '>'

        # Event block format
        fmt = '{}{}{}{}{}'.format(endian,
                                  str(18 * 4) + 's',  # Timings
                                  str(18) + 's',      # Flags
                                  'H',                # __
                                  str(18 * 4) + 's'   # Labels
                                 )
        # Pack bytes
        event_timings = np.zeros(18, dtype=np.float32)
        event_disp_flags = np.zeros(18, dtype=np.uint8)
        event_labels = np.empty(18, dtype=object)
        label_bytes = bytearray(18 * 4)
        for i, (time, label) in enumerate(events):
            if i > 17:
                # Don't raise Error, header events are rarely used.
                warnings.warn('Maximum of 18 events can be encoded in the header, skipping remaining events.')
                break

            event_timings[i] = time
            event_labels[i] = label
            label_bytes[i * 4:(i + 1) * 4] = label.encode('utf-8')

        write_count = min(i + 1, 18)
        event_disp_flags[:write_count] = 1

        # Update event headers in self
        self.long_event_labels = 0x3039 # Magic number
        self.event_count = write_count
        # Update event block
        self.event_timings = event_timings[:write_count]
        self.event_disp_flags = np.ones(write_count, dtype=np.bool)
        self.event_labels = event_labels[:write_count]
        self.event_block = struct.pack(fmt,
                                       event_timings.tobytes(),
                                       event_disp_flags.tobytes(),
                                       0,
                                       label_bytes
                                      )


class Param(object):
    '''A class representing a single named parameter from a C3D file.

    Attributes
    ----------
    name : str
        Name of this parameter.
    dtype: DataTypes
        Reference to the DataTypes object associated with the file.
    desc : str
        Brief description of this parameter.
    bytes_per_element : int, optional
        For array data, this describes the size of each element of data. For
        string data (including arrays of strings), this should be -1.
    dimensions : list of int
        For array data, this describes the dimensions of the array, stored in
        column-major order. For arrays of strings, the dimensions here will be
        the number of columns (length of each string) followed by the number of
        rows (number of strings).
    bytes : str
        Raw data for this parameter.
    handle :
        File handle positioned at the first byte of a .c3d parameter description.
    '''

    def __init__(self,
                 name,
                 dtype,
                 desc='',
                 bytes_per_element=1,
                 dimensions=None,
                 bytes=b'',
                 handle=None):
        '''Set up a new parameter, only the name is required.'''
        self.name = name
        self._dtypes = dtype
        self.desc = desc
        self.bytes_per_element = bytes_per_element
        self.dimensions = dimensions or []
        self.bytes = bytes
        if handle:
            self.read(handle)

    def __repr__(self):
        return '<Param: {}>'.format(self.desc)

    @property
    def num_elements(self):
        '''Return the number of elements in this parameter's array value.'''
        e = 1
        for d in self.dimensions:
            e *= d
        return e

    @property
    def total_bytes(self):
        '''Return the number of bytes used for storing this parameter's data.'''
        return self.num_elements * abs(self.bytes_per_element)

    def binary_size(self):
        '''Return the number of bytes needed to store this parameter.'''
        return (
            1 +  # group_id
            2 +  # next offset marker
            1 + len(self.name.encode('utf-8')) +  # size of name and name bytes
            1 +  # data size
            # size of dimensions and dimension bytes
            1 + len(self.dimensions) +
            self.total_bytes +  # data
            1 + len(self.desc.encode('utf-8'))  # size of desc and desc bytes
        )

    def write(self, group_id, handle):
        '''Write binary data for this parameter to a file handle.

        Parameters
        ----------
        group_id : int
            The numerical ID of the group that holds this parameter.
        handle : file handle
            An open, writable, binary file handle.
        '''
        name = self.name.encode('utf-8')
        handle.write(struct.pack('bb', len(name), group_id))
        handle.write(name)
        handle.write(struct.pack('<h', self.binary_size() - 2 - len(name)))
        handle.write(struct.pack('b', self.bytes_per_element))
        handle.write(struct.pack('B', len(self.dimensions)))
        handle.write(struct.pack('B' * len(self.dimensions), *self.dimensions))
        if self.bytes is not None and len(self.bytes) > 0:
            handle.write(self.bytes)
        desc = self.desc.encode('utf-8')
        handle.write(struct.pack('B', len(desc)))
        handle.write(desc)

    def read(self, handle):
        '''Read binary data for this parameter from a file handle.

        This reads exactly enough data from the current position in the file to
        initialize the parameter.
        '''
        self.bytes_per_element, = struct.unpack('b', handle.read(1))
        dims, = struct.unpack('B', handle.read(1))
        self.dimensions = [struct.unpack('B', handle.read(1))[
            0] for _ in range(dims)]
        self.bytes = b''
        if self.total_bytes:
            self.bytes = handle.read(self.total_bytes)
        desc_size, = struct.unpack('B', handle.read(1))
        self.desc = desc_size and self._dtypes.decode_string(handle.read(desc_size)) or ''

    def _as(self, dtype):
        '''Unpack the raw bytes of this param as a single value of the given data type.'''
        return np.frombuffer(self.bytes, count=1, dtype=dtype)[0]

    def _as_array(self, dtype, copy=True):
        '''Unpack the raw bytes of this param as an array of the given data type.'''
        assert self.dimensions, \
            '{}: cannot get value as {} array!'.format(self.name, dtype)
        buffer_view = np.frombuffer(self.bytes, dtype=dtype)
        # Reverse shape as the shape is defined in fortran format
        buffer_view = buffer_view.reshape(self.dimensions[::-1])
        if copy:
            return buffer_view.copy()
        return buffer_view

    def _as_any(self, dtype):
        '''Unpack the raw bytes of this param as either an array or single value of the given data type.'''
        if 0 in self.dimensions[:]: 		# Check if any dimension is 0 (empty buffer)
            return [] 						# Buffer is empty

        if len(self.dimensions) == 0:		# Parse data as a single value
            if dtype == np.float32:			# Floats need to be parsed separately!
                return self.float_value
            return self._as(dtype)
        else:								# Parse data as array
            if dtype == np.float32:
                data = self.float_array
            else:
                data = self._as_array(dtype)
            if len(self.dimensions) < 2:    # Check if data is contained in a single dimension
                return data.flatten()
            return data

    @property
    def _as_integer_value(self):
        ''' Get the param as either 32 bit float or unsigned integer.
            Evaluates if an integer is stored as a floating point representation.

            Note: This is implemented purely for parsing start/end frames.
        '''
        if self.total_bytes >= 4:
            # Check if float value representation is an integer
            value = self.float_value
            if int(value) == value:
                return value
            return self.uint32_value
        elif self.total_bytes >= 2:
            return self.uint16_value
        else:
            return self.uint8_value

    @property
    def int8_value(self):
        '''Get the param as an 8-bit signed integer.'''
        return self._as(self._dtypes.int8)

    @property
    def uint8_value(self):
        '''Get the param as an 8-bit unsigned integer.'''
        return self._as(self._dtypes.uint8)

    @property
    def int16_value(self):
        '''Get the param as a 16-bit signed integer.'''
        return self._as(self._dtypes.int16)

    @property
    def uint16_value(self):
        '''Get the param as a 16-bit unsigned integer.'''
        return self._as(self._dtypes.uint16)

    @property
    def int32_value(self):
        '''Get the param as a 32-bit signed integer.'''
        return self._as(self._dtypes.int32)

    @property
    def uint32_value(self):
        '''Get the param as a 32-bit unsigned integer.'''
        return self._as(self._dtypes.uint32)

    @property
    def float_value(self):
        '''Get the param as a 32-bit float.'''
        if self._dtypes.is_dec:
            return DEC_to_IEEE(self._as(np.uint32))
        else:  # is_mips or is_ieee
            return self._as(self._dtypes.float32)

    @property
    def bytes_value(self):
        '''Get the param as a raw byte string.'''
        return self.bytes

    @property
    def string_value(self):
        '''Get the param as a unicode string.'''
        return self._dtypes.decode_string(self.bytes)

    @property
    def int8_array(self):
        '''Get the param as an array of 8-bit signed integers.'''
        return self._as_array(self._dtypes.int8)

    @property
    def uint8_array(self):
        '''Get the param as an array of 8-bit unsigned integers.'''
        return self._as_array(self._dtypes.uint8)

    @property
    def int16_array(self):
        '''Get the param as an array of 16-bit signed integers.'''
        return self._as_array(self._dtypes.int16)

    @property
    def uint16_array(self):
        '''Get the param as an array of 16-bit unsigned integers.'''
        return self._as_array(self._dtypes.uint16)

    @property
    def int32_array(self):
        '''Get the param as an array of 32-bit signed integers.'''
        return self._as_array(self._dtypes.int32)

    @property
    def uint32_array(self):
        '''Get the param as an array of 32-bit unsigned integers.'''
        return self._as_array(self._dtypes.uint32)

    @property
    def int64_array(self):
        '''Get the param as an array of 32-bit signed integers.'''
        return self._as_array(self._dtypes.int64)

    @property
    def uint64_array(self):
        '''Get the param as an array of 32-bit unsigned integers.'''
        return self._as_array(self._dtypes.uint64)

    @property
    def float32_array(self):
        '''Get the param as an array of 32-bit floats.'''
        # Convert float data if not IEEE processor
        if self._dtypes.is_dec:
            # _as_array but for DEC
            assert self.dimensions, \
                '{}: cannot get value as {} array!'.format(self.name, self._dtypes.float32)
            return DEC_to_IEEE_BYTES(self.bytes).reshape(self.dimensions[::-1])  # Reverse fortran format
        else:  # is_ieee or is_mips
            return self._as_array(self._dtypes.float32)

    @property
    def float64_array(self):
        '''Get the param as an array of 64-bit floats.'''
        # Convert float data if not IEEE processor
        if self._dtypes.is_dec:
            raise ValueError('Unable to convert bytes encoded in a 64 bit floating point DEC format.')
        else:  # is_ieee or is_mips
            return self._as_array(self._dtypes.float64)

    @property
    def float_array(self):
        '''Get the param as an array of 32 or 64 bit floats.'''
        # Convert float data if not IEEE processor
        if self.bytes_per_element == 4:
            return self.float32_array
        elif self.bytes_per_element == 8:
            return self.float64_array
        else:
            raise TypeError(
                "Parsing parameter bytes to an array with {} bit floating-point precission is not supported.".format(
                self.bytes_per_element))

    @property
    def int_array(self):
        '''Get the param as an array of integer values.'''
        # Convert float data if not IEEE processor
        if self.bytes_per_element == 1:
            return self.int8_array
        elif self.bytes_per_element == 2:
            return self.int16_array
        elif self.bytes_per_element == 4:
            return self.int32_array
        elif self.bytes_per_element == 8:
            return self.int64_array
        else:
            raise TypeError("Parsing parameter bytes to an array with {} bit integer values is not unsupported.".format(
                            self.bytes_per_element))

    @property
    def uint_array(self):
        '''Get the param as an array of integer values.'''
        # Convert float data if not IEEE processor
        if self.bytes_per_element == 1:
            return self.uint8_array
        elif self.bytes_per_element == 2:
            return self.uint16_array
        elif self.bytes_per_element == 4:
            return self.uint32_array
        elif self.bytes_per_element == 8:
            return self.uint64_array
        else:
            raise TypeError(
                "Parsing parameter bytes to an array with {} bit integer values is not unsupported.".format(
                self.bytes_per_element))

    @property
    def bytes_array(self):
        '''Get the param as an array of raw byte strings.'''
        # Decode different dimensions
        if len(self.dimensions) == 0:
            return np.array([])
        elif len(self.dimensions) == 1:
            return np.array(self.bytes)
        else:
            # Convert Fortran shape (data in memory is identical, shape is transposed)
            word_len = self.dimensions[0]
            dims = self.dimensions[1:][::-1]  # Identical to: [:0:-1]
            byte_steps = np.cumprod(self.dimensions[:-1])[::-1]
            # Generate mult-dimensional array and parse byte words
            byte_arr = np.empty(dims, dtype=object)
            for i in np.ndindex(*dims):
                # Calculate byte offset as sum of each array index times the byte step of each dimension.
                off = np.sum(np.multiply(i, byte_steps))
                byte_arr[i] = self.bytes[off:off+word_len]
            return byte_arr

    @property
    def string_array(self):
        '''Get the param as a python array of unicode strings.'''
        # Decode different dimensions
        if len(self.dimensions) == 0:
            return np.array([])
        elif len(self.dimensions) == 1:
            return np.array([self.string_value])
        else:
            # Parse byte sequences
            byte_arr = self.bytes_array
            # Decode sequences
            for i in np.ndindex(byte_arr.shape):
                byte_arr[i] = self._dtypes.decode_string(byte_arr[i])
            return byte_arr


class Group(object):
    '''A group of parameters from a C3D file.

    In C3D files, parameters are organized in groups. Each group has a name, a
    description, and a set of named parameters.

    Attributes
    ----------
    dtypes : 'DataTypes'
        Data types object used for parsing.
    name : str
        Name of this parameter group.
    desc : str
        Description for this parameter group.
    '''

    def __init__(self, dtypes, name=None, desc=None):
        self._params = {}
        self._dtypes = dtypes
        # Assign through property setters
        self.name = name
        self.desc = desc

    def __repr__(self):
        return '<Group: {}>'.format(self.desc)

    def __contains__(self, key):
        return key in self._params

    @property
    def name(self):
        ''' Group name. '''
        return self._name

    @name.setter
    def name(self, value):
        ''' Group name string.

        Parameters
        ----------
        value : str
            New name for the group.
        '''
        if value is None or isinstance(value, str):
            self._name = value
        else:
            raise TypeError('Expected group name to be string, was {}.'.format(type(value)))

    @property
    def desc(self):
        ''' Group descriptor. '''
        return self._desc

    @desc.setter
    def desc(self, value):
        ''' Group descriptor.

        Parameters
        ----------
        value : str, or bytes
            New description for this parameter group.
        '''
        if isinstance(value, bytes):
            self._desc = self._dtypes.decode_string(value)
        elif isinstance(value, str) or value is None:
            self._desc = value
        else:
            raise TypeError(
                'Expected descriptor to be python string, bytes or None, was {}.'.format(type(value)))

    def param_items(self):
        ''' Acquire iterator for paramater key-entry pairs. '''
        return self._params.items()

    def param_values(self):
        ''' Acquire iterator for parameter entries. '''
        return self._params.values()

    def param_keys(self):
        ''' Acquire iterator for parameter entry keys. '''
        return self._params.keys()

    def get(self, key, default=None):
        '''Get a parameter by key.

        Parameters
        ----------
        key : any
            Parameter key to look up in this group.
        default : any, optional
            Value to return if the key is not found. Defaults to None.

        Returns
        -------
        param : :class:`Param`
            A parameter from the current group.
        '''
        return self._params.get(key, default)

    def add_param(self, name, **kwargs):
        '''Add a parameter to this group.

        Parameters
        ----------
        name : str
            Name of the parameter to add to this group. The name will
            automatically be case-normalized.

        Additional keyword arguments will be passed to the `Param` constructor.

        Raises
        ------
        TypeError
            Input arguments are of the wrong type.
        KeyError
            Name or numerical key already exist (attempt to overwrite existing data).
        '''
        if not isinstance(name, str):
            raise TypeError("Expected 'name' argument to be a string, was of type {}".format(type(name)))
        name = name.upper()
        if name in self._params:
            raise KeyError('Parameter already exists with key {}'.format(name))
        self._params[name] = Param(name, self._dtypes, **kwargs)

    def remove_param(self, name):
        '''Remove the specified parameter.

        Parameters
        ----------
        name : str
            Name for the parameter to remove.
        '''
        del self._params[name]

    def rename_param(self, name, new_name):
        ''' Rename a specified parameter group.

        Parameters
        ----------
        name : str, or 'Param'
            Parameter instance, or name.
        new_name : str
            New name for the parameter.

        Raises
        ------
        KeyError
            If no parameter with the original name exists.
        ValueError
            If the new name already exist (attempt to overwrite existing data).
        '''
        if new_name in self._params:
            raise ValueError("Key {} already exist.".format(new_name))
        if isinstance(name, Param):
            param = name
            name = param.name
        else:
            # Aquire instance using id
            param = self._params.get(name, None)
            if param is None:
                raise KeyError('No parameter found matching the identifier: {}'.format(str(name)))
        del self._params[name]
        self._params[new_name] = param

    def binary_size(self):
        '''Return the number of bytes to store this group and its parameters.'''
        return (
            1 +  # group_id
            1 + len(self._name.encode('utf-8')) +  # size of name and name bytes
            2 +  # next offset marker
            1 + len(self._desc.encode('utf-8')) +  # size of desc and desc bytes
            sum(p.binary_size() for p in self._params.values()))

    def write(self, group_id, handle):
        '''Write this parameter group, with parameters, to a file handle.

        Parameters
        ----------
        group_id : int
            The numerical ID of the group.
        handle : file handle
            An open, writable, binary file handle.
        '''
        name = self._name.encode('utf-8')
        desc = self._desc.encode('utf-8')
        handle.write(struct.pack('bb', len(name), -group_id))
        handle.write(name)
        handle.write(struct.pack('<h', 3 + len(desc)))
        handle.write(struct.pack('B', len(desc)))
        handle.write(desc)
        for param in self._params.values():
            param.write(group_id, handle)

    def get_int8(self, key):
        '''Get the value of the given parameter as an 8-bit signed integer.'''
        return self._params[key.upper()].int8_value

    def get_uint8(self, key):
        '''Get the value of the given parameter as an 8-bit unsigned integer.'''
        return self._params[key.upper()].uint8_value

    def get_int16(self, key):
        '''Get the value of the given parameter as a 16-bit signed integer.'''
        return self._params[key.upper()].int16_value

    def get_uint16(self, key):
        '''Get the value of the given parameter as a 16-bit unsigned integer.'''
        return self._params[key.upper()].uint16_value

    def get_int32(self, key):
        '''Get the value of the given parameter as a 32-bit signed integer.'''
        return self._params[key.upper()].int32_value

    def get_uint32(self, key):
        '''Get the value of the given parameter as a 32-bit unsigned integer.'''
        return self._params[key.upper()].uint32_value

    def get_float(self, key):
        '''Get the value of the given parameter as a 32-bit float.'''
        return self._params[key.upper()].float_value

    def get_bytes(self, key):
        '''Get the value of the given parameter as a byte array.'''
        return self._params[key.upper()].bytes_value

    def get_string(self, key):
        '''Get the value of the given parameter as a string.'''
        return self._params[key.upper()].string_value


class Manager(object):
    '''A base class for managing C3D file metadata.

    This class manages a C3D header (which contains some stock metadata fields)
    as well as a set of parameter groups. Each group is accessible using its
    name.

    Attributes
    ----------
    header : `Header`
        Header information for the C3D file.
    '''

    def __init__(self, header=None):
        '''Set up a new Manager with a Header.'''
        self._header = header or Header()
        self._groups = {}

    def __contains__(self, key):
        return key in self._groups

    @property
    def header(self):
        ''' Access the parsed c3d header. '''
        return self._header

    def group_items(self):
        ''' Acquire iterable over parameter group pairs.

        Returns
        -------
        items : Touple of ((str, :class:`Group`), ...)
            Python touple containing pairs of name keys and parameter group entries.
        '''
        return ((k, v) for k, v in self._groups.items() if isinstance(k, str))

    def group_values(self):
        ''' Acquire iterable over parameter group entries.

        Returns
        -------
        values : Touple of (:class:`Group`, ...)
            Python touple containing unique parameter group entries.
        '''
        return (v for k, v in self._groups.items() if isinstance(k, str))

    def group_keys(self):
        ''' Acquire iterable over parameter group entry string keys.

        Returns
        -------
        keys : Touple of (str, ...)
            Python touple containing keys for the parameter group entries.
        '''
        return (k for k in self._groups.keys() if isinstance(k, str))

    def group_listed(self):
        ''' Acquire iterable over sorted numerical parameter group pairs.

        Returns
        -------
        items : Touple of ((int, :class:`Group`), ...)
            Sorted python touple containing pairs of numerical keys and parameter group entries.
        '''
        return sorted((i, g) for i, g in self._groups.items() if isinstance(i, int))

    def _check_metadata(self):
        ''' Ensure that the metadata in our file is self-consistent. '''
        assert self._header.point_count == self.point_used, (
            'inconsistent point count! {} header != {} POINT:USED'.format(
                self._header.point_count,
                self.point_used,
            ))

        assert self._header.scale_factor == self.point_scale, (
            'inconsistent scale factor! {} header != {} POINT:SCALE'.format(
                self._header.scale_factor,
                self.point_scale,
            ))

        assert self._header.frame_rate == self.point_rate, (
            'inconsistent frame rate! {} header != {} POINT:RATE'.format(
                self._header.frame_rate,
                self.point_rate,
            ))

        if self.point_rate:
            ratio = self.analog_rate / self.point_rate
        else:
            ratio = 0
        assert self._header.analog_per_frame == ratio, (
            'inconsistent analog rate! {} header != {} analog-fps / {} point-fps'.format(
                self._header.analog_per_frame,
                self.analog_rate,
                self.point_rate,
            ))

        count = self.analog_used * self._header.analog_per_frame
        assert self._header.analog_count == count, (
            'inconsistent analog count! {} header != {} analog used * {} per-frame'.format(
                self._header.analog_count,
                self.analog_used,
                self._header.analog_per_frame,
            ))

        try:
            start = self.get_uint16('POINT:DATA_START')
            if self._header.data_block != start:
                warnings.warn('inconsistent data block! {} header != {} POINT:DATA_START'.format(
                    self._header.data_block, start))
        except AttributeError:
            warnings.warn('''no pointer available in POINT:DATA_START indicating the start of the data block, using
                             header pointer as fallback''')

        def check_parameters(params):
            for name in params:
                if self.get(name) is None:
                    warnings.warn('missing parameter {}'.format(name))

        if self.point_used > 0:
            check_parameters(('POINT:LABELS', 'POINT:DESCRIPTIONS'))
        else:
            warnings.warn('No point data found in file.')
        if self.analog_used > 0:
            check_parameters(('ANALOG:LABELS', 'ANALOG:DESCRIPTIONS'))
        else:
            warnings.warn('No analog data found in file.')

    def add_group(self, group_id, name, desc, rename_duplicated_groups=False):
        '''Add a new parameter group.

        Parameters
        ----------
        group_id : int
            The numeric ID for a group to check or create.
        name : str
            If a group is created, assign this name to the group.
            The name will be turned to upper case letters.
        desc : str, optional
            If a group is created, assign this description to the group.
        rename_duplicated_groups : bool
            If True, when adding a group with a name that already exists, the group will be renamed to
            `{name}{group_id}`.
            The original group will not be renamed.
            In general, having multiple groups with the same name is against the c3d specification.
            This option only exists to handle edge cases where files are not created according to the spec and still
            need to be imported.

        Returns
        -------
        group : :class:`Group`
            A group with the given ID, name, and description.

        Raises
        ------
        TypeError
            Input arguments are of the wrong type.
        KeyError
            Name or numerical key already exist (attempt to overwrite existing data).
        '''
        if not is_integer(group_id):
            raise TypeError('Expected Group numerical key to be integer, was {}.'.format(type(group_id)))
        if not isinstance(name, str):
            raise TypeError('Expected Group name key to be string, was {}.'.format(type(name)))
        group_id = int(group_id) # Asserts python int
        if group_id in self._groups:
            raise KeyError('Group with numerical key {} already exists'.format(group_id))
        name = name.upper()
        if name in self._groups:
            if rename_duplicated_groups is True:
                # In some cases group name is not unique (though c3d spec requires that).
                # To allow using such files we auto-generate new name.
                # Notice that referring to this group's parameters later with the original name will fail.
                new_name = name + str(group_id)
                warnings.warn(f'Repeated group name {name} modified to {new_name}')
                name = new_name
            else:
                raise KeyError(f'A group with the name {name} already exists.')

        group = self._groups[name] = self._groups[group_id] = Group(self._dtypes, name, desc)
        return group

    def remove_group(self, group_id):
        '''Remove the parameter group.

        Parameters
        ----------
        group_id : int, or str
            The numeric or name ID key for a group to remove all entries for.
        '''
        grp = self._groups.get(group_id, None)
        if grp is None:
            return
        gkeys = [k for (k, v) in self._groups.items() if v == grp]
        for k in gkeys:
            del self._groups[k]

    def rename_group(self, group_id, new_group_id):
        ''' Rename a specified parameter group.

        Parameters
        ----------
        group_id : int, str, or 'Group'
            Group instance, name, or numerical identifier for the group.
        new_group_id : str, or int
            If string, it is the new name for the group. If integer, it will replace its numerical group id.

        Raises
        ------
        KeyError
            If a group with a duplicate ID or name already exists.
        '''
        if isinstance(group_id, Group):
            grp = group_id
        else:
            # Aquire instance using id
            grp = self._groups.get(group_id, None)
            if grp is None:
                raise KeyError('No group found matching the identifier: {}'.format(group_id))
        if new_group_id in self._groups:
            if new_group_id == group_id:
                return
            raise ValueError('Key {} for the group {} already exist.'.format(new_group_id, grp.name))

        # Clear old id
        if isinstance(new_group_id, (str, bytes)):
            if grp.name in self._groups:
                del self._groups[grp.name]
            grp._name = new_group_id
        elif is_integer(new_group_id):
            new_group_id = int(new_group_id) # Ensure python int
            del self._groups[group_id]
        else:
            raise KeyError('Invalid group identifier of type: {}'.format(type(new_group_id)))
        # Update
        self._groups[new_group_id] = grp

    def get(self, group, default=None):
        '''Get a group or parameter.

        Parameters
        ----------
        group : str
            If this string contains a period (.), then the part before the
            period will be used to retrieve a group, and the part after the
            period will be used to retrieve a parameter from that group. If this
            string does not contain a period, then just a group will be
            returned.
        default : any
            Return this value if the named group and parameter are not found.

        Returns
        -------
        value : :class:`Group` or :class:`Param`
            Either a group or parameter with the specified name(s). If neither
            is found, returns the default value.
        '''
        if is_integer(group):
            return self._groups.get(int(group), default)
        group = group.upper()
        param = None
        if '.' in group:
            group, param = group.split('.', 1)
        if ':' in group:
            group, param = group.split(':', 1)
        if group not in self._groups:
            return default
        group = self._groups[group]
        if param is not None:
            return group.get(param, default)
        return group

    def get_int8(self, key):
        '''Get a parameter value as an 8-bit signed integer.'''
        return self.get(key).int8_value

    def get_uint8(self, key):
        '''Get a parameter value as an 8-bit unsigned integer.'''
        return self.get(key).uint8_value

    def get_int16(self, key):
        '''Get a parameter value as a 16-bit signed integer.'''
        return self.get(key).int16_value

    def get_uint16(self, key):
        '''Get a parameter value as a 16-bit unsigned integer.'''
        return self.get(key).uint16_value

    def get_int32(self, key):
        '''Get a parameter value as a 32-bit signed integer.'''
        return self.get(key).int32_value

    def get_uint32(self, key):
        '''Get a parameter value as a 32-bit unsigned integer.'''
        return self.get(key).uint32_value

    def get_float(self, key):
        '''Get a parameter value as a 32-bit float.'''
        return self.get(key).float_value

    def get_bytes(self, key):
        '''Get a parameter value as a byte string.'''
        return self.get(key).bytes_value

    def get_string(self, key):
        '''Get a parameter value as a string.'''
        return self.get(key).string_value

    def parameter_blocks(self):
        '''Compute the size (in 512B blocks) of the parameter section.'''
        bytes = 4. + sum(g.binary_size() for g in self._groups.values())
        return int(np.ceil(bytes / 512))

    @property
    def point_rate(self):
        ''' Number of sampled 3D coordinates per second.
        '''
        try:
            return self.get_float('POINT:RATE')
        except AttributeError:
            return self.header.frame_rate

    @property
    def point_scale(self):
        try:
            return self.get_float('POINT:SCALE')
        except AttributeError:
            return self.header.scale_factor

    @property
    def point_used(self):
        ''' Number of sampled 3D point coordinates per frame.
        '''
        try:
            return self.get_uint16('POINT:USED')
        except AttributeError:
            return self.header.point_count

    @property
    def analog_used(self):
        ''' Number of analog measurements, or channels, for each analog data sample.
        '''
        try:
            return self.get_uint16('ANALOG:USED')
        except AttributeError:
            return self.header.analog_count

    @property
    def analog_rate(self):
        '''  Number of analog data samples per second.
        '''
        try:
            return self.get_float('ANALOG:RATE')
        except AttributeError:
            return self.header.analog_per_frame * self.point_rate

    @property
    def analog_per_frame(self):
        '''  Number of analog samples per 3D frame (point sample).
        '''
        return int(self.analog_rate / self.point_rate)

    @property
    def analog_sample_count(self):
        ''' Number of analog samples per channel.
        '''
        has_analog = self.analog_used > 0
        return int(self.frame_count * self.analog_per_frame) * has_analog

    @property
    def analog_format(self):
        ''' Format for non-float (integer) analog data as defined by the'ANALOG:FORMAT' parameter.

            Valid values are 'SIGNED' or 'UNSIGNED' indicating that analog data
            is stored as signed or unsigned 16 bit integers. Defaults to 'SIGNED'
            if the parameter does not exist as defined in the standard.
        '''
        param = self.get('ANALOG:FORMAT')
        if param is not None:
            return param.string_value.strip().upper()
        return 'SIGNED'

    @property
    def analog_format_unsigned(self):
        ''' True if analog data stored on integer form should be treated as unsigned (rather then signed).
        '''
        return self.analog_format == 'UNSIGNED'

    @property
    def analog_resolution(self):
        ''' Bit resolution the analog samples are recorded at.

            Reads the 'ANALOG:BITS' parameter to determine the resolution. Valid values mentioned in the standard
            are 12, 14, or 16 bit resolution, with 16 bit defined as standard. Note that the BITS parameter 'should'
            not affect how analog data is stored in the file, rather it is information for how to interpret the data.
        '''
        param = self.get('ANALOG:BITS')
        if param is not None:
            return param.int32_value
        return 'SIGNED'


    @property
    def point_labels(self):
        return self.get('POINT:LABELS').string_array

    @property
    def analog_labels(self):
        return self.get('ANALOG:LABELS').string_array

    @property
    def frame_count(self):
        return self.last_frame - self.first_frame + 1  # Add 1 since range is inclusive [first, last]

    @property
    def first_frame(self):
        # Start frame seems to be less of an issue to determine.
        # this is a hack for phasespace files ... should put it in a subclass.
        param = self.get('TRIAL:ACTUAL_START_FIELD')
        if param is not None:
            # ACTUAL_START_FIELD is encoded in two 16 byte words...
            # return param.uint32_value
            words = param.uint16_array
            return words[0] + words[1] * 65535
        return self.header.first_frame

    @property
    def last_frame(self) -> int:
        ''' Trial frame corresponding to the last frame recorded in the data (inclusive).
        '''
        # Number of frames can be represented in many formats.
        # Start of by  different parameters where the frame can be encoded
        hlf = self.header.last_frame
        param = self.get('TRIAL:ACTUAL_END_FIELD')
        if param is not None:
            # Encoded as 2 16 bit words (rather then 1 32 bit word)
            # Manual refer to parsing the parameter as 2 16-bit words, generally equivalent to an uint32
            # end_frame = param.uint32_value
            words = param.uint16_array
            end_frame = words[0] + words[1] * 65536
            if hlf <= end_frame:
                return end_frame
        param = self.get('POINT:LONG_FRAMES')
        if param is not None:
            # 'Should be' encoded as float
            if param.bytes_per_element >= 4:
                end_frame = int(param.float_value)
            else:
                end_frame = param.uint16_value
            if hlf <= end_frame:
                return end_frame
        param = self.get('POINT:FRAMES')
        if param is not None:
            # Can be encoded either as 32 bit float or 16 bit uint
            if param.bytes_per_element == 4:
                end_frame = int(param.float_value)
            else:
                end_frame = param.uint16_value
            if hlf <= end_frame:
                return end_frame
        # Return header value by default
        return hlf

    def get_screen_axis(self):
        ''' Set the X_SCREEN and Y_SCREEN parameters in the POINT group.

        Returns
        -------
        value : Touple on form (str, str) or None
            Touple containing X_SCREEN and Y_SCREEN strings, or None if no parameters could be found.
        '''
        X = self.get('POINT:X_SCREEN')
        Y = self.get('POINT:Y_SCREEN')
        if X and Y:
            return (X.string_value, Y.string_value)
        return None

    def get_analog_transform_parameters(self):
        ''' Parse analog data transform parameters.
        '''
        # Offsets (return as 32-bit to ensure integer overflow is avoided)
        analog_offsets = np.zeros((self.analog_used), int)
        param = self.get('ANALOG:OFFSET')
        if param is not None and param.num_elements > 0:
            if self.analog_format_unsigned:
                analog_offsets[:] = param.uint16_array[:self.analog_used]
            else:
                analog_offsets[:] = param.int16_array[:self.analog_used]

        # Scale factors
        analog_scales = np.ones((self.analog_used), float)
        gen_scale = 1.
        param = self.get('ANALOG:GEN_SCALE')
        if param is not None:
            gen_scale = param.float_value
        param = self.get('ANALOG:SCALE')
        if param is not None and param.num_elements > 0:
            analog_scales[:] = param.float_array[:self.analog_used]

        return gen_scale, analog_scales, analog_offsets

    def get_analog_transform(self):
        ''' Get broadcastable analog transformation parameters.
        '''
        gen_scale, analog_scales, analog_offsets = self.get_analog_transform_parameters()
        analog_scales *= gen_scale
        analog_scales = np.broadcast_to(analog_scales[:, np.newaxis], (self.analog_used, self.analog_per_frame))
        analog_offsets = np.broadcast_to(analog_offsets[:, np.newaxis], (self.analog_used, self.analog_per_frame))
        return analog_scales, analog_offsets

class Reader(Manager):
    '''This class provides methods for reading the data in a C3D file.

    A C3D file contains metadata and frame-based data describing 3D motion.

    You can iterate over the frames in the file by calling `read_frames()` after
    construction:

    >>> r = c3d.Reader(open('capture.c3d', 'rb'))
    >>> for frame_no, points, analog in r.read_frames():
    ...     print('{0.shape} points in this frame'.format(points))
    '''

    def __init__(self, handle):
        '''Initialize this C3D file by reading header and parameter data.

        Parameters
        ----------
        handle : file handle
            Read metadata and C3D motion frames from the given file handle. This
            handle is assumed to be `seek`-able and `read`-able. The handle must
            remain open for the life of the `Reader` instance. The `Reader` does
            not `close` the handle.

        Raises
        ------
        ValueError
            If the processor metadata in the C3D file is anything other than 84
            (Intel format).
        '''
        super(Reader, self).__init__(Header(handle))

        self._handle = handle

        def seek_param_section_header():
            ''' Seek to and read the first 4 byte of the parameter header section '''
            self._handle.seek((self._header.parameter_block - 1) * 512)
            # metadata header
            return self._handle.read(4)

        # Begin by reading the processor type:
        buf = seek_param_section_header()
        _, _, parameter_blocks, processor = struct.unpack('BBBB', buf)
        self._dtypes = DataTypes(processor)
        # Convert header parameters in accordance with the processor type (MIPS format re-reads the header)
        self._header._processor_convert(self._dtypes, handle)

        # Restart reading the parameter header after parsing processor type
        buf = seek_param_section_header()

        start_byte = self._handle.tell()
        endbyte = start_byte + 512 * parameter_blocks - 4
        while self._handle.tell() < endbyte:
            chars_in_name, group_id = struct.unpack('bb', self._handle.read(2))
            if group_id == 0 or chars_in_name == 0:
                # we've reached the end of the parameter section.
                break
            name = self._dtypes.decode_string(self._handle.read(abs(chars_in_name))).upper()

            # Read the byte segment associated with the parameter and create a
            # separate binary stream object from the data.
            offset_to_next, = struct.unpack(['<h', '>h'][self._dtypes.is_mips], self._handle.read(2))
            if offset_to_next == 0:
                # Last parameter, as number of bytes are unknown,
                # read the remaining bytes in the parameter section.
                bytes = self._handle.read(endbyte - self._handle.tell())
            else:
                bytes = self._handle.read(offset_to_next - 2)
            buf = io.BytesIO(bytes)

            if group_id > 0:
                # We've just started reading a parameter. If its group doesn't
                # exist, create a blank one. add the parameter to the group.
                group = self._groups.setdefault(group_id, Group(self._dtypes))
                group.add_param(name, handle=buf)
            else:
                # We've just started reading a group. If a group with the
                # appropriate numerical id exists already (because we've
                # already created it for a parameter), just set the name of
                # the group. Otherwise, add a new group.
                group_id = abs(group_id)
                size, = struct.unpack('B', buf.read(1))
                desc = size and buf.read(size) or ''
                group = self.get(group_id)
                if group is not None:
                    self.rename_group(group, name)  # Inserts name key
                    group.desc = desc
                else:
                    # We allow duplicated group names here, even though it is against the c3d spec.
                    # The groups will be renamed.
                    self.add_group(group_id, name, desc, rename_duplicated_groups=True)

        self._check_metadata()

    def read_frames(self, copy=True, analog_transform=True, camera_sum=False, check_nan=True):
        '''Iterate over the data frames from our C3D file handle.

        Parameters
        ----------
        copy : bool
            If False, the reader returns a reference to the same data buffers
            for every frame. The default is True, which causes the reader to
            return a unique data buffer for each frame. Set this to False if you
            consume frames as you iterate over them, or True if you store them
            for later.
        analog_transform : bool, default=True
            If True, ANALOG:SCALE, ANALOG:GEN_SCALE, and ANALOG:OFFSET transforms
            defined in the file will be applied to the analog channels.
        check_nan : bool, default=True
            If True, X,Y,Z point coordinate channels will be checked for NaN values, replacing occurences with 0.
            Samples containing NaN values are also marked as invalid (residual channel value is set to -1).
        camera_sum : bool, default=False
            Camera flag bits will be summed, converting the fifth column to a camera visibility counter.
        Returns
        -------
        frames : sequence of (frame number, points, analog)
            This method generates a sequence of (frame number, points, analog)
            tuples, one tuple per frame. The first element of each tuple is the
            frame number. The second is a numpy array of parsed, 5D point data.
            Third element of each tuple is a numpy array of analog
            values that were recorded during the frame. It is common for the analog data
            to be sampled at a higher frequency than the 3D point data, resulting
            in multiple analog frames per frame of point data.
            The first three columns in the returned point data are the (x, y, z)
            coordinates of the observed motion capture point. The fourth column
            is an estimate of the error for this particular point, and the fifth
            column is the number of cameras that observed the point in question.
            Both the fourth and fifth values are -1 if the point is considered
            to be invalid.
        '''
        # Point magnitude scalar, if scale parameter is < 0 data is floating point
        # (in which case the magnitude is the absolute value)
        scale_mag = abs(self.point_scale)
        is_float = self.point_scale < 0

        if is_float:
            point_word_bytes = 4
        else:
            point_word_bytes = 2
        points = np.zeros((self.point_used, 5), np.float32)

        if is_float:
            # Note*: Floating point is 'always' defined for both analog and point data, according to the standard.
            analog_dtype = self._dtypes.float32
            analog_word_bytes = 4
        elif self.analog_format_unsigned:
            analog_dtype = self._dtypes.uint16
            analog_word_bytes = 2
        else:
            analog_dtype = self._dtypes.int16
            analog_word_bytes = 2

        analog = np.array([], float)
        analog_scales, analog_offsets = self.get_analog_transform()

        # Seek to the start point of the data blocks
        self._handle.seek((self._header.data_block - 1) * 512)
        # Number of values (words) read in regard to POINT/ANALOG data
        N_point = 4 * self.point_used
        N_analog = self.analog_used * self.analog_per_frame

        # Total bytes per frame
        point_bytes = N_point * point_word_bytes
        analog_bytes = N_analog * analog_word_bytes
        # Parse the data blocks
        for frame_no in range(self.first_frame, self.last_frame + 1):
            # Read the byte data (used) for the block
            raw_bytes = self._handle.read(N_point * point_word_bytes)
            raw_analog = self._handle.read(N_analog * analog_word_bytes)
            # Verify read pointers (any of the two can be assumed to be 0)
            if len(raw_bytes) < point_bytes:
                warnings.warn('''reached end of file (EOF) while reading POINT data at frame index {}
                                 and file pointer {}!'''.format(frame_no - self.first_frame, self._handle.tell()))
                return
            if len(raw_analog) < analog_bytes:
                warnings.warn('''reached end of file (EOF) while reading POINT data at frame index {}
                                 and file pointer {}!'''.format(frame_no - self.first_frame, self._handle.tell()))
                return

            if is_float:
                # Convert every 4 byte words to a float-32 reprensentation
                # (the fourth column is still not a float32 representation)
                if self._dtypes.is_dec:
                    # Convert each of the first 6 16-bit words from DEC to IEEE float
                    points[:, :4] = DEC_to_IEEE_BYTES(raw_bytes).reshape((self.point_used, 4))
                else:  # If IEEE or MIPS:
                    # Convert each of the first 6 16-bit words to native float
                    points[:, :4] = np.frombuffer(raw_bytes,
                                                  dtype=self._dtypes.float32,
                                                  count=N_point).reshape((self.point_used, 4))

                # Cast last word to signed integer in system endian format
                last_word = points[:, 3].astype(np.int32)

            else:
                # View the bytes as signed 16-bit integers
                raw = np.frombuffer(raw_bytes,
                                    dtype=self._dtypes.int16,
                                    count=N_point).reshape((self.point_used, 4))
                # Read the first six 16-bit words as x, y, z coordinates
                points[:, :3] = raw[:, :3] * scale_mag
                # Cast last word to signed integer in system endian format
                last_word = raw[:, 3].astype(np.int16)

            # Parse camera-observed bits and residuals.
            # Notes:
            # - Invalid sample if residual is equal to -1 (check if word < 0).
            # - A residual of 0.0 represent modeled data (filtered or interpolated).
            # - Camera and residual words are always 8-bit (1 byte), never 16-bit.
            # - If floating point, the byte words are encoded in an integer cast to a float,
            #    and are written directly in byte form (see the MLS guide).
            ##
            # Read the residual and camera byte words (Note* if 32 bit word negative sign is discarded).
            residual_byte, camera_byte = (last_word & 0x00ff), (last_word & 0x7f00) >> 8
            #if self._dtypes.big_endian_sys -> swap words?

            # Fourth value is floating-point (scaled) error estimate (residual)
            points[:, 3] = residual_byte * scale_mag

            # Determine invalid samples
            invalid = last_word < 0
            if check_nan:
                is_nan = ~np.all(np.isfinite(points[:, :4]), axis=1)
                points[is_nan, :3] = 0.0
                invalid |= is_nan
            # Update discarded - sign
            points[invalid, 3] = -1


            # Fifth value is the camera-observation byte
            if camera_sum:
                # Convert to observation sum
                points[:, 4] = sum((camera_byte & (1 << k)) >> k for k in range(8))
            else:
                points[:, 4] = camera_byte #.astype(np.float32)

            # Check if analog data exist, and parse if so
            if N_analog > 0:
                if is_float and self._dtypes.is_dec:
                    # Convert each of the 16-bit words from DEC to IEEE float
                    analog = DEC_to_IEEE_BYTES(raw_analog)
                else:
                    # Integer or INTEL/MIPS floating point data can be parsed directly
                    analog = np.frombuffer(raw_analog, dtype=analog_dtype, count=N_analog)

                # Reformat and convert
                analog = analog.reshape((-1, self.analog_used)).T
                analog = analog.astype(float)
                # Convert analog
                analog = (analog - analog_offsets) * analog_scales

            # Output buffers
            if copy:
                yield frame_no, points.copy(), analog  # .copy(), a new array is generated per frame for analog data.
            else:
                yield frame_no, points, analog

        # Function evaluating EOF, note that data section is written in blocks of 512
        final_byte_index = self._handle.tell()
        self._handle.seek(0, 2)  # os.SEEK_END)
        # Check if more then 1 block remain
        if self._handle.tell() - final_byte_index >= 512:
            warnings.warn('incomplete reading of data blocks. {} bytes remained after all datablocks were read!'.format(
                self._handle.tell() - final_byte_index))

    @property
    def proc_type(self):
        '''Get the processory type associated with the data format in the file.
        '''
        return self._dtypes.proc_type

    def to_writer(self, conversion):
        ''' Convert to 'Writer' using the conversion mode.
            See Writer.from_reader() for supported conversion modes and possible exceptions.
        '''
        return Writer.from_reader(self, conversion=conversion)


class GroupEditable(Decorator):
    ''' Group instance decorator providing convenience functions for Writer editing.
    '''
    def __init__(self, group):
        super(GroupEditable, self).__init__(group)

    def __contains__(self, key):
        return key in self._decoratee
    #
    #   Add decorator functions (throws on overwrite)
    #
    def add(self, name, desc, bpe, format, data, *dimensions):
        ''' Add a parameter with 'data' package formated in accordance with 'format'.
        '''
        if isinstance(data, bytes):
            pass
        else:
            data = struct.pack(format, data)

        self.add_param(name,
                       desc=desc,
                       bytes_per_element=bpe,
                       bytes=data,
                       dimensions=list(dimensions))

    def add_array(self, name, desc, data, dtype=None):
        '''Add a parameter with the 'data' package.

        Arguments
        ---------
        data : Numpy array, or python iterable.
        dtype : Numpy dtype to encode the array (Optional if data is numpy type).
        '''
        if not isinstance(data, np.ndarray):
            if dtype is not None:
                raise ValueError('Must specify dtype when passning non-numpy array type.')
            data = np.array(data, dtype=dtype)
        elif dtype is None:
            dtype = data.dtype

        self.add_param(name,
                       desc=desc,
                       bytes_per_element=dtype.itemsize,
                       bytes=data,
                       dimensions=data.shape)

    def add_str(self, name, desc, data, *dimensions):
        ''' Add a string parameter.
        '''
        self.add_param(name,
                       desc=desc,
                       bytes_per_element=-1,
                       bytes=data.encode('utf-8'),
                       dimensions=list(dimensions))

    def add_empty_array(self, name, desc, bpe):
        ''' Add an empty parameter block.
        '''
        self.add_param(name, desc=desc,
                       bytes_per_element=bpe, dimensions=[0])

    #
    #   Set decorator functions (overwrites)
    #
    def set(self, name, *args, **kwargs):
        ''' Add or overwrite a parameter with 'bytes' package formated in accordance with 'format'.
        '''
        try:
            self.remove_param(name)
        except KeyError as e:
            pass
        self.add(name, *args, **kwargs)

    def set_str(self, name, *args, **kwargs):
        ''' Add a string parameter.
        '''
        try:
            self.remove_param(name)
        except KeyError as e:
            pass
        self.add_str(name, *args, **kwargs)

    def set_array(self, name, *args, **kwargs):
        ''' Add a string parameter.
        '''
        try:
            self.remove_param(name)
        except KeyError as e:
            pass
        self.add_array(name, *args, **kwargs)

    def set_empty_array(self, name, *args, **kwargs):
        ''' Add an empty parameter block.
        '''
        try:
            self.remove_param(name)
        except KeyError as e:
            pass
        self.add_empty_array(name, *args, **kwargs)


class Writer(Manager):
    '''This class writes metadata and frames to a C3D file.

    For example, to read an existing C3D file, apply some sort of data
    processing to the frames, and write out another C3D file::

    >>> r = c3d.Reader(open('data.c3d', 'rb'))
    >>> w = c3d.Writer()
    >>> w.add_frames(process_frames_somehow(r.read_frames()))
    >>> with open('smoothed.c3d', 'wb') as handle:
    >>>     w.write(handle)

    Parameters
    ----------
    point_rate : float, optional
        The frame rate of the data. Defaults to 480.
    analog_rate : float, optional
        The number of analog samples per frame. Defaults to 0.
    point_scale : float, optional
        The scale factor for point data. Defaults to -1 (i.e., "check the
        POINT:SCALE parameter").
    point_units : str, optional
        The units that the point numbers represent. Defaults to ``'mm  '``.
    gen_scale : float, optional
        General scaling factor for analog data. Defaults to 1.
    '''

    def __init__(self,
                 point_rate=480.,
                 analog_rate=0.,
                 point_scale=-1.,
                 point_units='mm  ',
                 gen_scale=1.):
        '''Set metadata for this writer.

        '''
        self._dtypes = DataTypes(PROCESSOR_INTEL) # Always write INTEL format
        super(Writer, self).__init__()
        self._frames = []

        # Header properties
        self._header.frame_rate = np.float32(point_rate)
        self._header.scale_factor = np.float32(point_scale)
        self.analog_rate = analog_rate

        # Custom properties
        self._point_units = point_units
        self.set_analog_general_scale(gen_scale)

    @staticmethod
    def from_reader(reader, conversion=None):
        ''' Convert a `c3d.reader.Reader` to a persistent `c3d.writer.Writer` instance.

        Parameters
        ----------
        source : `c3d.reader.Reader`
            Source to copy data from.
        conversion : str
            Conversion mode, None is equivalent to the default mode. Supported modes are:
                'convert'       - (Default) Convert the Reader to a Writer
                                  instance, explicitly deleting the Reader.
                'copy'          - Reader objects will be deep copied.
                'copy_metadata' - Similar to 'copy' but only copies metadata and
                                  not point and analog frame data.
                'copy_shallow'  - Similar to 'copy' but group parameters are
                                  not copied.
                'copy_header'   - Similar to 'copy_shallow' but only the
                                  header is copied (frame data is not copied).

        Returns
        -------
        param : `c3d.writer.Writer`
            A writeable and persistent representation of the `c3d.reader.Reader` object.

        Raises
        ------
        ValueError
            If mode string is not equivalent to one of the supported modes.
            If attempting to convert non-Intel files using mode other than 'shallow_copy'.
        '''
        writer = Writer()
        # Modes
        is_header_only = conversion == 'copy_header'
        is_meta_copy = conversion == 'copy_metadata'
        is_meta_only = is_header_only or is_meta_copy
        is_consume = conversion == 'convert' or conversion is None
        is_shallow_copy = conversion == 'shallow_copy' or is_header_only
        is_deep_copy = conversion == 'copy' or is_meta_copy
        # Verify mode
        if not (is_consume or is_shallow_copy or is_deep_copy):
            raise ValueError(
                "Unknown mode argument {}. Supported modes are: 'consume', 'copy', or 'shallow_copy'".format(
                conversion))
        if not reader._dtypes.is_ieee and not is_shallow_copy:
            # Can't copy/consume non-Intel files due to the uncertainty of converting parameter data.
            raise ValueError(
                "File was read in {} format and only 'shallow_copy' mode is supported for non Intel files!".format(
                reader._dtypes.proc_type))

        if is_consume:
            writer._header = reader._header
            reader._header = None
            writer._groups = reader._groups
            reader._groups = None
            del reader
        elif is_deep_copy:
            writer._header = copy.deepcopy(reader._header)
            writer._groups = copy.deepcopy(reader._groups)
        elif is_shallow_copy:
            # Only copy header (no groups)
            writer._header = copy.deepcopy(reader._header)
            # Reformat header events
            writer._header.encode_events(writer._header.events)

            # Transfer a minimal set parameters
            writer.set_start_frame(reader.first_frame)
            writer.set_point_labels(reader.point_labels)
            writer.set_analog_labels(reader.analog_labels)

            gen_scale, analog_scales, analog_offsets = reader.get_analog_transform_parameters()
            writer.set_analog_general_scale(gen_scale)
            writer.set_analog_scales(analog_scales)
            writer.set_analog_offsets(analog_offsets)

        if not is_meta_only:
            # Copy frames
            for (i, point, analog) in reader.read_frames(copy=True, camera_sum=False):
                writer.add_frames((point, analog))
        return writer

    @property
    def analog_rate(self):
        return super(Writer, self).analog_rate

    @analog_rate.setter
    def analog_rate(self, value):
        if self.point_rate <= 0:
            raise ValueError(
                "Invalid point rate {}. ".format(self.point_rate)
                + "Ensure a valid value is set in either the header frame rate or point rate parameter before setting the analog rate.")
        per_frame_rate = value / self.point_rate
        if not float(per_frame_rate).is_integer():
            raise ValueError("Analog rate must be an integer multiple of the point rate.")
        self._header.analog_per_frame = np.uint16(per_frame_rate)

    @property
    def numeric_key_max(self):
        ''' Get the largest numeric key.
        '''
        num = 0
        if len(self._groups) > 0:
            for i in self._groups.keys():
                if isinstance(i, int):
                    num = max(i, num)
        return num

    @property
    def numeric_key_next(self):
        ''' Get a new unique numeric group key.
        '''
        return self.numeric_key_max + 1

    def get_create(self, label):
        ''' Get or create the specified parameter group.'''
        label = label.upper()
        group = self.get(label)
        if group is None:
            group = self.add_group(self.numeric_key_next, label, label + ' group')
        return group

    @property
    def point_group(self):
        ''' Get or create the POINT parameter group.'''
        return self.get_create('POINT')

    @property
    def analog_group(self):
        ''' Get or create the ANALOG parameter group.'''
        return self.get_create('ANALOG')

    @property
    def trial_group(self):
        ''' Get or create the TRIAL parameter group.'''
        return self.get_create('TRIAL')

    def get(self, group, default=None):
        '''Get a GroupEditable decorator for keyed group instance, or a parameter instance.

        Parameters
        ----------
        group : str
            Key, see Manager.get() for valid key formats.
        default : any
            Return this value if the named group and parameter are not found.

        Returns
        -------
        value : :class:`GroupEditable` or :class:`Param`
            Either a decorated group instance or parameter with the specified name(s). If neither
            is found, the default value is returned.
        '''
        val = super(Writer, self).get(group, default)
        if isinstance(val, Group):
            return GroupEditable(val)
        return val # Parameter

    def add_group(self, *args, **kwargs):
        '''Add a new parameter group. See Manager.add_group() for more information.

        Returns
        -------
        group : :class:`Group`
            An editable group instance.
        '''
        return GroupEditable(super(Writer, self).add_group(*args, **kwargs))

    def add_frames(self, frames, index=None):
        '''Add frames to this writer instance.

        Parameters
        ----------
        frames : Single or sequence of (point, analog) pairs
            A sequence or frame of frame data to add to the writer.
        index : int or None
            Insert the frame or sequence at the index (the first sequence frame will be inserted at give index).
            Note that the index should be relative to 0 rather then the frame number provided by read_frames()!
        '''
        sh = np.shape(frames)
        # Single frame
        if len(sh) != 2:
            frames = [frames]
            sh = np.shape(frames)
        # Sequence of invalid shape
        if sh[1] != 2:
            raise ValueError(
                'Expected frame input to be sequence of point and analog pairs on form (-1, 2). ' +
                '\Input was of shape {}.'.format(str(sh)))

        if index is not None:
            self._frames[index:index] = frames
        else:
            self._frames.extend(frames)

    @staticmethod
    def pack_labels(labels):
        labels = np.ravel(labels)
        # Get longest label name
        label_max_size = 0
        label_max_size = max(label_max_size, np.max([len(label) for label in labels]))
        label_str = ''.join(label.ljust(label_max_size) for label in labels)
        return label_str, label_max_size

    def set_point_labels(self, labels):
        ''' Set point data labels.
        '''
        label_str, label_max_size = Writer.pack_labels(labels)
        self.point_group.add_str('LABELS', 'Point labels.', label_str, label_max_size, len(labels))

    def set_analog_labels(self, labels):
        ''' Set analog data labels.
        '''
        label_str, label_max_size = Writer.pack_labels(labels)
        self.analog_group.add_str('LABELS', 'Analog labels.', label_str, label_max_size, len(labels))

    def set_analog_general_scale(self, value):
        ''' Set ANALOG:GEN_SCALE factor (uniform analog scale factor).
        '''
        self.analog_group.set('GEN_SCALE', 'Analog general scale factor', 4, '<f', value)

    def set_analog_scales(self, values):
        ''' Set ANALOG:SCALE factors (per channel scale factor).

        Parameters
        ----------
        values : iterable or None
            Iterable containing individual scale factors for encoding analog channel data.
        '''
        if is_iterable(values):
            data = np.array([v for v in values], dtype=np.float32)
            self.analog_group.set_array('SCALE', 'Analog channel scale factors', data)
        elif values is None:
            self.analog_group.set_empty_array('SCALE', 'Analog channel scale factors', 4)
        else:
            raise ValueError('Expected iterable containing analog scale factors.')

    def set_analog_offsets(self, values):
        ''' Set ANALOG:OFFSET offsets (per channel offset).

        Parameters
        ----------
        values : iterable or None
            Iterable containing individual offsets for encoding analog channel data.
        '''
        if is_iterable(values):
            data = np.array([v for v in values], dtype=np.int16)
            self.analog_group.set_array('OFFSET', 'Analog channel offsets', data)
        elif values is None:
            self.analog_group.set_empty_array('OFFSET', 'Analog channel offsets', 2)
        else:
            raise ValueError('Expected iterable containing analog data offsets.')

    def set_start_frame(self, frame=1):
        ''' Set the 'TRIAL:ACTUAL_START_FIELD' parameter and header.first_frame entry.

        Parameter
        ---------
        frame : int
            Number for the first frame recorded in the file.
            Frame counter for a trial recording always start at 1 for the first frame.
        '''
        self.trial_group.set('ACTUAL_START_FIELD', 'Actual start frame', 2, '<I', frame, 2)
        if frame < 65535:
            self._header.first_frame = np.uint16(frame)
        else:
            self._header.first_frame = np.uint16(65535)

    def _set_last_frame(self, frame):
        ''' Sets the 'TRIAL:ACTUAL_END_FIELD' parameter and header.last_frame entry.
        '''
        self.trial_group.set('ACTUAL_END_FIELD', 'Actual end frame', 2, '<I', frame, 2)
        self._header.last_frame = np.uint16(min(frame, 65535))


    def set_screen_axis(self, X='+X', Y='+Y'):
        ''' Set the X_SCREEN and Y_SCREEN parameters in the POINT group.

        Parameter
        ---------
        X : str
            2 character string with first character indicating positive or negative axis (+/-),
            and the second axis (X/Y/Z). Examples: '+X' or '-Y'
        Y : str
            Second axis string with same format as Y. Determines the second Y screen axis.
        '''
        if len(X) != 2:
            raise ValueError('Expected string literal to be a 2 character string for the X_SCREEN parameter.')
        if len(Y) != 2:
            raise ValueError('Expected string literal to be a 2 character string for the Y_SCREEN parameter.')
        group = self.point_group
        group.set_str('X_SCREEN', 'X_SCREEN parameter', X, 2)
        group.set_str('Y_SCREEN', 'Y_SCREEN parameter', Y, 2)

    def write(self, handle):
        '''Write metadata and point + analog frames to a file handle.

        Parameters
        ----------
        handle : file
            Write metadata and C3D motion frames to the given file handle. The
            writer does not close the handle.
        '''
        if not self._frames:
            raise RuntimeError('Attempted to write empty file.')

        points, analog = self._frames[0]
        ppf = len(points)
        apf = len(analog)


        first_frame = self.first_frame
        if first_frame <= 0: # Bad value
            first_frame = 1
        nframes = len(self._frames)
        last_frame = first_frame + nframes - 1

        UINT16_MAX = 65535

        # POINT group
        group = self.point_group
        group.set('USED', 'Number of point samples', 2, '<H', ppf)
        group.set('FRAMES', 'Total frame count', 2, '<H', min(UINT16_MAX, nframes))
        if nframes >= UINT16_MAX:
            # Should be floating point
            group.set('LONG_FRAMES', 'Total frame count', 4, '<f', np.float32(nframes))
        elif 'LONG_FRAMES' in group:
            # Docs states it should not exist if frame_count < 65535
            group.remove_param('LONG_FRAMES')
        group.set('DATA_START', 'First data block containing frame samples.', 2, '<H', 0)
        group.set('SCALE', 'Point data scaling factor', 4, '<f', np.float32(self.point_scale))
        group.set('RATE', 'Point data sample rate', 4, '<f', np.float32(self.point_rate))
        # Optional
        if 'UNITS' not in group:
            group.add_str('UNITS', 'Units used for point data measurements.',
                          self._point_units, len(self._point_units))
        if 'DESCRIPTIONS' not in group:
            group.add_str('DESCRIPTIONS', 'Channel descriptions.', ' ' * ppf, 1, ppf)

        # ANALOG group
        group = self.analog_group
        group.set('USED', 'Analog channel count', 2, '<H', apf)
        group.set('RATE', 'Analog samples per second', 4, '<f', np.float32(self.analog_rate))
        if 'GEN_SCALE' not in group:
            self.set_analog_general_scale(1.0)
        # Optional
        if 'SCALE' not in group:
            self.set_analog_scales(None)
        if 'OFFSET' not in group:
            self.set_analog_offsets(None)
        if 'DESCRIPTIONS' not in group:
            group.add_str('DESCRIPTIONS', 'Channel descriptions.', ' ' * apf, 1, apf)

        # TRIAL group
        self.set_start_frame(first_frame)
        self._set_last_frame(last_frame)

        # sync parameter information to header.
        blocks = self.parameter_blocks()
        self.get('POINT:DATA_START').bytes = struct.pack('<H', 2 + blocks)
        self._header.data_block = np.uint16(2 + blocks)
        self._header.point_count = np.uint16(ppf)
        self._header.analog_count = np.uint16(np.prod(analog.shape))

        self._write_metadata(handle)
        self._write_frames(handle)

    def _pad_block(self, handle):
        '''Pad the file with 0s to the end of the next block boundary.'''
        extra = handle.tell() % 512
        if extra:
            handle.write(b'\x00' * (512 - extra))

    def _write_metadata(self, handle):
        '''Write metadata to a file handle.

        Parameters
        ----------
        handle : file
            Write metadata and C3D motion frames to the given file handle. The
            writer does not close the handle.
        '''
        self._check_metadata()

        # Header
        self._header.write(handle)
        self._pad_block(handle)
        assert handle.tell() == 512

        # Groups
        handle.write(struct.pack(
            'BBBB', 0, 0, self.parameter_blocks(), PROCESSOR_INTEL))
        for group_id, group in self.group_listed():
            group.write(group_id, handle)

        # Padding
        self._pad_block(handle)
        while handle.tell() != 512 * (self.header.data_block - 1):
            handle.write(b'\x00' * 512)

    def _write_frames(self, handle):
        '''Write our frame data to the given file handle.

        Parameters
        ----------
        handle : file
            Write metadata and C3D motion frames to the given file handle. The
            writer does not close the handle.
        '''
        assert handle.tell() == 512 * (self._header.data_block - 1)
        scale_mag = abs(self.point_scale)
        is_float = self.point_scale < 0
        if is_float:
            point_dtype = self._dtypes.float32
            point_scale = 1.0
        else:
            point_dtype = self._dtypes.int16
            point_scale = scale_mag
        raw = np.zeros((self.point_used, 4), point_dtype)

        analog_scales, analog_offsets = self.get_analog_transform()
        analog_scales_inv = 1.0 / analog_scales

        for points, analog in self._frames:
            # Transform point data
            valid = points[:, 3] >= 0.0
            raw[~valid, 3] = -1
            raw[valid, :3] = points[valid, :3] / point_scale
            raw[valid, 3] = np.bitwise_or(np.rint(points[valid, 3] / scale_mag).astype(np.uint8),
                                          (points[valid, 4].astype(np.uint16) << 8),
                                          dtype=np.uint16)

            # Transform analog data
            analog = analog * analog_scales_inv + analog_offsets
            analog = analog.T

            # Write
            analog = analog.astype(point_dtype)
            handle.write(raw.tobytes())
            handle.write(analog.tobytes())
        self._pad_block(handle)
