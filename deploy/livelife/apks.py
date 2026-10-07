"""Trusted APK signing/publication. Branch artifacts are parsed, never executed."""

import base64
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

from .android_build import APP_ID, MAX_APK, validate_apk, validate_config
from .common import atomic_json, atomic_text, instance, sha


def environment(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"main|pr-[1-9][0-9]*|manual-[a-f0-9]{32}", value
    ):
        raise ValueError("invalid APK environment")
    return value


def apk_id(value):
    if not isinstance(value, str) or not re.fullmatch("[a-f0-9]{32}", value):
        raise ValueError("invalid APK ID")
    return value


MAX_STORAGE = 2 * 1024**3


class ApkRegistry:
    def __init__(self, registry):
        self.r = registry
        self.root = registry.root.parent / "apks"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def initialize(db):
        db.executescript("""CREATE TABLE IF NOT EXISTS apk_builds (
            id TEXT PRIMARY KEY, environment TEXT NOT NULL, branch TEXT NOT NULL, generation INTEGER NOT NULL,
            created REAL NOT NULL, expires REAL, state TEXT NOT NULL, config TEXT NOT NULL,
            error TEXT NOT NULL DEFAULT '', digest TEXT, size INTEGER, job TEXT);
            CREATE TABLE IF NOT EXISTS apk_environments (
            id TEXT PRIMARY KEY, generation INTEGER NOT NULL, closed INTEGER NOT NULL DEFAULT 0,
            current TEXT, attempt TEXT, binding TEXT, bind_mode TEXT);
            CREATE TABLE IF NOT EXISTS apk_counter (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL);
            INSERT OR IGNORE INTO apk_counter VALUES(1,0);""")

    def reserve(self, request):
        r = self.r
        env = environment(request["environment"])
        commit = sha(request["sha"])
        generation = request["generation"]
        if (
            not isinstance(generation, int)
            or isinstance(generation, bool)
            or generation < 1
        ):
            raise ValueError("invalid APK generation")
        branch = request["branch"]
        if (
            not isinstance(branch, str)
            or len(branch.encode()) > 255
            or any(ord(c) < 32 for c in branch)
        ):
            raise ValueError("invalid APK branch")
        ident = hashlib.sha256(f"{env}:{commit}:{generation}".encode()).hexdigest()[:32]
        with r.locked() as db:
            previous = db.execute(
                "SELECT * FROM apk_environments WHERE id=?", (env,)
            ).fetchone()
            if previous and (
                previous["generation"] > generation
                or previous["closed"]
                and previous["generation"] >= generation
            ):
                return {"status": "superseded"}
            existing = db.execute(
                "SELECT * FROM apk_builds WHERE id=?", (ident,)
            ).fetchone()
            if existing:
                return self.describe(existing)
            target, mode = request["target"], request["mode"]
            binding = previous["binding"] if previous else None
            bind_mode = previous["bind_mode"] if previous else None
            if request.get("explicit"):
                binding, bind_mode = target, mode
            elif binding:
                target, mode = binding, bind_mode
            if mode not in ("staging", "own", "fixed") or (target == "staging") != (
                mode == "staging"
            ):
                raise ValueError("invalid APK backend selection")
            if target == "staging":
                backend = db.execute(
                    "SELECT i.* FROM refs r JOIN instances i ON i.id=r.instance WHERE r.owner='main'"
                ).fetchone()
                backend_id = None
            else:
                backend_id = instance(target)
                backend = db.execute(
                    "SELECT * FROM instances WHERE id=?", (backend_id,)
                ).fetchone()
            if not backend:
                raise ValueError("APK backend is not deployed")
            # Duplicate completion notifications reuse the same physical APK.
            if not request.get("force") and previous and not previous["closed"]:
                for key in ("attempt", "current"):
                    row = db.execute(
                        "SELECT * FROM apk_builds WHERE id=?", (previous[key],)
                    ).fetchone()
                    if row and row["state"] in ("pending", "ready"):
                        config = json.loads(row["config"])
                        if (
                            config["frontend_sha"] == commit
                            and config["backend_mode"] == mode
                            and (
                                mode == "staging"
                                or config["backend_sha"] == backend["sha"]
                            )
                        ):
                            return self.describe(row)
            code = (
                db.execute("SELECT value FROM apk_counter WHERE id=1").fetchone()[0] + 1
            )
            if code > 2100000000:
                raise ValueError("Android versionCode exhausted")
            db.execute("UPDATE apk_counter SET value=? WHERE id=1", (code,))
            expires = None if env == "main" else r.clock() + 7 * 86400
            config = dict(
                schema_version=1,
                apk_id=ident,
                build_id="apk-" + ident,
                frontend_sha=commit,
                version_code=code,
                version_name=f"0.1.0-test.{code}",
                environment=env,
                api_base_url=r.base_url
                + (
                    "/api/staging/" if mode == "staging" else f"/api/versions/{target}/"
                ),
                backend_mode=mode,
                backend_sha=backend["sha"],
                status_url=f"{r.base_url}/downloads/android/build-{ident}/status.json",
                expires=expires,
            )
            validate_config(config, commit, r.base_url)
            db.execute(
                "INSERT INTO apk_builds(id,environment,branch,generation,created,expires,state,config) VALUES(?,?,?,?,?,?,?,?)",
                (
                    ident,
                    env,
                    branch,
                    generation,
                    r.clock(),
                    expires,
                    "pending",
                    json.dumps(config),
                ),
            )
            db.execute(
                "INSERT OR REPLACE INTO apk_environments VALUES(?,?,0,?,?,?,?)",
                (
                    env,
                    generation,
                    previous["current"] if previous else None,
                    ident,
                    binding,
                    bind_mode,
                ),
            )
            # Durable lease BEFORE the course build starts. Staging follows main.
            db.execute(
                "INSERT INTO refs VALUES(?,?,?,?,?)",
                ("apk:" + ident, backend_id, target, commit, None),
            )
            r.mark_unused(db)
            result = self.describe(
                db.execute("SELECT * FROM apk_builds WHERE id=?", (ident,)).fetchone()
            )
            self.write_status(result)
            return result

    def describe(self, row):
        config = json.loads(row["config"])
        env = row["environment"]
        path = "staging" if env == "main" else env
        return {
            **config,
            "status": row["state"],
            "expires": row["expires"],
            "error": row["error"],
            "created": row["created"],
            "generation": row["generation"],
            "branch": row["branch"],
            "digest": row["digest"],
            "size": row["size"],
            "download_page": f"{self.r.base_url}/downloads/android/{path}/",
            "build_page": f"{self.r.base_url}/downloads/android/build-{row['id']}/",
            "qr_url": f"{self.r.base_url}/downloads/android/{path}/qr.png?v={row['id']}",
            "apk_url": f"{self.r.base_url}/__livelife/apks/{row['id']}/livelife-test-{config['version_code']}.apk",
        }

    def lookup(self, env):
        with self.r.locked() as db:
            record = db.execute(
                "SELECT * FROM apk_environments WHERE id=?", (environment(env),)
            ).fetchone()
            if not record:
                return {"status": "missing"}
            attempted = db.execute(
                "SELECT * FROM apk_builds WHERE id=?", (record["attempt"],)
            ).fetchone()
            current = db.execute(
                "SELECT * FROM apk_builds WHERE id=?", (record["current"],)
            ).fetchone()
            result = self.describe(attempted) if attempted else {"status": "missing"}
            if record["closed"]:
                result["status"] = "released"
            if (
                current
                and current["state"] == "ready"
                and result.get("apk_id") != current["id"]
            ):
                result["last_success"] = self.describe(current)
            if record["binding"]:
                result["selection"] = {
                    "target": record["binding"],
                    "mode": record["bind_mode"],
                }
            return result

    def write_status(self, result):
        directory = self.root / result["apk_id"]
        directory.mkdir(exist_ok=True)
        atomic_json(directory / "status.json", result)

    def sign(self, directory, config):
        settings = self.r.runtime.config
        tools = Path(settings["root"]) / "build-tools"
        sdk = tools / "android-sdk/build-tools/36.0.0"
        java = tools / "jdk/bin/java"
        import os

        env = {
            **os.environ,
            "JAVA_HOME": str(tools / "jdk"),
            "PATH": str(java.parent) + ":/usr/bin:/bin",
        }
        unsigned, aligned = directory / "unsigned.apk", directory / "aligned.apk"
        output = directory / f"livelife-test-{config['version_code']}.apk"
        badging = subprocess.check_output(
            [str(sdk / "aapt2"), "dump", "badging", str(unsigned)], env=env, timeout=30
        ).decode()
        if not re.search(
            r"package: name='"
            + re.escape(APP_ID)
            + r"' versionCode='"
            + str(config["version_code"])
            + r"' versionName='"
            + re.escape(config["version_name"])
            + "'",
            badging,
        ):
            raise ValueError("APK applicationId/version mismatch")
        if "sdkVersion:'24'" not in badging or "targetSdkVersion:'36'" not in badging:
            raise ValueError("APK SDK mismatch")
        subprocess.run(
            [str(sdk / "zipalign"), "-f", "-p", "4", str(unsigned), str(aligned)],
            check=True,
            env=env,
            timeout=120,
            capture_output=True,
        )
        credentials = Path(settings["root"]) / "credentials"
        subprocess.run(
            [
                str(sdk / "apksigner"),
                "sign",
                "--ks",
                str(credentials / "android-test.jks"),
                "--ks-key-alias",
                "livelife-test",
                "--ks-pass",
                "file:" + str(credentials / "android-test.pass"),
                "--key-pass",
                "file:" + str(credentials / "android-test.pass"),
                "--v4-signing-enabled",
                "false",
                "--out",
                str(output),
                str(aligned),
            ],
            check=True,
            env=env,
            timeout=120,
            capture_output=True,
        )
        report = subprocess.check_output(
            [
                str(sdk / "apksigner"),
                "verify",
                "--verbose",
                "--print-certs",
                str(output),
            ],
            env=env,
            timeout=30,
        ).decode()
        expected = (credentials / "android-test.sha256").read_text().strip().lower()
        if "Signer #1 certificate SHA-256 digest: " + expected not in report:
            raise ValueError("unexpected APK signer")
        validate_apk(output.read_bytes(), config)
        unsigned.unlink()
        aligned.unlink()
        return output

    def publish_built(self, request):
        ident = apk_id(request["apk_id"])
        with self.r.locked() as db:
            self.collect(db)
        self.prune_files()
        with self.r.locked() as db:
            row = db.execute("SELECT * FROM apk_builds WHERE id=?", (ident,)).fetchone()
            if not row:
                raise ValueError("unknown APK reservation")
            if row["state"] != "pending":
                return self.describe(row)
            config = json.loads(row["config"])
        artifact = self.r.runtime.rpc(
            {
                "op": "build_artifact",
                "component": "android",
                "job": request["job"],
                "sha": config["frontend_sha"],
            }
        )
        data = base64.b64decode(artifact["bundle"], validate=True)
        manifest = artifact["manifest"]
        if (
            manifest["config"] != config
            or manifest["digest"] != hashlib.sha256(data).hexdigest()
        ):
            raise ValueError("course APK manifest mismatch")
        validate_apk(data, config)
        with self.r.locked() as db:
            row = db.execute("SELECT * FROM apk_builds WHERE id=?", (ident,)).fetchone()
            record = db.execute(
                "SELECT * FROM apk_environments WHERE id=?", (row["environment"],)
            ).fetchone()
            if row["state"] != "pending":
                return self.describe(row)
            if record["closed"] or record["attempt"] != ident:
                self.expire(db, row, "superseded")
                return {"status": "superseded"}
            self.collect(db)
            usage = sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())
            if usage + len(data) * 3 > MAX_STORAGE:
                raise ValueError("APK storage budget exceeded")
            directory = self.root / ident
            directory.mkdir(exist_ok=True)
            (directory / "unsigned.apk").write_bytes(data)
            output = self.sign(directory, config)
            if output.stat().st_size > MAX_APK:
                raise ValueError("signed APK exceeds 64 MiB")
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            previous_routes = self.r.routes(db)
            old = db.execute(
                "SELECT * FROM apk_builds WHERE id=?", (record["current"],)
            ).fetchone()
            if row["environment"] == "main" and old and old["id"] != ident:
                expires = self.r.clock() + 7 * 86400
                db.execute(
                    "UPDATE apk_builds SET expires=? WHERE id=?", (expires, old["id"])
                )
                db.execute(
                    "UPDATE refs SET expires=? WHERE owner=?",
                    (expires, "apk:" + old["id"]),
                )
                self.write_status(
                    self.describe(
                        db.execute(
                            "SELECT * FROM apk_builds WHERE id=?", (old["id"],)
                        ).fetchone()
                    )
                )
            db.execute(
                "UPDATE apk_builds SET state='ready',digest=?,size=?,job=? WHERE id=?",
                (digest, output.stat().st_size, request["job"], ident),
            )
            db.execute(
                "UPDATE apk_environments SET current=? WHERE id=?",
                (ident, row["environment"]),
            )
            db.execute(
                "UPDATE refs SET expires=? WHERE owner=?",
                (row["expires"], "apk:" + ident),
            )
            result = self.describe(
                db.execute("SELECT * FROM apk_builds WHERE id=?", (ident,)).fetchone()
            )
            self.write_status(result)
            self.write_page(result)
            self.r.publish(db, previous_routes)
            return result

    def write_page(self, result):
        from datetime import datetime, timezone
        import qrcode

        directory = self.root / result["apk_id"]
        date = (
            "main 最新包永久保留"
            if result["expires"] is None
            else datetime.fromtimestamp(result["expires"], timezone.utc).isoformat()
        )

        def escape(value):
            return html.escape(str(value), quote=True)

        page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Livelife Android 测试包</title>
<style>body{{max-width:680px;margin:32px auto;padding:16px;font:16px/1.7 system-ui}}code{{overflow-wrap:anywhere}}img{{width:240px}}a{{display:inline-block;padding:8px}}.warn{{color:#974500}}</style>
<h1>Livelife Android 测试包</h1><p class="warn">样例演示应用，业务登录尚未实现。最低 Android 7；此页面不代表真机验收通过。</p>
<p id="status">正在核对安装包有效期…</p><p><a id="download" hidden href="{escape(result["apk_url"])}">下载 APK · {escape(result["version_name"])}</a></p>
<img src="qr.png" alt="Android 下载页二维码"><p>有效期：{escape(date)}</p>
<p>客户端 SHA：<code>{escape(result["frontend_sha"])}</code><br>后端模式：{escape(result["backend_mode"])}<br>后端 SHA：<code>{escape(result["backend_sha"])}</code><br>API：<code>{escape(result["api_base_url"])}</code><br>versionCode：{result["version_code"]}<br>SHA-256：<code>{escape(result["digest"])}</code></p>
<p>手机扫码打开页面，下载后允许浏览器安装未知来源应用。各 PR 共用同一测试应用，安装较新 versionCode 会覆盖；切回旧代码请重新构建，勿直接降级。包到期后不能继续接口测试。</p>
<p><a href="https://github.com/TomoriKaho/Livelife/blob/main/docs/android-testing.md">完整安装与验收教程</a></p>
<script>fetch('status.json',{{cache:'no-store'}}).then(r=>{{if(!r.ok)throw Error('状态读取失败');return r.json()}}).then(s=>{{const ok=s.status==='ready'&&(s.expires===null||Date.now()<s.expires*1000);document.getElementById('status').textContent=ok?'可下载安装':'此测试包已过期或被释放，请下载新的版本';document.getElementById('download').hidden=!ok;}}).catch(()=>{{document.getElementById('status').textContent='无法确认安装包状态，请稍后刷新';}});</script></html>'''
        atomic_text(directory / "index.html", page)
        qrcode.make(result["download_page"]).save(directory / "qr.png")

    def fail(self, ident, error):
        with self.r.locked() as db:
            row = db.execute(
                "SELECT * FROM apk_builds WHERE id=?", (apk_id(ident),)
            ).fetchone()
            if row is None:
                raise ValueError("unknown APK ID")
            if row and row["state"] == "pending":
                db.execute(
                    "UPDATE apk_builds SET error=? WHERE id=?",
                    (str(error)[:500], ident),
                )
                self.expire(
                    db,
                    db.execute(
                        "SELECT * FROM apk_builds WHERE id=?", (ident,)
                    ).fetchone(),
                    "failure",
                )
            return self.describe(
                db.execute("SELECT * FROM apk_builds WHERE id=?", (ident,)).fetchone()
            )

    def expire(self, db, row, status="expired"):
        db.execute("UPDATE apk_builds SET state=? WHERE id=?", (status, row["id"]))
        db.execute("DELETE FROM refs WHERE owner=?", ("apk:" + row["id"],))
        self.write_status(
            self.describe(
                db.execute(
                    "SELECT * FROM apk_builds WHERE id=?", (row["id"],)
                ).fetchone()
            )
        )
        self.r.mark_unused(db)

    def release(self, env, generation):
        environment(env)
        if env == "main":
            raise ValueError("main APK cannot be released")
        with self.r.locked() as db:
            record = db.execute(
                "SELECT * FROM apk_environments WHERE id=?", (environment(env),)
            ).fetchone()
            if not record:
                db.execute(
                    "INSERT INTO apk_environments(id,generation,closed) VALUES(?,?,1)",
                    (env, generation),
                )
                return {"status": "released"}
            if record["generation"] > generation:
                return {"status": "superseded"}
            previous = self.r.routes(db)
            for row in db.execute(
                "SELECT * FROM apk_builds WHERE environment=? AND state IN ('pending','ready')",
                (env,),
            ).fetchall():
                self.expire(db, row, "released")
            db.execute(
                "UPDATE apk_environments SET closed=1,generation=? WHERE id=?",
                (generation, env),
            )
            self.r.publish(db, previous)
            return {"status": "released"}

    def collect(self, db):
        now = self.r.clock()
        for row in db.execute(
            "SELECT * FROM apk_builds WHERE (state='ready' AND expires IS NOT NULL AND expires<=?) OR (state='pending' AND created<=?)",
            (now, now - 7200),
        ).fetchall():
            self.expire(db, row, "expired" if row["state"] == "ready" else "failure")

    def routes(self, db):
        result = {}
        for row in db.execute("SELECT * FROM apk_builds"):
            result[f"/downloads/android/build-{row['id']}/"] = {
                "kind": "apk",
                "apk_id": row["id"],
            }
        for env in db.execute(
            "SELECT * FROM apk_environments WHERE closed=0 AND current IS NOT NULL"
        ):
            row = db.execute(
                "SELECT * FROM apk_builds WHERE id=? AND state='ready'",
                (env["current"],),
            ).fetchone()
            if row:
                path = "staging" if env["id"] == "main" else env["id"]
                result[f"/downloads/android/{path}/"] = {
                    "kind": "apk",
                    "apk_id": row["id"],
                }
        return result

    def recover(self, db):
        self.collect(db)
        for row in db.execute("SELECT * FROM apk_builds"):
            self.write_status(self.describe(row))
        self.r.runtime.publish(self.r.routes(db))

    def prune_files(self):
        # Called only AFTER state and gateway changes have committed.
        with self.r.locked() as db:
            dead = [
                r["id"]
                for r in db.execute(
                    "SELECT id FROM apk_builds WHERE state NOT IN ('pending','ready')"
                )
            ]
        for ident in dead:
            for path in (self.root / ident).glob("*.apk"):
                path.unlink(missing_ok=True)

    def snapshot(self, db):
        return {
            "apk_environments": [
                dict(r) for r in db.execute("SELECT * FROM apk_environments")
            ],
            "apk_builds": [
                self.describe(r) for r in db.execute("SELECT * FROM apk_builds")
            ],
        }
