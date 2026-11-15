"""USB-only socket activation and HTTP-to-HTTPS redirect; no wildcard binding."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import socket


def activated_server(server_class, handler_class, port):
    if (os.environ.get('LISTEN_PID') != str(os.getpid())
            or os.environ.get('LISTEN_FDS') != '1'):
        raise ValueError('one_systemd_socket_required')
    listener = socket.socket(fileno=3)
    try:
        device = listener.getsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, 64).rstrip(b'\0')
        if (listener.family != socket.AF_INET
                or listener.getsockname() != ('192.168.7.1', port)
                or device != b'phusb0'
                or not listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN)):
            raise ValueError('usb_admin_socket_not_isolated')
        server = server_class(('192.168.7.1', port), handler_class, bind_and_activate=False)
        server.socket.close()
        server.socket = listener
        server.server_address = listener.getsockname()
        server.server_name = '192.168.7.1'
        server.server_port = port
        return server
    except BaseException:
        listener.close()
        raise


class Redirect(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *_):
        pass

    def do_GET(self):
        self.send_response(308)
        # Never reflect Host, path or query; do not handle credentials over HTTP.
        self.send_header('Location', 'https://192.168.7.1/')
        self.send_header('Content-Length', '0')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    do_HEAD = do_GET

    def do_POST(self):
        self.send_response(405)
        self.send_header('Allow', 'GET, HEAD')
        self.send_header('Content-Length', '0')
        self.end_headers()


if __name__ == '__main__':
    with activated_server(HTTPServer, Redirect, 80) as server:
        server.serve_forever()
