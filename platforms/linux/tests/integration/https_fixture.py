"""Local TLS fixture for selected-uplink integration; never a NordVPN emulator."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import ssl

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_GET(self):
        if self.path.startswith('/dns-query?'):
            value = {'Status':0,'Answer':[{'type':1,'data':'192.0.2.20'}]}
        elif self.path == '/v1/fixture':
            value = {'local_fixture':True}
        else:
            self.send_error(404)
            return
        data=json.dumps(value).encode()
        self.send_response(200)
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)

server=HTTPServer(('0.0.0.0',443),Handler)
context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('/tmp/fixture-cert.pem','/tmp/fixture-key.pem')
server.socket=context.wrap_socket(server.socket,server_side=True)
server.serve_forever()
