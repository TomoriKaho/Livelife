"""Trusted GitHub metadata joins independent frontend/backend completions."""
import base64
import hashlib
import os
import urllib.error
import urllib.parse

from .common import sha
from .web import validate_manifest


def web_environment(branch):
    return 'main' if branch == 'main' else 'branch-' + hashlib.sha256(branch.encode()).hexdigest()[:32]


class WebActions:
    @property
    def web_enabled(self):
        return os.environ.get('LIVELIFE_FRONTEND_ENABLED') == 'true'

    def commit(self, ref):
        return self.github.call(f'/repos/{self.repo}/commits/{urllib.parse.quote(ref, safe="")}')

    def tree(self, commit):
        info = self.commit(commit)
        tree = self.github.call(f'/repos/{self.repo}/git/trees/{info["commit"]["tree"]["sha"]}')
        return {entry['path']: entry['sha'] for entry in tree['tree']}

    def context(self, branch, commit):
        try:
            latest = self.commit(branch)['sha']
        except urllib.error.HTTPError as error:
            if error.code == 404 and branch != 'main':
                return None
            raise
        if latest != commit:
            return None
        query = urllib.parse.urlencode({'head': self.repo.split('/')[0] + ':' + branch, 'state': 'all', 'per_page': 100})
        prs = self.github.call(f'/repos/{self.repo}/pulls?{query}')
        opened = [p for p in prs if p['state'] == 'open' and p['head']['repo']['full_name'] == self.repo]
        if branch != 'main' and prs and not opened:
            return None
        number = opened[0]['number'] if opened else None
        comparison = self.github.call(f'/repos/{self.repo}/compare/main...{commit}')
        base = self.tree(comparison['merge_base_commit']['sha'])
        current = self.tree(commit)
        return {'environment': web_environment(branch), 'branch': branch, 'pr': number, 'source_sha': commit,
                'frontend_changed': current.get('frontend') != base.get('frontend'),
                'backend_changed': current.get('backend') != base.get('backend'), 'backend_tree': current.get('backend')}

    def resolve_web_backend(self, context):
        if context['environment'] == 'main' or not context['backend_changed']:
            owner = 'main'
            mode = 'staging'
        else:
            owner = 'pr:' + str(context['pr']) if context['pr'] else 'branch:' + context['environment'][7:]
            mode = 'own'
        snapshot = self.rpc({'op': 'snapshot'})
        reference = next((r for r in snapshot['refs'] if r['owner'] == owner), None)
        if reference is None:
            return None, mode
        backend = next(r for r in snapshot['instances'] if r['id'] == reference['instance'])
        if (mode == 'own' or context['environment'] == 'main') and self.tree(backend['sha']).get('backend') != context['backend_tree']:
            return None, mode
        return 'staging' if mode == 'staging' else backend['id'], mode

    def sync_web(self, branch, commit=None, manifest=None, bundle=None, generation=None, renew=True, job=None):
        commit = commit or self.commit(branch)['sha']
        context = self.context(branch, commit)
        if context is None:
            return {'status': 'superseded'}
        prior = self.rpc({'op': 'web_lookup', 'environment': context['environment']})
        if (not manifest and context['environment'] != 'main' and not context['frontend_changed']
                and not context['backend_changed'] and prior['status'] == 'missing'):
            return {'status': 'skipped', 'reason': 'no frontend or backend changes'}
        selected_build = None
        if not manifest:
            snapshot = self.rpc({'op': 'snapshot'})
            builds = {b['build_id']: b for b in snapshot.get('web_builds', [])}
            if context['environment'] == 'main' or context['frontend_changed']:
                selected_build = prior.get('desired_build') or prior.get('last_build')
                selected = builds.get(selected_build)
                if not selected or self.tree(selected['frontend_sha']).get('frontend') != self.tree(commit).get('frontend'):
                    selected_build = None
            elif context['pr'] or prior.get('desired_build'):
                main = next((e for e in snapshot.get('web_environments', []) if e['id'] == 'main'), {})
                selected_build = main.get('build_id')
        target, mode = self.resolve_web_backend(context)
        request = {'op': 'web_publish', **{k: context[k] for k in ('environment', 'branch', 'pr', 'source_sha')},
                   'generation': generation if generation is not None else self.generation,
                   'target': target, 'mode': mode, 'build_id': selected_build, 'renew': renew}
        if manifest:
            if job:
                request.update(op='web_publish_built', job=job)
            else:
                request.update(manifest=manifest, bundle=base64.b64encode(bundle).decode())
        try:
            result = self.rpc(request)
        except Exception as error:
            failed = {**prior, 'status': 'failed', 'source_sha': commit, 'error': str(error)[:500]}
            self.summary(failed)
            if context['pr']:
                self.preview_comment(context['pr'], failed)
            raise
        self.summary(result)
        if context['pr']:
            self.preview_comment(context['pr'], result)
        return result

    def preview_comment(self, number, result=None, extra=''):
        if result is None:
            pr = self.pr(number)
            result = self.rpc({'op': 'web_lookup', 'environment': web_environment(pr['head']['ref'])})
        status = result.get('status', 'waiting')
        title = {'ready': '网页预览已部署', 'waiting': '网页预览等待配套构建', 'missing': '网页预览等待前端产物',
                 'failed': '本次预览失败', 'released': 'PR 预览已清理', 'superseded': '已有更新的部署任务'}.get(status, status)
        lines = [title + '。', '']
        if result.get('frontend_sha'):
            label = '网页' if status == 'ready' else '上一次成功网页（不代表最新提交）'
            lines += [f"- {label}：[打开预览]({result['frontend_url']})",
                      f"- 前端 SHA：`{result['frontend_sha']}`",
                      f"- 构建：`{result['build_id']}`",
                      f"- 后端模式：`{result['backend_mode']}`",
                      f"- API：`{result['api_base_url']}`",
                      f"- 加载时后端 SHA：`{result['backend_sha']}`"]
        if result.get('source_sha'):
            lines.append(f"- 当前分支提交：`{result['source_sha']}`")
        for check in result.get('checks', []):
            lines.append(f"- {check['component']} 最新检查：`{check['status']}`")
        if result.get('error'):
            lines.append('- 错误：' + result['error'])
        if extra:
            lines += ['', extra]
        if status != 'released':
            lines += ['', '网页与 API 可直接访问；网页测试不表示 Android/iOS 验证通过。']
        self.github.comment(number, '\n'.join(lines))

    def record_check(self, run, component):
        self.rpc({'op': 'web_note', 'environment': web_environment(run['head_branch']), 'component': component,
                  'source_sha': sha(run['head_sha']), 'generation': int(run['id']) * 1000 + int(run.get('run_attempt', 1)),
                  'status': run['conclusion'] if run['conclusion'] in ('success', 'failure', 'cancelled') else 'failure'})

    def frontend_completed(self, run):
        if not self.web_enabled or run['head_repository']['full_name'] != self.repo:
            return self.summary({'status': 'skipped', 'reason': 'frontend disabled or fork'})
        context = self.context(run['head_branch'], run['head_sha'])
        if context is None:
            return self.summary({'status': 'superseded'})
        self.record_check(run, 'frontend')
        if run['conclusion'] != 'success':
            result = self.sync_web(run['head_branch'], run['head_sha'])
            if context['pr']:
                self.preview_comment(context['pr'], result, '前端构建失败，请查看 Frontend checks 日志。')
            return
        manifest, bundle = self.github.artifact(run['id'], 'frontend-bundle')
        validate_manifest(manifest)
        if (manifest['frontend_sha'], manifest['run_id'], manifest['run_attempt']) != (
                run['head_sha'], run['id'], run.get('run_attempt', 1)):
            raise ValueError('web artifact identity does not match its workflow run')
        return self.sync_web(run['head_branch'], run['head_sha'], manifest, bundle,
                             int(run['id']) * 1000 + int(run.get('run_attempt', 1)))

    def reconcile_web(self):
        snapshot = self.rpc({'op': 'snapshot'})
        for env in snapshot.get('web_environments', []):
            if env.get('closed'):
                continue
            try:
                if env.get('pr') and self.pr(env['pr'])['state'] == 'closed':
                    self.rpc({'op': 'web_release', 'environment': env['id'], 'generation': self.generation})
                    self.preview_comment(env['pr'], {'status': 'released'})
                else:
                    self.sync_web(env['branch'], renew=False)
            except urllib.error.HTTPError as error:
                if error.code != 404 or env['id'] == 'main':
                    raise
                self.rpc({'op': 'web_release', 'environment': env['id'], 'generation': self.generation})

    def backend_web_completed(self, run, deployment_failed=False):
        if not self.web_enabled or run['head_repository']['full_name'] != self.repo:
            return
        context = self.context(run['head_branch'], run['head_sha'])
        if context is None:
            return
        self.record_check({**run, 'conclusion': 'failure'} if deployment_failed else run, 'backend')
        # Backend-only unpublished branches keep their API lease without creating a web environment.
        if context['pr'] or context['environment'] == 'main' or context['frontend_changed']:
            self.sync_web(run['head_branch'], run['head_sha'])
        if context['environment'] == 'main':
            self.reconcile_web()
