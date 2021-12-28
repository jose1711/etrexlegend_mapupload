#!/usr/bin/env python
'''
etrex_upload.py

Upload Garmin map (gmapsupp.img) to Garmin eTrex Legend via serial
connection.

Note that eTrex Legend has only 8 MB available memory for custom
maps. Throw aways details that you don't need. Also note that maximum
upload speed is 10.9 kB/s hence it can take up to 12 minutes to
finish the upload.

==================== BIG BOLD WARNING ====================

By interacting with eTrex Legend (and maybe other Garmin devices
too) via serial connection in an unexpected way it is possible
to brick your device. This is based on a personal experience.
Although I did manage to unbrick it you may not be that lucky
hence:
  - use at your own risk and do not complain if your Garmin
    can no longer boot
  - backup your data first
  - be prepared for a hw upgrade

==================== BIG BOLD WARNING ====================

Heavily based on code from:
  - qlandkartegt/garmindev (https://sourceforge.net/projects/qlandkartegt/)
  - pygarmin (https://github.com/quentinsf/pygarmin)

'''
import argparse
import logging
import os
import os.path
import serial
import struct
import sys
import termios
import time
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)


DLE = b'\x10'
ETX = b'\x03'
EOM = b'\x10\x03'

Pid_Product_Rqst = 254  # 0xfe
Pid_Command_Data = 10   # 0xa
Cmnd_Transfer_Mem = 63  # 0x3f
Pid_Capacity_Data = 95  # 0x5f
Pid_Ack_Byte = 6        # 0x06

def readEscapedByte():
    c = ser.read(1)
    if c == DLE:
        c = ser.read(1)
    return c


def sendAcknowledge(ptype):
    logging.debug("Sending ACK")
    sendPacket(Pid_Ack_Byte, struct.pack("<h", ptype), 0)


def set_bitrate():
    logging.debug('Sending test packet..')
    sendPacket(10, b'\x0e\x00')
    if readPacket()[0] != 38:
        print('No response to test packet!')
        sys.exit(1)

    print('Switching speed to 115200..')
    sendPacket(48, struct.pack('i', 115200), 1)

    response_packet, device_speed = readPacket()
    if response_packet != 49:
        print('Did not manage to switch speed!')
        sys.exit(1)
    device_speed = struct.unpack('i', device_speed)[0]
    print(f'Device wants speed of {device_speed}')
   
    time.sleep(0.1)
    
    # set a new speed on port
    logging.debug('Changing speed to 115200')
    ser.baudrate = 115200
    tty = termios.tcgetattr(ser.fileno())
    tty[4] = termios.B115200
    tty[5] = termios.B115200
    termios.tcsetattr(ser.fileno(), termios.TCSADRAIN, tty)

    for i in range(1, 4):
        logging.debug(f'Sending ping packet {i}..')
        sendPacket(10, b'\x3a\x00', 1)


def readPacket(sendAck=1):
    ret = b''
    dle = ser.read(1)
    # find start of a message
    while dle != DLE:
        logging.debug(f'resync - expected DLE and got something else: {repr(dle)}')
        dle = ser.read(1)

    tp = ser.read(1)
    if tp == ETX:
        # EOM
        dle = ser.read(1)
        tp = ser.read(1)

    # we should be synchronised now
    ptype = ord(tp)
    ld = readEscapedByte()
    datalen = ord(ld)
    data = b''
    for i in range(0, datalen):
        data = data + readEscapedByte()
    ck = readEscapedByte()
    if ck != checksum(tp + ld + data):
        raise LinkException("Invalid checksum")
    eom = ser.read(2)
    assert eom == EOM, 'Invalid EOM seen'
    if sendAck:
        sendAcknowledge(ptype)
    logging.debug('returning (ptype: %s, data: %s):' % (repr(ptype), ', '.join(['0x%02x' % x for x in data])))
    return (ptype, data)


def readAcknowledge(ptype):
    "Read an ack msg in response to a particular sent msg"
    tp, data = readPacket(0)
    if (tp & 0xff) != Pid_Ack_Byte or data[0] != ptype:
        raise Exception('Acknowledge error')


def sendPacket(ptype, data, readAck=1):
    tp = struct.pack('B', ptype)
    ld = struct.pack('B', len(data))
    logging.debug('data to checksum: (%s + %s + %s = %s' % (repr(tp), repr(ld), repr(data), repr(tp+ld+data)))
    chk = checksum(tp + ld + data)
    logging.debug(f'data to write: DLE {DLE} + tp/packet_type {tp} + ld/size {ld} + data {data} + chk {chk} + EOM {EOM}')
    data = DLE + tp + ld + data + chk + EOM
    ser.write(data)
    if readAck:
        readAcknowledge(ptype)


def sendMapChunk(ptype, offset, data):
    tp = struct.pack('B', ptype)
    if len(data) < 250:
        ld = struct.pack('B', len(data) + 4)
    else:
        ld = struct.pack('B', 0xfa + 4)
    offset = struct.pack('I', offset)
    escaped_offset = offset.replace(DLE, DLE+DLE)
    escaped_data = data.replace(DLE, DLE + DLE)
    logging.debug('data to checksum: (%s + %s + %s + %s = %s' % (repr(tp), repr(ld), repr(offset), repr(data), repr(tp+ld+offset+data)))
    chk = checksum(tp + ld + offset + data)
    chk = chk.replace(DLE, DLE+DLE)
    data = escaped_data
    offset = escaped_offset
    logging.debug(f'data to be written: DLE {DLE} + tp/packet_type {tp} + ld/size {ld} + data {data} + chk {chk} + EOM {EOM}')
    data = DLE + tp + ld + offset + data + chk + EOM
    ser.write(data)
    readAcknowledge(ptype)


def checksum(data):
    sum = 0
    for i in data:
        sum = sum + i
    sum = sum % 256
    ret = struct.pack('B', ((256-sum) % 256))
    logging.debug('returning from checksum: %s' % repr(ret))
    return ret


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', dest='debug', action='store_true', default=False, help='Debug messages')
    parser.add_argument('-p', dest='port', nargs=1, metavar='PORT', default='/dev/ttyUSB0', help='Port name to use (/dev/ttyUSB0 by default)')
    parser.add_argument('-s', dest='slow', action='store_true', default=False, help='Slow (9600 bd) upload')
    parser.add_argument('map_file', nargs='?', default='gmapsupp.img', help='Garmin mapfile to upload (gmapsupp.img by default)')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    port = args.port
    map_file = args.map_file

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    progress = Progress(
        TextColumn("[bold blue]", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
    )

    if not os.path.isfile(map_file):
        print(f'File {map_file} does not exist!')
        sys.exit(1)

    ser = serial.Serial(port, baudrate=9600)

    # product request (must return eTrex Legend..)
    logging.debug('Sending product request..')
    sendPacket(Pid_Product_Rqst, b'\x00\x00', 1)
    if b'eTrex Legend' not in readPacket()[1]:
        print('eTrex Legend not detected! Is it on?')
        sys.exit(1)
    print(f'eTrex Legend found on {port}')
    logging.debug(readPacket())

    logging.debug('Get size of memory')
    sendPacket(0x1c, b'\x00\x00', 0)
    # \x3f = Transfer_Mem
    sendPacket(Pid_Command_Data, b'\x3f\x00', 0)
     
    readPacket()
    readPacket()
    memory_size = struct.unpack('I', readPacket()[1][4:8])[0]/1024/1024
    if memory_size <= 0:
        print('Capacity could not be determined! Try restarting the device.')
        sys.exit()
    print(f'Device memory: {memory_size} mb')

    if not args.slow:
        set_bitrate()

    ser.timeout = 5
    ser.read()

    # erase map data? (75)
    sendPacket(0x4b, b'\x0a\x00', 0)
    while True:
        response_ptype, response_data = readPacket()
        if response_ptype == 74:
            break

    ser.timeout = 1
    ser.read()

    logging.debug('Sending map data')
    offset = 0
    map_size = os.stat(map_file).st_size
    chunk_size = 0xfa
    with open(map_file, 'rb') as mf:
        with progress:
            if not args.debug:
                task_id = progress.add_task("map_upload", start=False)
                progress.update(task_id, total=map_size)
                progress.start_task(task_id)

            while True:
                map_chunk = mf.read(chunk_size)
                if not map_chunk:
                    break
                sendMapChunk(0x24, offset, map_chunk)
                offset += chunk_size
                if args.debug: 
                    print(f'Uploaded: {int(offset/map_size*100)} %')
                else:
                    progress.update(task_id, advance=0xfa)

    print('Terminate map transfer (device will reboot)..')
    sendPacket(0x2d, b'\x0a\x00', 0)
    time.sleep(2)
    print('Finished.')
    ser.close()
