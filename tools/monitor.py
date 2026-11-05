#!/usr/bin/env python3
"""Bounded serial log capture for the dedicated development UART, optional reset."""
import argparse
import time
import serial
p=argparse.ArgumentParser()
p.add_argument('--port',required=True)
p.add_argument('--seconds',type=int,default=40)
p.add_argument('--reset',action='store_true')
a=p.parse_args()
s=serial.Serial(port=None,baudrate=115200,timeout=.2)
s.dtr=False;s.rts=False;s.port=a.port;s.open()
try:
    if a.reset:
        s.rts=True;time.sleep(.1);s.rts=False
    end=time.monotonic()+a.seconds
    while time.monotonic()<end:
        line=s.readline()
        if line: print(line.decode('utf-8',errors='replace').rstrip(),flush=True)
finally:
    s.close()
