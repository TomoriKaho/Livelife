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
from livelife.web_actions import WebActions, web_environment
from livelife.android_actions import AndroidActions
from livelife.remote_actions import RemoteActions, REQUESTS


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

    def artifact(self, run_id, name='backend-bundle'):
        response = self.call(f"/repos/{self.repo}/actions/runs/{int(run_id)}/artifacts?per_page=100")
        candidates = [a for a in response["artifacts"] if a["name"] == name and not a["expired"]]
        if len(candidates) != 1:
            raise ValueError("expected one unexpired backend-bundle artifact")
        artifact = candidates[0]
        limit = (70 if name == 'frontend-bundle' else 25) * 1024 * 1024
        if artifact["size_in_bytes"] > limit:
            raise ValueError("artifact too large")
        request = urllib.request.Request(artifact["archive_download_url"],
            headers={"Authorization": "Bearer " + self.token, "User-Agent": "Livelife-control"})
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
                archive = response.read(limit + 1)
        except urllib.error.HTTPError as error:
            if error.code != 302:
                raise
            url = error.headers["Location"]
            if urllib.parse.urlparse(url).scheme != "https":
                raise ValueError("artifact redirect must be HTTPS")
            # Never forward GITHUB_TOKEN to artifact storage.
            with urllib.request.urlopen(url, timeout=30) as response:
                archive = response.read(limit + 1)
        return read_web_artifact(archive) if name == 'frontend-bundle' else read_artifact(archive)

    def comment(self, number, text):
        marker = "<!-- livelife-preview -->"
        path = f"/repos/{self.repo}/issues/{int(number)}/comments"
        page = 1
        previous = None
        while True:
            comments = self.call(f"{path}?per_page=100&page={page}")
            for item in comments:
                if item["user"]["login"] == "github-actions[bot]" and item["body"].startswith((marker, '<!-- livelife-backend-preview -->')):
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


def read_web_artifact(data):
    if len(data) > 70 * 1024 * 1024:
        raise ValueError('frontend artifact too large')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) != 2 or {e.filename for e in entries} != {'manifest.json', 'frontend.tgz'}:
            raise ValueError('unexpected frontend artifact files')
        if archive.getinfo('manifest.json').file_size > 4096 or archive.getinfo('frontend.tgz').file_size > 64 * 1024 * 1024:
            raise ValueError('expanded frontend artifact too large')
        manifest = json.loads(archive.read('manifest.json'))
        bundle = archive.read('frontend.tgz')
        from livelife.web import validate_manifest
        validate_manifest(manifest)
        if hashlib.sha256(bundle).hexdigest() != manifest['digest']:
            raise ValueError('frontend artifact digest mismatch')
        return manifest, bundle


class Controller(AndroidActions, RemoteActions, WebActions):
    def __init__(self):
        self.repo = os.environ["GITHUB_REPOSITORY"]
        self.github = GitHub(self.repo, os.environ["GH_TOKEN"])
        self.generation = int(os.environ["GITHUB_RUN_ID"]) * 1000 + int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
        self.target = os.environ["LIVELIFE_SSH_TARGET"]
        if not re.fullmatch(r"livelife@[0-9.]+", self.target):
            raise ValueError("expected dedicated livelife@IPv4 SSH target")
        self.ssh_command = ["ssh", "-C", "-T", "-i", os.environ["LIVELIFE_SSH_KEY_FILE"],
                            "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                            "-o", "UserKnownHostsFile=" + os.environ["LIVELIFE_KNOWN_HOSTS_FILE"],
                            "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15",
                            "-o", "ServerAliveCountMax=3", self.target]

    def rpc(self, request):
        payload = json.dumps(request) + '\n'
        print(f"Preview RPC: {request['op']}, {len(payload.encode())} request bytes", flush=True)
        result = subprocess.run(self.ssh_command, input=payload,
                                capture_output=True, text=True, timeout=1800)
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
        if run.get('name') == 'Frontend checks':
            return self.frontend_completed(run)
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
        request = {"op": "deploy", "owner": key, "sha": commit, "generation": generation}
        try:
            result = self.rpc(request)
            if result['status'] == 'upload_required':
                request.update(bundle=base64.b64encode(bundle).decode(), digest=hashlib.sha256(bundle).hexdigest())
                result = self.rpc(request)
            self.summary(result)
            if result["status"] == "ready" and number:
                self.release(branch_owner(branch), generation)
                self.comment(number, f"后端预览已部署。\n\n"
                    f"- API：[hello 测试]({result['api_base_url']}test/hello)\n"
                    f"- 固定版本 API 地址：`{result['api_base_url']}`\n"
                    f"- 后端 SHA：`{result['backend_sha']}`\n"
                    f"- 当前 PR 最新入口：`{os.environ['LIVELIFE_PUBLIC_BASE_URL'].rstrip('/')}/api/pr-{number}/`\n"
                    "- 网页预览由 #27 接入；网页与 API 可直接访问。\n")
        except Exception:
            if number:
                self.comment(number, f"本次后端部署失败，候选 SHA：`{commit}`。\n\n"
                    "原有成功部署保留；请查看 Actions 日志，勿将旧版当成本次提交的测试结果。")
            raise

    def comment(self, number, text):
        if self.web_enabled:
            return self.preview_comment(number, extra=text)
        return self.github.comment(number, text)

    def reconcile(self):
        snapshot = self.rpc({"op": "snapshot"})
        for ref in snapshot["refs"]:
            if re.fullmatch(r"(pr|frontend):[1-9][0-9]*", ref["owner"]):
                number = int(ref["owner"].split(":")[1])
                # API failures stop reconciliation, never imply all PRs closed.
                if self.pr(number)["state"] != "open":
                    self.release(ref["owner"])
        if self.web_enabled:
            self.reconcile_web()
        self.reconcile_android()
        self.summary(self.rpc({"op": "collect"}))


    def manual(self, inputs):
        op = inputs["operation"]
        if op == "android-build":
            return self.manual_android(inputs)
        if op in ("web-lookup", "web-release", "web-rollback"):
            branch = inputs.get("frontend_branch")
            if branch and inputs.get("frontend_pr"):
                raise ValueError("choose a PR or branch, not both")
            if not branch:
                pr = self.pr(int(inputs["frontend_pr"]))
                if pr["head"]["repo"]["full_name"] != self.repo:
                    raise ValueError(
                        "fork previews cannot access deployment credentials"
                    )
                branch = pr["head"]["ref"]
            key = web_environment(branch)
            request = {
                "op": op.replace("-", "_"),
                "environment": key,
                "generation": self.generation,
            }
            return self.summary(self.rpc(request))
        if op in ("collect", "recover", "snapshot"):
            return self.summary(self.rpc({"op": op}))
        if inputs.get("frontend_branch"):
            if inputs.get("frontend_pr"):
                raise ValueError("choose a PR or branch, not both")
            branch = inputs["frontend_branch"]
            if branch == "main":
                raise ValueError("main frontend always follows staging")
            commit = self.commit(branch)["sha"]
            key = "frontend:" + web_environment(branch)
            if op == "lookup":
                return self.summary(self.rpc({"op": "lookup", "owner": key}))
            if op == "release":
                return self.summary(self.release(key))
            target = self.manual_target(inputs["backend_target"])
            result = self.rpc(
                {
                    "op": "bind",
                    "owner": key,
                    "target": target,
                    "generation": self.generation,
                    "frontend_sha": commit,
                }
            )
            self.summary(result)
            if self.web_enabled:
                self.sync_web(branch)
            return
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
            if (
                backend_pr["state"] != "open"
                or backend_pr["head"]["repo"]["full_name"] != self.repo
            ):
                raise ValueError("backend target must be an open same-repository PR")
            current = self.rpc({"op": "lookup", "owner": "pr:" + str(backend_number)})
            if current["backend_sha"] != backend_pr["head"]["sha"]:
                raise ValueError("backend latest SHA is not deployed yet")
            target = current[
                "instance"
            ]  # Pin the resolved SHA; don't race an alias update.
        result = self.rpc(
            {
                "op": "bind",
                "owner": key,
                "target": target,
                "frontend_sha": pr["head"]["sha"],
                "generation": self.generation,
            }
        )
        self.summary(result)
        if result["status"] != "ready":
            return  # A newer binding/close won; don't advertise this request.
        if self.web_enabled:
            return self.sync_web(pr["head"]["ref"])
        self.github.comment(
            number,
            f"后端绑定已更新。\n\n"
            f"- API 地址：`{result['api_base_url']}`\n"
            f"- 后端 SHA：`{result['backend_sha']}`\n"
            "- 这是 #29 的绑定记录；#27 接入后负责更新网页配置。\n",
        )


    def manual_target(self, target):
        if re.fullmatch(r'pr-[1-9][0-9]*', target):
            number = int(target[3:])
            pr = self.pr(number)
            if pr['state'] != 'open' or pr['head']['repo']['full_name'] != self.repo:
                raise ValueError('backend target must be an open same-repository PR')
            current = self.rpc({'op': 'lookup', 'owner': 'pr:' + str(number)})
            if current['backend_sha'] != pr['head']['sha']:
                raise ValueError('backend latest SHA is not deployed yet')
            return current['instance']
        return target

    def handle(self, event_name, event):
        if event_name == "workflow_run":
            run = event["workflow_run"]
            if run.get("name") in REQUESTS:
                result = self.remote_completed(run)
                if self.android_enabled and getattr(self, "course_checked_run", None) == (run["id"], run.get("run_attempt", 1), run["head_sha"]):
                    checked = self.github.call(
                        f"/repos/{self.repo}/actions/runs/{int(run['id'])}"
                    )
                    if (
                        checked.get("conclusion") == "success"
                        and checked["head_repository"]["full_name"] == self.repo
                        and checked.get("path", "").split("@")[0]
                        == REQUESTS[checked["name"]][1]
                        and (
                            checked["name"] == "Frontend build request"
                            or checked["head_branch"] != "main"
                        )
                    ):
                        self.sync_android(
                            checked["head_branch"],
                            checked["head_sha"],
                            int(checked["id"]) * 1000
                            + int(checked.get("run_attempt", 1)),
                            checked["id"],
                            checked.get("run_attempt", 1),
                        )
                return result
            try:
                result = self.build_completed(run)
            except Exception:
                # Preserve the deployment error even if reporting also fails.
                try:
                    if run.get("name") != "Frontend checks":
                        self.backend_web_completed(run, deployment_failed=True)
                except Exception as report_error:
                    self.summary(
                        {"status": "failed", "report_error": str(report_error)[:500]}
                    )
                raise
            else:
                if run.get("name") != "Frontend checks":
                    self.backend_web_completed(run)
                return result
        if event_name == "workflow_dispatch":
            return self.manual(event["inputs"])
        if event_name == "pull_request_target":
            pr = self.pr(event["number"])
            if pr["head"]["repo"]["full_name"] != self.repo:
                return self.summary({"status": "skipped", "reason": "fork"})
            if pr["state"] == "open":
                if self.web_enabled:
                    self.sync_web(pr["head"]["ref"], pr["head"]["sha"])
                if self.android_enabled:
                    self.sync_android(pr["head"]["ref"], pr["head"]["sha"])
                return
                return
            if pr["state"] == "closed":
                if self.android_enabled:
                    self.summary(
                        self.rpc(
                            {
                                "op": "apk_release",
                                "environment": f"pr-{event['number']}",
                                "generation": self.generation,
                            }
                        )
                    )
                if self.web_enabled:
                    self.summary(
                        self.rpc(
                            {
                                "op": "web_release",
                                "environment": web_environment(pr["head"]["ref"]),
                                "generation": self.generation,
                            }
                        )
                    )
                self.release("pr:" + str(event["number"]))
                self.release("frontend:" + str(event["number"]))
                if self.web_enabled:
                    self.preview_comment(event["number"], {"status": "released"})
                else:
                    self.github.comment(
                        event["number"],
                        "PR 已关闭，已释放此 PR 的后端保留记录和前端绑定。\n\n"
                        "其他前端仍引用的固定版本继续保留；无引用版本经过一小时后回收。重新打开后重新检查、部署。",
                    )
            return self.summary(self.rpc({"op": "collect"}))
        if event_name == "delete":
            if event["ref_type"] == "branch":
                if self.web_enabled and event["ref"] != "main":
                    self.summary(
                        self.rpc(
                            {
                                "op": "web_release",
                                "environment": web_environment(event["ref"]),
                                "generation": self.generation,
                            }
                        )
                    )
                self.summary(self.release(branch_owner(event["ref"])))
            return
        if event_name == "schedule":
            return self.reconcile()
        raise ValueError("unsupported workflow event")



if __name__ == "__main__":
    Controller().handle(os.environ["GITHUB_EVENT_NAME"], json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()))
