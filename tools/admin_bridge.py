#!/usr/bin/env python3
"""Phoenix local admin bridge over USB UART. No IP routing or OS VPN changes.
The board performs the authentication and handles the same REST endpoints.
"""
import argparse,json,mimetypes,queue,secrets,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
import serial

class Bridge:
 def __init__(self,port,token_file,log):
  self.token=Path(token_file).read_text().strip()
  if len(self.token)!=64 or any(c not in '0123456789abcdef' for c in self.token):raise ValueError('Invalid admin token file')
  self.serial=serial.Serial(port=None,baudrate=115200,timeout=.2,write_timeout=10)
  self.serial.dtr=True;self.serial.rts=True;self.serial.port=port;self.serial.open()
  self.lock=threading.Lock();self.replies=queue.Queue();self.next_id=secrets.randbelow(1000000000)
  self.log=open(log,'a',buffering=1)
  threading.Thread(target=self.read,daemon=True).start()
 def read(self):
  while True:
   try:line=self.serial.readline().decode('utf8',errors='replace').strip()
   except serial.SerialException:self.log.write('Serial connection lost\n');return
   if not line:continue
   if line.startswith('PHADMIN '):
    try:self.replies.put(json.loads(line[8:]))
    except json.JSONDecodeError:self.log.write('Incomplete admin response\n')
   else:self.log.write(line+'\n')
 def request(self,method,path,body=None,authorization=None):
  with self.lock:
   self.next_id=(self.next_id+1)%2147483647
   credential=self.token if authorization is None else authorization.removeprefix('Bearer ')
   message=dict(id=self.next_id,method=method,path=path,token=credential)
   if body is not None:message['body']=body
   payload=('\nadmin '+json.dumps(message,separators=(',',':'),ensure_ascii=True)+'\n').encode()
   if len(payload)>16384:return 413,{'error':'request_too_large'}
   self.serial.write(payload);self.serial.flush()
   deadline=time.monotonic()+12
   while time.monotonic()<deadline:
    try:reply=self.replies.get(timeout=max(.01,deadline-time.monotonic()))
    except queue.Empty:break
    if reply.get('id')==self.next_id:return int(reply['status']),reply['body']
   return 504,{'error':'serial_gateway_timeout'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--listen',type=int,default=8085);p.add_argument('--token-file',default='results/gatewaybench/admin-token.txt');p.add_argument('--log',default='results/gatewaybench/uart-admin-bridge.log');a=p.parse_args()
 root=Path(__file__).resolve().parent.parent/'main'/'web';bridge=Bridge(a.port,a.token_file,a.log);host=f'127.0.0.1:{a.listen}'
 class Handler(BaseHTTPRequestHandler):
  protocol_version='HTTP/1.1'
  def log_message(self,*args):pass
  def send_data(self,status,body,mime='application/json'):
   if not isinstance(body,bytes):body=json.dumps(body,separators=(',',':')).encode()
   self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");self.end_headers()
   try:self.wfile.write(body)
   except (BrokenPipeError,ConnectionResetError):pass
  def handle_request(self):
   if self.headers.get('Host')!=host or self.headers.get('Origin') not in (None,'http://'+host) or self.headers.get('Sec-Fetch-Site')=='cross-site':self.close_connection=True;self.send_data(403,{'error':'origin'});return
   parsed=urlsplit(self.path);path=parsed.path
   if self.command=='GET' and path in ('/','/app.js','/app.css','/countries.json'):
    file=root/('index.html' if path=='/' else path[1:]);self.send_data(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream');return
   if not path.startswith('/api/v1/') or self.command not in ('GET','POST'):self.send_data(404,{'error':'not_found'});return
   try:
    size=int(self.headers.get('Content-Length','0'))
    if size<0 or size>12000:self.send_data(413,{'error':'size'});return
    body=json.loads(self.rfile.read(size)) if size else None
    status,data=bridge.request(self.command,path[len('/api/v1/'):]+('?' + parsed.query if parsed.query else ''),body,self.headers.get('Authorization'))
    self.send_data(status,data)
   except (ValueError,serial.SerialException):self.send_data(400,{'error':'invalid_request_or_serial_unavailable'})
  do_GET=handle_request
  do_POST=handle_request
 class Server(ThreadingHTTPServer):
  daemon_threads=True
  def get_request(self):
   sock,addr=super().get_request();sock.settimeout(20);return sock,addr
 print(f'Phoenix admin over USB serial: http://{host}',flush=True)
 Server(('127.0.0.1',a.listen),Handler).serve_forever()
if __name__=='__main__':main()
