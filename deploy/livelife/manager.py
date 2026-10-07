"""Forced-command JSON RPC on the public host; never exposed over HTTP."""
import base64
import hashlib
import json
from pathlib import Path
import sys

from .registry import Registry
from .runtime import Runtime
from .common import read_request


def dispatch(registry, request):
    op = request["op"]
    if op in ('build_submit', 'build_status'):
        return registry.runtime.rpc(request)
    if op == 'deploy_built':
        return registry.deploy(request['owner'], request['sha'], request['generation'], None, request['job'])
    if op == 'web_publish_built':
        result = registry.runtime.rpc({'op': 'build_artifact', 'job': request['job'], 'sha': request['source_sha']})
        manifest = result['manifest']
        if manifest['frontend_sha'] != request['source_sha']:
            raise ValueError('course frontend SHA mismatch')
        return registry.web.publish({**request, 'op': 'web_publish', 'manifest': manifest,
                                     'bundle': base64.b64decode(result['bundle'], validate=True)})
    if op == 'web_note':
        return registry.web.note(request)
    if op == 'web_publish':
        if 'bundle' in request:
            request = dict(request, bundle=base64.b64decode(request['bundle'], validate=True))
        return registry.web.publish(request)
    if op == 'web_lookup':
        return registry.web.lookup(request['environment'])
    if op == 'web_release':
        return registry.web.release(request['environment'], request['generation'])
    if op == 'web_rollback':
        return registry.web.rollback(request['environment'], request['generation'])
    if op == "deploy":
        bundle = None
        if 'bundle' in request:
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


def main(request=None):
    try:
        root = Path(__file__).resolve().parents[2]
        config = json.loads((root / "config.json").read_text())
        if request is None:
            request = read_request(sys.stdin.buffer, 96 * 1024 * 1024)
        registry = Registry(root / "state", Runtime(config), config["base_url"])
        print(json.dumps(dispatch(registry, request), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
