"""Unsigned Android build inputs/results, shared with the trusted publisher."""
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
from urllib.parse import urlparse
from .common import sha

APP_ID = 'io.github.tomorikaho.livelife.dev'
MAX_APK = 64 * 1024**2


def validate_config(c, commit=None, base_url='https://192.144.253.40'):
    if not isinstance(c, dict) or c.get('schema_version') != 1 or not re.fullmatch('[a-f0-9]{32}', str(c.get('apk_id'))):
        raise ValueError('invalid Android configuration')
    sha(c['frontend_sha']); sha(c['backend_sha'])
    code = c['version_code']
    if isinstance(code, bool) or not isinstance(code, int) or not 1 <= code <= 2100000000:
        raise ValueError('invalid Android versionCode')
    if c['build_id'] != 'apk-' + c['apk_id'] or c['version_name'] != f'0.1.0-test.{code}':
        raise ValueError('invalid Android version identity')
    if commit and c['frontend_sha'] != sha(commit):
        raise ValueError('Android source SHA mismatch')
    if c['backend_mode'] not in ('staging', 'own', 'fixed'):
        raise ValueError('invalid Android backend mode')
    path = '/api/staging/' if c['backend_mode'] == 'staging' else f"/api/versions/be-{c['backend_sha']}/"
    if c['api_base_url'] != base_url + path or c['status_url'] != f"{base_url}/downloads/android/build-{c['apk_id']}/status.json":
        raise ValueError('invalid Android endpoint')
    if urlparse(base_url).scheme != 'https' or c.get('expires') is not None and not isinstance(c['expires'], (float, int)):
        raise ValueError('invalid Android expiry/origin')
    return c


def validate_apk(data, config):
    if not 0 < len(data) <= MAX_APK:
        raise ValueError('APK exceeds 64 MiB or is empty')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(i.file_size for i in entries) > 256 * 1024**2:
            raise ValueError('APK expanded size/entries exceeded')
        names = set()
        for i in entries:
            path = Path(i.filename)
            kind = (i.external_attr >> 16) & 0o170000
            if path.is_absolute() or '..' in path.parts or '\\' in i.filename or i.filename in names or kind not in (0, 0o100000, 0o040000):
                raise ValueError('unsafe APK entry')
            names.add(i.filename)
        name = 'assets/public/native-config.json'
        if archive.getinfo(name).file_size > 8192 or json.loads(archive.read(name)) != config:
            raise ValueError('embedded APK configuration mismatch')
        if not {'AndroidManifest.xml', 'classes.dex', 'assets/public/index.html'} <= names:
            raise ValueError('incomplete APK')


def prepare(workspace, config):
    validate_config(config)
    public = workspace / 'frontend/public'
    public.mkdir(exist_ok=True)
    (public / 'native-config.json').write_text(json.dumps(config) + '\n')


def package(path, destination, config):
    data = path.read_bytes()
    validate_apk(data, config)
    destination.mkdir(exist_ok=True)
    (destination / 'android-unsigned.apk').write_bytes(data)
    result = {'config': config, 'sha': config['frontend_sha'], 'apk_id': config['apk_id'],
              'digest': hashlib.sha256(data).hexdigest(), 'size': len(data)}
    (destination / 'manifest.json').write_text(json.dumps(result) + '\n')
    return result
