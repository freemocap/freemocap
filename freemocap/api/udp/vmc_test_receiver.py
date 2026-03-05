#!/usr/bin/env python3
"""
VMC test receiver: prints incoming bone transforms to the terminal.

Run this alongside freemocap with VMC enabled to verify data is flowing.
No dependencies beyond Python stdlib.

Usage:
    python vmc_test_receiver.py              # listen on default port 39539
    python vmc_test_receiver.py 39540        # listen on custom port
"""

import socket
import struct
import sys


def _read_osc_string(data: bytes, offset: int) -> tuple[str, int]:
    """Read a null-terminated, 4-byte-aligned OSC string."""
    end = data.index(b'\x00', offset)
    s = data[offset:end].decode('utf-8')
    # Advance past null + padding to 4-byte boundary
    padded_end = end + 1
    padded_end += (4 - padded_end % 4) % 4
    return s, padded_end


def _read_osc_float(data: bytes, offset: int) -> tuple[float, int]:
    """Read a big-endian float32."""
    value = struct.unpack_from('>f', data, offset)[0]
    return value, offset + 4


def parse_osc_message(data: bytes, offset: int = 0) -> dict | None:
    """Parse a single OSC message. Returns dict with address + args, or None."""
    if offset >= len(data):
        return None

    address, offset = _read_osc_string(data, offset)
    if offset >= len(data):
        return {'address': address, 'args': []}

    type_tag, offset = _read_osc_string(data, offset)
    if not type_tag.startswith(','):
        return {'address': address, 'args': []}

    args: list[str | float | int] = []
    for tag in type_tag[1:]:  # skip the leading comma
        if tag == 'f':
            val, offset = _read_osc_float(data, offset)
            args.append(val)
        elif tag == 's':
            val, offset = _read_osc_string(data, offset)
            args.append(val)
        elif tag == 'i':
            val = struct.unpack_from('>i', data, offset)[0]
            offset += 4
            args.append(val)
        else:
            break  # unknown type, stop parsing

    return {'address': address, 'args': args}


def parse_bundle(data: bytes) -> list[dict]:
    """Parse an OSC bundle into a list of messages."""
    messages: list[dict] = []

    # Check for #bundle header
    if data[:8] != b'#bundle\x00':
        msg = parse_osc_message(data)
        if msg:
            messages.append(msg)
        return messages

    offset = 8  # skip "#bundle\0"
    offset += 8  # skip timetag

    while offset < len(data):
        if offset + 4 > len(data):
            break
        size = struct.unpack_from('>I', data, offset)[0]
        offset += 4
        if offset + size > len(data):
            break
        msg = parse_osc_message(data, offset)
        if msg:
            messages.append(msg)
        offset += size

    return messages


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 39539

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', port))
    sock.settimeout(1.0)

    print(f"VMC test receiver listening on UDP port {port}")
    print(f"Waiting for /VMC/Ext/Bone/Pos messages...\n")

    frame_count = 0
    try:
        while True:
            try:
                data, addr = sock.recvfrom(65536)
            except socket.timeout:
                continue

            messages = parse_bundle(data)
            bone_messages = [m for m in messages if m['address'] == '/VMC/Ext/Bone/Pos']

            if bone_messages:
                frame_count += 1
                print(f"--- Frame {frame_count} ({len(bone_messages)} bones from {addr[0]}:{addr[1]}) ---")
                for msg in bone_messages:
                    args = msg['args']
                    if len(args) >= 8:
                        name = args[0]
                        px, py, pz = args[1], args[2], args[3]
                        qx, qy, qz, qw = args[4], args[5], args[6], args[7]
                        print(f"  {name:20s}  pos=({px:+7.3f}, {py:+7.3f}, {pz:+7.3f})  "
                              f"quat=({qw:+6.3f}, {qx:+6.3f}, {qy:+6.3f}, {qz:+6.3f})")
                print()

    except KeyboardInterrupt:
        print(f"\nReceived {frame_count} frames total. Goodbye!")
    finally:
        sock.close()


if __name__ == '__main__':
    main()
