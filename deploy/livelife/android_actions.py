"""Default-branch orchestration for Android build/sign/download records."""

from datetime import datetime, timezone
import hashlib
import os
import urllib.error
from .common import sha


class AndroidActions:
    @property
    def android_enabled(self):
        return os.environ.get("LIVELIFE_ANDROID_ENABLED") == "true"

    def android_comment_lines(self, number):
        if not self.android_enabled:
            return []
        result = self.rpc({"op": "apk_lookup", "environment": f"pr-{number}"})
        if result["status"] == "missing":
            return [
                "",
                "Android：尚无测试包；后端-only PR 可在 Preview environments 手动打包。",
            ]
        lines = ["", f"Android 本次状态：`{result['status']}`"]
        downloadable = (
            result if result["status"] == "ready" else result.get("last_success")
        )
        if downloadable:
            label = (
                "下载 Android 测试包"
                if result["status"] == "ready"
                else "上一成功测试包（不代表最新提交）"
            )
            lines += [
                f"- [{label}]({downloadable['download_page']})",
                f"- 客户端 SHA：`{downloadable['frontend_sha']}`",
                f"- Android：`{downloadable['version_name']}` / versionCode `{downloadable['version_code']}`",
                f"- 后端：`{downloadable['backend_mode']}` / `{downloadable['backend_sha']}`",
                f"- API：`{downloadable['api_base_url']}`",
                f"- 有效期：{datetime.fromtimestamp(downloadable['expires'], timezone.utc).isoformat() if downloadable['expires'] is not None else 'main 最新包永久保留'}",
                f"![Android 下载二维码]({downloadable['qr_url']})",
            ]
        if result.get("error"):
            lines.append("- Android 错误：" + result["error"])
        lines.append("安装成功不代表真机验收通过；请记录设备、版本与测试结果。")
        return lines

    def android_target(self, context, prior=None):
        selection = (prior or {}).get("selection")
        if selection:
            return selection["target"], selection["mode"]
        # Existing explicit web selection also applies on the initial APK build.
        refs = self.rpc({"op": "snapshot"})["refs"]
        owner = (
            "frontend:" + str(context["pr"])
            if context["pr"]
            else "frontend:" + context["environment"]
        )
        selected = next((r for r in refs if r["owner"] == owner), None)
        if selected:
            return (
                ("staging", "staging")
                if selected["target"] == "staging"
                else (selected["instance"], "fixed")
            )
        return self.resolve_web_backend(context)

    def run_android(
        self,
        context,
        target,
        mode,
        generation,
        run_id,
        attempt=1,
        explicit=False,
        force=False,
    ):
        env = (
            "main"
            if context["environment"] == "main"
            else (f"pr-{context['pr']}" if context["pr"] else context["environment"])
        )
        reserved = self.rpc(
            {
                "op": "apk_reserve",
                "environment": env,
                "branch": context["branch"],
                "sha": context["source_sha"],
                "generation": generation,
                "target": target,
                "mode": mode,
                "explicit": explicit,
                "force": force,
            }
        )
        if reserved["status"] not in ("pending", "ready"):
            return self.summary(reserved)
        status_run = {"id": run_id}
        if reserved["status"] == "ready":
            self.check_status(
                context["source_sha"],
                "android",
                "success",
                "已复用有效 Android 测试包",
                status_run,
            )
            return reserved
        self.check_status(
            context["source_sha"],
            "android",
            "pending",
            "课程机 Android 构建、签名与发布中",
            status_run,
        )
        try:
            if context["pr"]:
                self.preview_comment(context["pr"])
            result = self.wait_build(
                {
                    "component": "android",
                    "sha": context["source_sha"],
                    "branch": env,
                    "run_id": reserved["generation"] // 1000,
                    "attempt": reserved["generation"] % 1000,
                    "config": {
                        k: reserved[k]
                        for k in (
                            "schema_version",
                            "apk_id",
                            "build_id",
                            "frontend_sha",
                            "version_code",
                            "version_name",
                            "environment",
                            "api_base_url",
                            "backend_mode",
                            "backend_sha",
                            "status_url",
                            "expires",
                        )
                    },
                }
            )
            if result["status"] != "success":
                raise RuntimeError(result.get("error") or "Android build did not pass")
            if context["pr"] and self.pr(context["pr"])["state"] != "open":
                self.rpc(
                    {
                        "op": "apk_release",
                        "environment": env,
                        "generation": self.generation,
                    }
                )
                self.check_status(
                    context["source_sha"],
                    "android",
                    "error",
                    "PR 已关闭，测试包已释放",
                    status_run,
                )
                return {"status": "released"}
            if (
                not force
                and self.commit(context["branch"])["sha"] != context["source_sha"]
            ):
                self.rpc(
                    {
                        "op": "apk_fail",
                        "apk_id": reserved["apk_id"],
                        "error": "branch moved during build",
                    }
                )
                self.check_status(
                    context["source_sha"],
                    "android",
                    "error",
                    "分支已有新提交，本次包不发布",
                    status_run,
                )
                return {"status": "superseded"}
            result = self.rpc(
                {
                    "op": "apk_publish_built",
                    "apk_id": reserved["apk_id"],
                    "job": result["id"],
                }
            )
            self.check_status(
                context["source_sha"],
                "android",
                "success" if result["status"] == "ready" else "error",
                "Android 测试包已签名发布"
                if result["status"] == "ready"
                else "Android 任务已被更新或关闭",
                status_run,
            )
            self.summary(result)
            temporary = os.environ.get("RUNNER_TEMP")
            if temporary:
                import json
                from pathlib import Path

                (Path(temporary) / "livelife-course-android-record.json").write_text(
                    json.dumps(result, indent=2) + "\n"
                )
            return result
        except Exception as error:
            self.check_status(
                context["source_sha"],
                "android",
                "failure",
                "Android 失败：" + str(error),
                status_run,
            )
            self.rpc(
                {
                    "op": "apk_fail",
                    "apk_id": reserved["apk_id"],
                    "error": str(error)[:500],
                }
            )
            raise
        finally:
            if context["pr"]:
                self.preview_comment(context["pr"])

    def sync_android(
        self, branch, commit=None, generation=None, run_id=None, attempt=1
    ):
        if not self.android_enabled:
            return
        commit = commit or self.commit(branch)["sha"]
        context = self.context(branch, commit)
        if not context or not (
            context["environment"] == "main"
            or context["pr"]
            and context["frontend_changed"]
        ):
            return
        env = "main" if context["environment"] == "main" else f"pr-{context['pr']}"
        prior = self.rpc({"op": "apk_lookup", "environment": env})
        target, mode = self.android_target(context, prior)
        if target is None:
            self.summary(
                {
                    "status": "waiting",
                    "component": "android",
                    "reason": "paired backend is not ready",
                    "source_sha": commit,
                }
            )
            return  # Backend completion/scheduled reconciliation retries, no build slot occupied.
        return self.run_android(
            context,
            target,
            mode,
            generation or self.generation,
            run_id or int(os.environ["GITHUB_RUN_ID"]),
            attempt,
            force=attempt > 1,
        )

    def manual_android(self, inputs):
        if not self.android_enabled:
            raise ValueError("LIVELIFE_ANDROID_ENABLED must be enabled first")
        ref = inputs.get("client_ref") or "main"
        commit = self.commit(ref)["sha"]
        number = int(inputs["frontend_pr"]) if inputs.get("frontend_pr") else None
        if number:
            pr = self.pr(number)
            if pr["state"] != "open" or pr["head"]["repo"]["full_name"] != self.repo:
                raise ValueError("manual APK requires an open same-repository PR")
        ident = hashlib.sha256(f"{commit}:{self.generation}".encode()).hexdigest()[:32]
        env = "pr-" + str(number) if number else "manual-" + ident
        context = {
            "environment": env,
            "pr": number,
            "branch": ref,
            "source_sha": sha(commit),
        }
        target = inputs.get("backend_target") or "staging"
        if target == "default":
            if number:
                natural = self.context(pr["head"]["ref"], pr["head"]["sha"])
                target, mode = self.android_target(
                    natural, self.rpc({"op": "apk_lookup", "environment": env})
                )
            else:
                target, mode = "staging", "staging"
            explicit = False
        else:
            target = self.manual_target(target)
            mode = "staging" if target == "staging" else "fixed"
            explicit = True
        if not target:
            raise ValueError("paired backend is not successfully deployed yet")
        return self.run_android(
            context,
            target,
            mode,
            self.generation,
            int(os.environ["GITHUB_RUN_ID"]),
            int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
            explicit=explicit,
            force=True,
        )

    def reconcile_android(self):
        if not self.android_enabled:
            return
        snapshot = self.rpc({"op": "snapshot"})
        for env in snapshot.get("apk_environments", []):
            if env["closed"] or env["id"] == "main":
                continue
            try:
                closed = (
                    (self.pr(int(env["id"][3:]))["state"] != "open")
                    if env["id"].startswith("pr-")
                    else False
                )
                if not closed:
                    self.commit(
                        next(
                            b["branch"]
                            for b in snapshot["apk_builds"]
                            if b["environment"] == env["id"]
                        )
                    )
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                closed = True
            if closed:
                self.rpc(
                    {
                        "op": "apk_release",
                        "environment": env["id"],
                        "generation": self.generation,
                    }
                )
        pulls = self.github.call(f"/repos/{self.repo}/pulls?state=open&per_page=100")
        for pr in pulls:
            if pr["head"]["repo"]["full_name"] == self.repo:
                self.sync_android(pr["head"]["ref"], pr["head"]["sha"])
        self.sync_android("main")
