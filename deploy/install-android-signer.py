"""Copy verified signing tools course -> public host, without another download."""

import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
from livelife.runtime import Runtime

root = Path(sys.argv[1]).resolve()
data = Runtime(json.loads((root / "config.json").read_text())).rpc(
    {"op": "android_tools"}
)
bundle = base64.b64decode(data["bundle"], validate=True)
if len(bundle) > 256 * 1024**2 or hashlib.sha256(bundle).hexdigest() != data["digest"]:
    raise ValueError("invalid signing tool archive")
tools = root / "build-tools"
tools.mkdir(exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:gz") as archive:
    total = 0
    for index, item in enumerate(archive):
        total += item.size
        path = Path(item.name)
        if (
            index > 10000
            or total > 1024**3
            or path.is_absolute()
            or ".." in path.parts
            or not (item.isfile() or item.isdir())
            or not (
                item.name == "jdk"
                or item.name.startswith("jdk/")
                or item.name.startswith("android-sdk/build-tools/36.0.0")
            )
        ):
            raise ValueError("unsafe signing tool archive")
        archive.extract(item, tools, filter="data")
print(
    "Verified course-host signing tools installed; no signing secrets were transferred."
)
