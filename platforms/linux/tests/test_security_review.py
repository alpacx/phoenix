import socket
import struct
import unittest
from unittest.mock import patch
from phoenix_linux.rpc import receive
from phoenix_linux.jsonutil import loads


class SecurityReviewTests(unittest.TestCase):
    def test_strict_json_at_both_protocol_boundaries(self):
        for value in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                loads(value)
            left,right=socket.socketpair()
            try:
                left.sendall(struct.pack('!I',len(value))+value)
                with self.assertRaises(ValueError):
                    receive(right)
            finally:
                left.close();right.close()

    def test_rpc_total_deadline_not_reset_by_partial_reads(self):
        left,right=socket.socketpair()
        try:
            left.sendall(struct.pack('!I',2)+b'{}')
            with patch('phoenix_linux.rpc.time.monotonic',side_effect=[0,1,21]):
                with self.assertRaisesRegex(ValueError,'rpc_read_deadline'):
                    receive(right)
        finally:
            left.close();right.close()
