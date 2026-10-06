"""Forced-command JSON RPC on the public host; never exposed over HTTP."""
import base64
import hashlib
import json
from pathlib import Path
import sys

from .registry import Registry
from .runtime import Runtime


def dispatch(registry, request):
    op = request["op"]
    if op == "deploy":
        bundle = base64.b64decode(request["bundle"], validate=True)
        if len(bundle) > 20 * 1024 * 1024 or hashlib.sha256(bundle).hexdigest() != request["digest"]:
            raise ValueError("invalid bundle digest/size")
        return registry.deploy(request["owner"], request["sha"], request["generation"], bundle)
    if op == "bind":
        return registry.bind(request["owner"], request["target"], request["generation"], request.get("frontend_sha"))
    if op == "release":
        return registry.release(request["owner"], request["generation"])
    if op == "lookup":
        return registry.lookup(request["owner"])
    if op == "collect":
        return registry.collect()
    if op == "recover":
        return registry.recover()
    if op == "snapshot":
        return registry.snapshot()
    raise ValueError("unsupported operation")


def main():
    try:
        root = Path(__file__).resolve().parents[2]
        config = json.loads((root / "config.json").read_text())
        raw = sys.stdin.buffer.read(40 * 1024 * 1024 + 1)
        if len(raw) > 40 * 1024 * 1024:
            raise ValueError("request exceeds limit")
        registry = Registry(root / "state", Runtime(config), config["base_url"])
        print(json.dumps(dispatch(registry, json.loads(raw)), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
