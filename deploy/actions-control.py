"""Run ONLY from the default branch in the privileged control workflow.

Artifacts are data, never executed on this runner/public host. The backend is
executed on the course host with test-only permissions after CI succeeds.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from livelife.common import sha


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, repo, token):
        self.repo = repo
        self.token = token

    def call(self, path, data=None, method=None):
        request = urllib.request.Request("https://api.github.com" + path,
            data=None if data is None else json.dumps(data).encode(), method=method,
            headers={"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
                     "User-Agent": "Livelife-backend-control", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def artifact(self, run_id):
        response = self.call(f"/repos/{self.repo}/actions/runs/{int(run_id)}/artifacts?per_page=100")
        candidates = [a for a in response["artifacts"] if a["name"] == "backend-bundle" and not a["expired"]]
        if len(candidates) != 1:
            raise ValueError("expected one unexpired backend-bundle artifact")
        artifact = candidates[0]
        if artifact["size_in_bytes"] > 25 * 1024 * 1024:
            raise ValueError("artifact too large")
        request = urllib.request.Request(artifact["archive_download_url"],
            headers={"Authorization": "Bearer " + self.token, "User-Agent": "Livelife-control"})
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
                archive = response.read(25 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            if error.code != 302:
                raise
            url = error.headers["Location"]
            if urllib.parse.urlparse(url).scheme != "https":
                raise ValueError("artifact redirect must be HTTPS")
            # Never forward GITHUB_TOKEN to artifact storage.
            with urllib.request.urlopen(url, timeout=30) as response:
                archive = response.read(25 * 1024 * 1024 + 1)
        return read_artifact(archive)

    def comment(self, number, text):
        marker = "<!-- livelife-backend-preview -->"
        path = f"/repos/{self.repo}/issues/{int(number)}/comments"
        page = 1
        previous = None
        while True:
            comments = self.call(f"{path}?per_page=100&page={page}")
            for item in comments:
                if item["user"]["login"] == "github-actions[bot]" and item["body"].startswith(marker):
                    previous = item["id"]
            if len(comments) < 100:
                break
            page += 1
        body = {"body": marker + "\n" + text}
        if previous:
            self.call(f"/repos/{self.repo}/issues/comments/{previous}", body, "PATCH")
        else:
            self.call(path, body, "POST")


def read_artifact(data):
    if len(data) > 25 * 1024 * 1024:
        raise ValueError("artifact too large")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = {e.filename for e in entries}
        if len(entries) not in (1, 2) or len(names) != len(entries) or names - {"manifest.json", "backend.tgz"}:
            raise ValueError("unexpected artifact files")
        if any(e.file_size > 20 * 1024 * 1024 for e in entries):
            raise ValueError("expanded artifact too large")
        if archive.getinfo("manifest.json").file_size > 4096:
            raise ValueError("artifact manifest too large")
        manifest = json.loads(archive.read("manifest.json"))
        sha(manifest["sha"])
        if not isinstance(manifest.get("available"), bool):
            raise ValueError("invalid artifact manifest")
        expected = {"manifest.json", "backend.tgz"} if manifest["available"] else {"manifest.json"}
        if names != expected:
            raise ValueError("artifact contents do not match manifest")
        bundle = archive.read("backend.tgz") if manifest["available"] else None
        return manifest, bundle


def branch_owner(branch):
    return "branch:" + hashlib.sha256(branch.encode()).hexdigest()[:32]


class Controller:
    def __init__(self):
        self.repo = os.environ["GITHUB_REPOSITORY"]
        self.github = GitHub(self.repo, os.environ["GH_TOKEN"])
        self.generation = int(os.environ["GITHUB_RUN_ID"]) * 1000 + int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
        self.target = os.environ["LIVELIFE_SSH_TARGET"]
        if not re.fullmatch(r"livelife@[0-9.]+", self.target):
            raise ValueError("expected dedicated livelife@IPv4 SSH target")
        self.ssh_command = ["ssh", "-T", "-i", os.environ["LIVELIFE_SSH_KEY_FILE"],
                            "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                            "-o", "UserKnownHostsFile=" + os.environ["LIVELIFE_KNOWN_HOSTS_FILE"],
                            "-o", "ConnectTimeout=10", self.target]

    def rpc(self, request):
        result = subprocess.run(self.ssh_command, input=json.dumps(request),
                                capture_output=True, text=True, timeout=900)
        if result.returncode:
            raise RuntimeError(f"deployment RPC failed: {result.stdout[-3000:]} {result.stderr[-1000:]}")
        return json.loads(result.stdout)

    def pr(self, number):
        return self.github.call(f"/repos/{self.repo}/pulls/{int(number)}")

    def release(self, key, generation=None):
        return self.rpc({"op": "release", "owner": key, "generation": generation or self.generation})

    def summary(self, result):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write("```json\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n```\n")

    def build_completed(self, run):
        if run["conclusion"] != "success" or run["head_repository"]["full_name"] != self.repo:
            return self.summary({"status": "skipped", "reason": "unsuccessful or fork run"})
        manifest, bundle = self.github.artifact(run["id"])
        if not manifest["available"]:
            return self.summary({"status": "skipped", "reason": "#24 backend not initialized"})
        commit = sha(run["head_sha"])
        if commit != manifest["sha"]:
            raise ValueError("artifact SHA does not match the GitHub workflow run")
        branch = run["head_branch"]
        latest = self.github.call(f"/repos/{self.repo}/commits/{urllib.parse.quote(branch, safe='')}")["sha"]
        if commit != latest:
            return self.summary({"status": "superseded", "reason": "branch moved"})
        query = urllib.parse.urlencode({"head": self.repo.split('/')[0] + ":" + branch, "state": "all", "per_page": 100})
        prs = self.github.call(f"/repos/{self.repo}/pulls?{query}")
        opened = [p for p in prs if p["state"] == "open" and p["head"]["repo"]["full_name"] == self.repo]
        key = "main" if branch == "main" else ("pr:" + str(opened[0]["number"]) if opened else branch_owner(branch))
        if branch != "main" and not opened and prs:
            return self.summary({"status": "skipped", "reason": "backend PR is closed"})
        number = opened[0]["number"] if opened else None
        # Use the BUILD's ordering, not the later workflow_run callback's ID.
        # A close event that happened during the build wins over its completion.
        generation = int(run["id"]) * 1000 + int(run.get("run_attempt", 1))
        request = {"op": "deploy", "owner": key, "sha": commit, "generation": generation,
                   "bundle": base64.b64encode(bundle).decode(), "digest": hashlib.sha256(bundle).hexdigest()}
        try:
            result = self.rpc(request)
            self.summary(result)
            if result["status"] == "ready" and number:
                self.release(branch_owner(branch), generation)
                self.github.comment(number, f"后端预览已部署。\n\n"
                    f"- API：[hello 测试]({result['api_base_url']}test/hello)\n"
                    f"- 固定版本 API 地址：`{result['api_base_url']}`\n"
                    f"- 后端 SHA：`{result['backend_sha']}`\n"
                    f"- 当前 PR 最新入口：`{os.environ['LIVELIFE_PUBLIC_BASE_URL'].rstrip('/')}/api/pr-{number}/`\n"
                    "- 网页预览由 #27 接入；访问凭证由维护者另行提供。\n")
        except Exception:
            if number:
                self.github.comment(number, f"本次后端部署失败，候选 SHA：`{commit}`。\n\n"
                    "原有成功部署保留；请查看 Actions 日志，勿将旧版当成本次提交的测试结果。")
            raise

    def reconcile(self):
        snapshot = self.rpc({"op": "snapshot"})
        for ref in snapshot["refs"]:
            if ref["owner"].startswith(("pr:", "frontend:")):
                number = int(ref["owner"].split(":")[1])
                # API failures stop reconciliation, never imply all PRs closed.
                if self.pr(number)["state"] != "open":
                    self.release(ref["owner"])
        self.summary(self.rpc({"op": "collect"}))

    def manual(self, inputs):
        op = inputs["operation"]
        if op in ("collect", "recover", "snapshot"):
            return self.summary(self.rpc({"op": op}))
        number = int(inputs["frontend_pr"])
        pr = self.pr(number)
        if pr["head"]["repo"]["full_name"] != self.repo:
            raise ValueError("fork previews cannot access deployment credentials")
        key = "frontend:" + str(number)
        if op == "release":
            return self.summary(self.release(key))
        if op == "lookup":
            return self.summary(self.rpc({"op": "lookup", "owner": key}))
        if op != "bind" or pr["state"] != "open":
            raise ValueError("bind requires an open frontend PR")
        target = inputs["backend_target"]
        if re.fullmatch(r"pr-[1-9][0-9]*", target):
            backend_number = int(target[3:])
            backend_pr = self.pr(backend_number)
            if backend_pr["state"] != "open" or backend_pr["head"]["repo"]["full_name"] != self.repo:
                raise ValueError("backend target must be an open same-repository PR")
            current = self.rpc({"op": "lookup", "owner": "pr:" + str(backend_number)})
            if current["backend_sha"] != backend_pr["head"]["sha"]:
                raise ValueError("backend latest SHA is not deployed yet")
            target = current["instance"]  # Pin the resolved SHA; don't race an alias update.
        result = self.rpc({"op": "bind", "owner": key, "target": target,
                           "frontend_sha": pr["head"]["sha"], "generation": self.generation})
        self.summary(result)
        self.github.comment(number, f"后端绑定已更新。\n\n"
            f"- API 地址：`{result['api_base_url']}`\n"
            f"- 后端 SHA：`{result['backend_sha']}`\n"
            "- 这是 #29 的绑定记录；#27 接入后负责更新网页配置。\n")

    def handle(self, event_name, event):
        if event_name == "workflow_run":
            return self.build_completed(event["workflow_run"])
        if event_name == "workflow_dispatch":
            return self.manual(event["inputs"])
        if event_name == "pull_request_target":
            pr = self.pr(event["number"])
            if pr["state"] == "closed":
                self.release("pr:" + str(event["number"]))
                self.release("frontend:" + str(event["number"]))
                self.github.comment(event["number"], "PR 已关闭，已释放此 PR 的后端保留记录和前端绑定。\n\n"
                    "其他前端仍引用的固定版本继续保留；无引用版本经过一小时后回收。重新打开后重新检查、部署。")
            return self.summary(self.rpc({"op": "collect"}))
        if event_name == "delete":
            if event["ref_type"] == "branch":
                self.summary(self.release(branch_owner(event["ref"])))
            return
        if event_name == "schedule":
            return self.reconcile()
        raise ValueError("unsupported workflow event")


if __name__ == "__main__":
    Controller().handle(os.environ["GITHUB_EVENT_NAME"], json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()))
