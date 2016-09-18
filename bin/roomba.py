import httplib
import json
import serial
import sys
import time
import traceback


# Constants
ENDPOINT = 'xxx.appspot.com'
PHONE_NUMBER = '+815xxxx'
SERIAL_DEV = None

# Roomba CODE
CONNECTION = [128, 130]
CLEAN = [135]
POWER = [133]
BUTTON = [165, 0]
SONG = [140, 1, 15, 76, 32, 76, 32, 77, 32, 79, 32, 79, 32, 77, 32, 76, 32, 74, 32, 72, 32, 72, 32, 74, 32, 76, 32, 76, 48, 74, 16, 74, 64]
SING = [141, 1]


# Implementation
def get_order():
    conn = httplib.HTTPConnection(ENDPOINT)
    conn.request('GET', '/orders/{}'.format(PHONE_NUMBER))
    j = json.load(conn.getresponse())
    conn.close()
    return j


def connect():
    return serial.Serial(SERIAL_DEV, 115200)


def send(s, code):
    for i in CONNECTION + code:
        s.write(chr(i))


# Main
last_order_id = None
if len(sys.argv) < 2:
    sys.stderr.write('COMMAND SERIAL_DEVICE\n')
    sys.exit()

SERIAL_DEV = sys.argv[1]
s = connect()
interval = 3

while(1):
    order = get_order()
    id_ = order.get('id', None)
    if id_ is None:
        time.sleep(interval)
        continue

    command = order['order']

    if last_order_id == id_:
        time.sleep(interval)
        continue

    try:
        if command == 'START':
            send(s, CLEAN)
        elif command == 'STOP':
            send(s, BUTTON)
        elif command == 'SING':
            send(s, SONG)
            time.sleep(1)
            send(s, SING)
    except Exception:
        s = connect()
        sys.stderr.write(traceback.format_exc())
    else:
        last_order_id = id_

    time.sleep(interval)
