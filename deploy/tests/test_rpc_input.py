"""Real open-pipe regression for complete requests without an EOF handshake."""
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife.common import read_request


class Chunked(io.BytesIO):
    def read1(self, size):
        return super().read1(min(size, 3))


class RPCInputTests(unittest.TestCase):
    def test_complete_object_returns_while_writer_keeps_pipe_open(self):
        source = str(Path(__file__).resolve().parents[1])
        code = ('import sys,json; sys.path.insert(0, ' + repr(source) + '); '
                'from livelife.common import read_request; '
                'print(json.dumps(read_request(sys.stdin.buffer, 1024)), flush=True)')
        process = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            process.stdin.write(b'{"op":"snapshot"}')
            process.stdin.flush()
            # Deliberately keep stdin open. Old read(limit) waits for EOF here.
            process.wait(timeout=3)
            self.assertEqual(process.returncode, 0, process.stderr.read().decode())
            self.assertEqual(json.loads(process.stdout.read()), {'op': 'snapshot'})
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            for stream in [process.stdin, process.stdout, process.stderr]:
                stream.close()

    def test_nested_unicode_and_escaped_strings_across_chunks(self):
        request = {'op': 'snapshot', 'data': [{'text': '北大 } [ " \\'}, [], {'empty': {}}]}
        data = (' \n' + json.dumps(request, ensure_ascii=False) + '\n').encode()
        self.assertEqual(read_request(Chunked(data), 1024), request)

    def test_complete_legacy_and_newline_requests(self):
        for suffix in [b'', b'\n', b'\r\n']:
            self.assertEqual(read_request(io.BytesIO(b'{"op":"recover"}' + suffix), 1024), {'op': 'recover'})

    def test_oversize_and_invalid_inputs_rejected(self):
        for data in [b'', b'[]', b'null', b'{"op":', b'{"a": ]}', b'{}{}', b'{}script',
                     b'{"a":"' + b'x' * 128 + b'"}']:
            with self.subTest(data=data[:25]), self.assertRaises(ValueError):
                read_request(io.BytesIO(data), 64)

    def test_payload_limit_applies_across_reads(self):
        data = b'{"padding":"' + b'x' * 100 + b'"}'
        self.assertEqual(read_request(Chunked(data), len(data)), {'padding': 'x' * 100})
        with self.assertRaisesRegex(ValueError, 'exceeds limit'):
            read_request(Chunked(data), len(data) - 1)
