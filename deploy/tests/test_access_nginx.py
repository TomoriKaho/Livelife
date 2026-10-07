"""Exercise the real gateway in isolation when Nginx/OpenSSL are available."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife.runtime import Runtime

NGINX = shutil.which('nginx')
OPENSSL = shutil.which('openssl')
SOURCE = Path(__file__).resolve().parents[1]


class Echo(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(dict(self.headers)).encode()
        self.send_response(401 if self.path == '/private' else 200)
        if self.path == '/private':
            self.send_header('WWW-Authenticate', 'Bearer')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@unittest.skipUnless(NGINX and OPENSSL and Path('/etc/nginx/mime.types').exists(), 'requires Linux Nginx/OpenSSL')
class NginxAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='livelife-access-', dir='/tmp')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        for name in ['gateway/run/client_body', 'gateway/run/proxy', 'gateway/logs', 'gateway/config',
                     'gateway/data', 'tls', 'web/builds', 'web/shared']:
            (cls.root / name).mkdir(parents=True, exist_ok=True)
        cls.key = 'a' * 64
        (cls.root / 'web/shared/asset.txt').write_text('static fixture')
        cls.upstream = ThreadingHTTPServer(('127.0.0.1', 0), Echo)
        cls.addClassCleanup(cls.upstream.server_close)
        threading.Thread(target=cls.upstream.serve_forever, daemon=True).start()
        cls.addClassCleanup(cls.upstream.shutdown)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        config = (SOURCE / 'nginx.conf').read_text().replace('/opt/livelife', str(cls.root))
        (cls.root / 'gateway/nginx.conf').write_text(config)
        runtime = Runtime({'root': str(cls.root), 'base_url': 'https://localhost'})
        with patch('livelife.runtime.subprocess.run'):
            runtime.publish({'/api/staging/': {'id': 'be-' + 'a' * 40, 'sha': 'a' * 40,
                                             'port': cls.upstream.server_port - 10000}})
        config = config.replace('listen 443 ssl;', f'listen 127.0.0.1:{cls.port} ssl;')
        (cls.root / 'gateway/nginx.conf').write_text(config)
        subprocess.run([OPENSSL, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=localhost', '-keyout', str(cls.root / 'tls/key.pem'),
                        '-out', str(cls.root / 'tls/fullchain.pem')], check=True, capture_output=True)
        command = [NGINX, '-p', str(cls.root / 'gateway') + '/', '-c', str(cls.root / 'gateway/nginx.conf')]
        check = subprocess.run(command + ['-t'], text=True, capture_output=True)
        if check.returncode:
            raise RuntimeError(check.stderr)
        cls.process = subprocess.Popen(command + ['-g', 'daemon off; master_process off;'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.addClassCleanup(cls.stop_nginx)
        deadline = time.monotonic() + 5
        while True:
            try:
                with socket.create_connection(('127.0.0.1', cls.port), timeout=1):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('isolated gateway did not start')
                time.sleep(0.05)

    @classmethod
    def stop_nginx(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)

    def request(self, path='/api/staging/test/hello', headers=None, method='GET'):
        connection = http.client.HTTPSConnection('127.0.0.1', self.port, timeout=5,
                                                 context=ssl._create_unverified_context())
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_public_resources_need_no_preview_credentials(self):
        for path in ['/api/staging/test/hello', '/__livelife/versions.json', '/__livelife/web-assets/asset.txt']:
            status, headers, _ = self.request(path)
            self.assertEqual(status, 200)
            self.assertNotIn('WWW-Authenticate', headers)
            self.assertNotIn('Set-Cookie', headers)
        status, headers, body = self.request('/__livelife/access', method='POST')
        self.assertEqual(status, 404)
        self.assertNotIn('Set-Cookie', headers)
        self.assertEqual(self.request('/__livelife/access-form.html')[0], 404)

    def test_business_unauthorized_response_is_not_replaced(self):
        status, headers, body = self.request('/api/staging/private')
        self.assertEqual(status, 401)
        self.assertEqual(headers['WWW-Authenticate'], 'Bearer')
        self.assertIsInstance(json.loads(body), dict)
        self.assertNotIn('Set-Cookie', headers)

    def test_infrastructure_secret_removed_and_application_auth_preserved(self):
        for cookie in [f'livelife_preview={self.key}', f'livelife_preview={self.key}; app=one; theme=dark',
                       f'app=one; livelife_preview={self.key}; theme=dark', f'app=one; theme=dark; livelife_preview={self.key}',
                       f'app=one; LiveLife_Preview={self.key}; theme=dark']:
            status, _, body = self.request(headers={'Cookie': cookie, 'X-Livelife-Preview-Key': self.key,
                                                    'Authorization': 'Bearer application-fixture'})
            self.assertEqual(status, 200)
            headers = json.loads(body)
            self.assertEqual(headers['Authorization'], 'Bearer application-fixture')
            self.assertNotIn('X-Livelife-Preview-Key', headers)
            self.assertNotIn(self.key, body.decode())
            if 'app=' in cookie:
                self.assertEqual(headers['Cookie'], 'app=one; theme=dark')
            else:
                self.assertNotIn('Cookie', headers)
        status, _, body = self.request(headers={'Cookie': f'livelife_preview={self.key}; app=one; livelife_preview={self.key}',
                                               'Authorization': 'Bearer application-fixture'})
        self.assertEqual(status, 200)
        self.assertNotIn(self.key, body.decode())
        self.assertNotIn('Cookie', json.loads(body))
        self.assertEqual(json.loads(body)['Authorization'], 'Bearer application-fixture')
        status, _, body = self.request(headers={'Cookie': 'session=business', 'Authorization': 'Bearer application-fixture'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['Cookie'], 'session=business')
