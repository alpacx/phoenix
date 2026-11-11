"""Unprivileged, loopback-only HTTPS administration frontend."""
import argparse
from http.server import HTTPServer
import os
from pathlib import Path
import re
import signal
import ssl
from .rpc import RemoteAPI
from .server import handler


class TLSHTTPServer(HTTPServer):
    def get_request(self):
        stream, address = self.socket.accept()
        stream.settimeout(5)
        try:
            return self.context.wrap_socket(stream, server_side=True), address
        except BaseException:
            stream.close()
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', default='/run/phoenix-control/control.sock')
    parser.add_argument('--port', type=int, default=8443)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--tls-cert', required=True)
    parser.add_argument('--tls-key', required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('Frontend must run without root privileges')
    token = Path(args.token_file).read_text().strip()
    if not re.fullmatch('[0-9a-f]{64}', token):
        raise SystemExit('Invalid admin token')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.tls_cert, args.tls_key)
    server = TLSHTTPServer(('127.0.0.1', args.port), handler(RemoteAPI(args.socket), token))
    server.tls = True
    server.context = context
    def terminate(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
