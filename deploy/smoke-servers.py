"""Run as livelife on an initialized public host with three fixture Git bundles.

Uses an isolated registry. Requires the real registry to be empty, since it
temporarily publishes smoke routes. Never assigns fixtures to shared staging.
No passwords/tokens printed. Temporary backends are removed in finally.
"""
import base64
import http.client
import json
from pathlib import Path
import socket
import ssl
import shutil
import sys
import time

from livelife.registry import Registry
from livelife.runtime import Runtime


def request(path, authenticated=True):
    context = ssl.create_default_context()
    sock = context.wrap_socket(socket.create_connection(("127.0.0.1", 443), timeout=10),
                               server_hostname="192.144.253.40")
    connection = http.client.HTTPConnection("192.144.253.40")
    connection.sock = sock
    headers = {}
    if authenticated:
        credentials = Path("/opt/livelife/credentials/access.txt").read_text().strip()
        headers["Authorization"] = "Basic " + base64.b64encode(credentials.encode()).decode()
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        return response.status, response.read(), response.getheader("X-Livelife-Backend-SHA")
    finally:
        connection.close()


def main():
    config = json.loads(Path("/opt/livelife/config.json").read_text())
    runtime = Runtime(config)
    actual = Registry("/opt/livelife/state", runtime, config["base_url"])
    if actual.snapshot()["instances"]:
        raise RuntimeError("smoke requires empty real registry; use a separate gateway otherwise")
    registry = Registry("/opt/livelife/smoke-29/state", runtime, config["base_url"], grace=0)
    entries = json.loads(Path(sys.argv[1]).read_text())
    assert len(entries) == 3
    try:
        for index, entry in enumerate(entries):
            key = "branch:" + str(index + 1) * 32
            result = registry.deploy(key, entry["sha"], index + 1, Path(entry["bundle"]).read_bytes())
            # Reload is asynchronous; a just-created route can reach an old
            # worker briefly. Bound the wait and report the actual response.
            deadline = time.monotonic() + 5
            while True:
                status, body, commit = request(result["api_path"] + "test/hello")
                if status == 200 or time.monotonic() >= deadline:
                    break
                time.sleep(0.1)
            assert status == 200, f"hello returned {status}: {body[:200]!r}"
            assert json.loads(body) == {"message": "hello world"}
            assert commit == entry["sha"]
            assert request(result["api_path"] + "test/hello", authenticated=False)[0] == 401
            # FastAPI docs must address this immutable root-path correctly.
            status, body, _ = request(result["api_path"] + "docs")
            assert status == 200 and result["api_path"].encode() in body
        first = "be-" + entries[0]["sha"]
        registry.bind("frontend:900000029", first, 10, entries[0]["sha"])
        registry.release("branch:" + "1" * 32, 11)
        registry.collect()
        assert registry.lookup("frontend:900000029")["instance"] == first
        assert request(f"/api/versions/{first}/test/hello")[0] == 200
        for index in (1, 2):
            registry.release("branch:" + str(index + 1) * 32, 20 + index)
        registry.release("frontend:900000029", 30)
        registry.collect()
        assert not registry.snapshot()["instances"]
        print("PASS: 3 immutable Git versions, distinct ports, real FastAPI hello/docs, HTTPS auth, fixed binding and cleanup")
    finally:
        # Only rows belonging to this isolated smoke registry are eligible.
        for row in registry.snapshot()["instances"]:
            runtime.remove(row["id"], row["port"])
        runtime.publish({})  # The real registry was explicitly verified empty.
        shutil.rmtree("/opt/livelife/smoke-29/state")


if __name__ == "__main__":
    main()
