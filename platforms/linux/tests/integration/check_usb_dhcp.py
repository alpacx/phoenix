"""Real DHCP exchange over isolated veth; no USB hardware/configfs emulation claim."""
import ipaddress
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time
from phoenix_linux.usb_lan import UsbLan
from phoenix_linux.runtime import Runner
import shutil

if not Path('/.dockerenv').exists() or os.geteuid() != 0:
    raise SystemExit('Run only in the dedicated Docker test container')

def command(*args):subprocess.run(args, check=True, capture_output=True)
command('ip','link','add','phusb0','type','veth','peer','name','phclient')
command('ip','link','set','phclient','address','02:50:48:00:00:02')
command('ip','link','set','phclient','up')
mac = bytes.fromhex('025048000002')
xid = 0x50480001
sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800))
sock.bind(('phclient', 0));sock.settimeout(.5)

def send(kind, address=None):
    options = bytes([53,1,kind,61,7,1]) + mac + bytes([55,3,1,3,6])
    if address:options += bytes([50,4]) + address + bytes([54,4]) + socket.inet_aton('192.168.7.1')
    payload = struct.pack('!BBBBIHHIIII16s64s128s',1,1,6,0,xid,0,0x8000,0,0,0,0,mac+b'\0'*10,b'',b'') + bytes.fromhex('63825363') + options + b'\xff'
    udp = struct.pack('!HHHH',68,67,8+len(payload),0) + payload
    header = struct.pack('!BBHHHBBH4s4s',0x45,0,20+len(udp),1,0,64,17,0,b'\0'*4,b'\xff'*4)
    total = sum(struct.unpack('!10H',header))
    while total >> 16:total = (total & 65535)+(total >> 16)
    header = header[:10]+struct.pack('!H',(~total)&65535)+header[12:]
    sock.send(b'\xff'*6 + mac + b'\x08\x00' + header + udp)

def receive(kind):
    deadline = time.monotonic()+5
    while time.monotonic()<deadline:
        try:frame=sock.recv(4096)
        except socket.timeout:continue
        if len(frame)<282 or frame[12:14]!=b'\x08\x00':continue
        offset=14+(frame[14]&15)*4
        if struct.unpack('!HH',frame[offset:offset+4])!=(67,68):continue
        data=frame[offset+8:]
        if data[0]!=2 or struct.unpack('!I',data[4:8])[0]!=xid:continue
        options={};i=240
        while i<len(data) and data[i]!=255:
            key=data[i];i+=1
            if key==0:continue
            n=data[i];i+=1;options[key]=data[i:i+n];i+=n
        if options.get(53)==bytes([kind]):return data[16:20],options
    raise AssertionError('DHCP response timeout')

with tempfile.TemporaryDirectory() as tmp:
    usb=UsbLan('phusb0','1.1.1.1',tmp,Runner(),binding=lambda _:True,
               which=lambda name:None if name=='nmcli' else shutil.which(name))
    try:
        usb.start();send(1);address,offer=receive(2)
        assert ipaddress.IPv4Address(address) in ipaddress.ip_network('192.168.7.0/24')
        send(3,address);assigned,ack=receive(5)
        assert assigned==address and ack[3]==socket.inet_aton('192.168.7.1')
        assert ack[6]==socket.inet_aton('1.1.1.1')
        usb.set_dns('9.9.9.9');xid+=1;send(3,address);_,ack=receive(5)
        assert ack[6]==socket.inet_aton('9.9.9.9')
        assert usb.healthy()
    finally:usb.stop();sock.close()
    addresses=subprocess.run(['ip','-j','address','show','dev','phusb0'],check=True,capture_output=True,text=True).stdout
    assert '192.168.7.1' not in addresses
print('PASS: real DHCP DISCOVER/OFFER/REQUEST/ACK, USB subnet/router/DNS, DNS change and address cleanup over veth. USB enumeration is NOT tested.')
