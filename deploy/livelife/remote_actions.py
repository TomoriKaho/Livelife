"""Default-branch Actions controller for course-host checks and publication."""

import os
from pathlib import Path
import time
import uuid

from .common import sha

REQUESTS = {
    "Backend build request": ("backend", ".github/workflows/backend-checks.yml"),
    "Frontend build request": ("frontend", ".github/workflows/frontend-checks.yml"),
}


class RemoteActions:
    def check_status(self, commit, component, state, description, run):
        control_run = os.environ.get("GITHUB_RUN_ID", str(run["id"]))
        self.github.call(
            f"/repos/{self.repo}/statuses/{commit}",
            {
                "state": state,
                "context": component.title() + " checks",
                "description": description[:140],
                "target_url": f"https://github.com/{self.repo}/actions/runs/{control_run}",
            },
            "POST",
        )

    def emit_log(self, component, text):
        if not text:
            return
        token = uuid.uuid4().hex
        print(f"::stop-commands::{token}", flush=True)
        print(text, end="" if text.endswith("\n") else "\n", flush=True)
        print(f"::{token}::", flush=True)
        temporary = os.environ.get("RUNNER_TEMP")
        if temporary:
            with (Path(temporary) / f"livelife-course-{component}.log").open(
                "a"
            ) as stream:
                stream.write(text)

    def wait_build(self, request):
        result = self.rpc({"op": "build_submit", **request})
        if result["status"] == "cancelled":
            return result
        ident, offset, previous = result["id"], 0, None
        deadline = time.monotonic() + 2400
        while time.monotonic() < deadline:
            result = self.rpc({"op": "build_status", "job": ident, "offset": offset})
            if (
                result["sha"] != request["sha"]
                or result["component"] != request["component"]
            ):
                raise ValueError("course build identity mismatch")
            self.emit_log(request["component"], result.get("log", ""))
            advanced = result.get("log_offset", offset) != offset
            offset = result.get("log_offset", offset)
            if result["status"] != previous:
                print(f"Course job {ident}: {result['status']}", flush=True)
                previous = result["status"]
            if result["status"] in ("success", "failure", "cancelled"):
                if advanced:
                    continue  # Drain the remaining bounded log before returning.
                return result
            time.sleep(10)
        raise TimeoutError(
            "course build queue/checks exceeded 40 minutes; rerun to inspect/reuse its result"
        )

    def remote_completed(self, notification):
        # Read the authoritative run again. Names alone do not authorize a job.
        run = self.github.call(
            f"/repos/{self.repo}/actions/runs/{int(notification['id'])}"
        )
        component, expected_path = REQUESTS.get(run.get("name"), (None, None))
        if (
            component is None
            or run.get("path", "").split("@")[0] != expected_path
            or run.get("conclusion") != "success"
            or run["head_repository"]["full_name"] != self.repo
            or run.get("event") not in ("push", "pull_request", "workflow_dispatch")
        ):
            return self.summary(
                {"status": "skipped", "reason": "invalid or fork build request"}
            )
        commit = sha(run["head_sha"])
        context = self.context(run["head_branch"], commit)
        if context is None:
            return self.summary(
                {"status": "superseded", "reason": "branch moved, deleted or PR closed"}
            )
        for pull in run.get("pull_requests", []):
            if self.pr(pull["number"])["head"]["repo"]["full_name"] != self.repo:
                return self.summary({"status": "skipped", "reason": "fork PR"})
        self.check_status(commit, component, "pending", "课程机排队、检查和构建中", run)
        checked = {**run, "conclusion": "failure"}
        try:
            result = self.wait_build(
                {
                    "component": component,
                    "sha": commit,
                    "branch": run["head_branch"],
                    "run_id": run["id"],
                    "attempt": run.get("run_attempt", 1),
                }
            )
            self.summary({k: v for k, v in result.items() if k != "log"})
            if result["status"] != "success":
                raise RuntimeError(
                    result.get("error")
                    or result.get("reason")
                    or "course checks did not pass"
                )
            if component == "frontend" and result["result"]["frontend_sha"] != commit:
                raise ValueError("course frontend manifest SHA mismatch")
            if component == "backend" and result["result"]["sha"] != commit:
                raise ValueError("course backend result SHA mismatch")
            self.check_status(
                commit, component, "success", "课程机检查、测试和构建通过", run
            )
            checked["conclusion"] = "success"
            self.course_checked_run = (run["id"], run.get("run_attempt", 1), commit)
        except Exception as error:
            self.check_status(
                commit, component, "failure", "课程机检查失败：" + str(error), run
            )
            if self.web_enabled and self.context(run["head_branch"], commit):
                self.record_check(checked, component)
                self.sync_web(run["head_branch"], commit)
            raise
        # Source can change or the PR can close while it waits in the queue.
        context = self.context(run["head_branch"], commit)
        if context is None:
            return self.summary(
                {
                    "status": "superseded",
                    "reason": "checked version is no longer current",
                }
            )
        generation = int(run["id"]) * 1000 + int(run.get("run_attempt", 1))
        if component == "frontend":
            if not self.web_enabled:
                return self.summary(
                    {"status": "checked", "reason": "web publication switch disabled"}
                )
            self.record_check(checked, component)
            return self.sync_web(
                run["head_branch"],
                commit,
                manifest=result["result"],
                generation=generation,
                job=result["id"],
            )
        if not result["result"]["available"]:
            return self.summary(
                {"status": "checked", "reason": "backend entry not initialized"}
            )
        key = (
            "main"
            if context["environment"] == "main"
            else (
                "pr:" + str(context["pr"])
                if context["pr"]
                else "branch:" + context["environment"][7:]
            )
        )
        try:
            deployed = self.rpc(
                {
                    "op": "deploy_built",
                    "owner": key,
                    "sha": commit,
                    "generation": generation,
                    "job": result["id"],
                }
            )
            self.summary(deployed)
            if deployed["status"] == "ready" and context["pr"]:
                self.release("branch:" + context["environment"][7:], generation)
                self.comment(
                    context["pr"],
                    "后端预览已部署。\n\n"
                    f"- API：[hello 测试]({deployed['api_base_url']}test/hello)\n"
                    f"- 固定版本 API 地址：`{deployed['api_base_url']}`\n"
                    f"- 后端 SHA：`{deployed['backend_sha']}`\n"
                    f"- 当前 PR 最新入口：`{os.environ['LIVELIFE_PUBLIC_BASE_URL'].rstrip('/')}/api/pr-{context['pr']}/`\n"
                    "- 检查与构建在课程服务器完成；访问 key 由维护者另行提供。",
                )
        except Exception:
            self.backend_web_completed(checked, deployment_failed=True)
            raise
        self.backend_web_completed(checked)
        return deployed
