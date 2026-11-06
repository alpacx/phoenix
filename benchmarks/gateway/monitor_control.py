#!/usr/bin/env python3
"""Bench-only UART logger, commands from a local file; no network control port."""
import argparse,time,re
from pathlib import Path
import serial
p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--commands',required=True);p.add_argument('--seconds',type=int,default=3600);a=p.parse_args()
command=Path(a.commands);command.write_text('')
s=serial.Serial(port=None,baudrate=115200,timeout=.1);s.dtr=False;s.rts=False;s.port=a.port;s.open()
try:
 s.rts=True;time.sleep(.1);s.rts=False
 end=time.monotonic()+a.seconds;last=''
 while time.monotonic()<end:
  line=s.readline()
  if line:print(line.decode('utf8',errors='replace').rstrip(),flush=True)
  value=command.read_text().strip()
  if value and value!=last:
   _,cmd=value.split(' ',1)
   if cmd not in ('bench vpn','bench blocked','bench direct','bench probe') and not re.fullmatch(r'pair [0-9a-f]{64}',cmd):raise ValueError('unsupported bench command')
   s.write((cmd+'\n').encode());last=value
   print('HOST COMMAND '+('pair [redacted]' if cmd.startswith('pair ') else cmd),flush=True)
finally:s.close()
