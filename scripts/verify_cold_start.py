"""Isolated, opt-in Docker rehearsal. Never uses the deployment Compose file."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
import uuid


IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
PROBE = """import json, urllib.request
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.shared.migration_info import get_current_migration_version
heads = sorted(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())
current = sorted(get_current_migration_version().split(','))
assert current == heads, (current, heads)
health = json.load(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3))
assert health['status'] == 'ok'
print(json.dumps({'heads': heads, 'health': health}))
"""


def run(args, *, check=True, timeout=180):
    # Compose never reads the caller's .env or inherited COMPOSE_* settings.
    env = {k: v for k, v in os.environ.items() if not k.startswith('COMPOSE_')}
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)
    if check and result.returncode:
        # Do not echo Docker stderr: an image may contain sensitive configuration.
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(args[:3])}")
    return result


def inspect_image(image_id, *, app=False):
    if not IMAGE_ID.fullmatch(image_id):
        raise ValueError('Use a full immutable local sha256 image ID, not a tag')
    item = json.loads(run(['docker', 'image', 'inspect', image_id]).stdout)[0]
    if item['Id'] != image_id or item.get('Os') != 'linux':
        raise ValueError('Expected an existing Linux image with the exact requested ID')
    config = item.get('Config') or {}
    if app and config.get('Volumes'):
        raise ValueError('App image declares volumes; select an image without anonymous mounts')
    if app and config.get('WorkingDir') != '/app':
        raise ValueError('App image must use /app as its working directory')
    # Reject credential-bearing image environment; never print values.
    for entry in config.get('Env') or []:
        key, _, value = entry.partition('=')
        if app and value and any(word in key.upper() for word in ('TOKEN', 'PASSWORD', 'SECRET', 'API_KEY', 'DATABASE_URL')):
            raise ValueError(f'App image has baked sensitive configuration: {key}')
    return {'id': image_id, 'created': item.get('Created'), 'architecture': item.get('Architecture')}


def compose_config(app_image, postgres_image):
    password = secrets.token_hex(24)
    environment = {
        'DATABASE_URL': f'postgresql+psycopg2://rehearsal:{password}@postgres:5432/rehearsal',
        'OWNER_API_KEY': secrets.token_hex(32),
        'OWNER_CHAT_ID': '1', 'TELEGRAM_POLLING_ENABLED': 'false',
        'TELEGRAM_STAGE_NOTIFY': 'false', 'TELEGRAM_PROACTIVE_NOTIFY_ENABLED': 'false',
        'ORCHESTRATION_ENGINE': 'rule_based', 'APP_ENVIRONMENT': 'cold-start-rehearsal',
    }
    common = {'image': app_image, 'pull_policy': 'never', 'environment': environment,
              'entrypoint': [], 'networks': ['isolated']}
    return {
        'services': {
            'postgres': {
                'image': postgres_image, 'pull_policy': 'never', 'networks': ['isolated'],
                'environment': {'POSTGRES_USER': 'rehearsal', 'POSTGRES_PASSWORD': password, 'POSTGRES_DB': 'rehearsal'},
                'volumes': ['database:/var/lib/postgresql/data'],
                'healthcheck': {'test': ['CMD', 'pg_isready', '-U', 'rehearsal', '-d', 'rehearsal'], 'interval': '2s', 'timeout': '3s', 'retries': 30},
            },
            'migrate': {**common, 'command': ['alembic', 'upgrade', 'head'],
                        'depends_on': {'postgres': {'condition': 'service_healthy'}}},
            'app': {**common, 'command': ['python', '-m', 'app.main'],
                    'depends_on': {'migrate': {'condition': 'service_completed_successfully'}}},
        },
        'volumes': {'database': {}}, 'networks': {'isolated': {'internal': True}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-image', required=True)
    parser.add_argument('--postgres-image', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='Create isolated containers; otherwise inspect images only')
    args = parser.parse_args()
    evidence = {'coverage': 'Isolated rehearsal topology, not deployment Compose; bot polling, host reboot, production and immutable release provenance NOT verified',
                'images': {'app': inspect_image(args.app_image, app=True), 'postgres': inspect_image(args.postgres_image)}, 'cycles': []}
    if not args.execute:
        print(json.dumps(evidence, indent=2))
        return
    if args.evidence.exists():
        raise ValueError('Evidence path already exists; choose a new file')
    project = 'ai-team-cold-' + uuid.uuid4().hex
    evidence['project'] = project
    with tempfile.TemporaryDirectory(prefix=project) as folder:
        config_file = Path(folder) / 'compose.json'
        env_file = Path(folder) / 'empty.env'
        env_file.write_text('', encoding='utf-8')
        config = compose_config(args.app_image, args.postgres_image)
        config_file.write_text(json.dumps(config), encoding='utf-8')
        command = ['docker', 'compose', '--project-name', project, '--project-directory', folder,
                   '--env-file', str(env_file), '-f', str(config_file)]
        # Before the cleanup scope: a collision must never delete existing resources.
        for resource in ('container', 'volume', 'network'):
            existing = run(['docker', resource, 'ls', '-q', '--filter', f'label=com.docker.compose.project={project}']).stdout.strip()
            if existing:
                raise RuntimeError('Unexpected existing resources for generated project')
        try:
            for cycle in range(1, 4):
                started = time.monotonic()
                run(command + ['up', '-d', '--no-build', 'app'])
                deadline = time.monotonic() + 120
                while True:
                    probe = run(command + ['exec', '-T', 'app', 'python', '-c', PROBE], check=False, timeout=15)
                    if probe.returncode == 0:
                        evidence['cycles'].append({'cycle': cycle, 'database': 'fresh' if cycle == 1 else 'retained',
                                                   'seconds': round(time.monotonic() - started, 2), 'probe': json.loads(probe.stdout)})
                        print(f'Cycle {cycle}/3 passed', flush=True)
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f'Cycle {cycle} did not become ready')
                    time.sleep(2)
                run(command + ['down', '--timeout', '10'])  # retain only this project's DB volume
            config['services']['migrate']['command'] = ['python', '-c', 'raise SystemExit(42)']
            config_file.write_text(json.dumps(config), encoding='utf-8')
            failed = run(command + ['up', '-d', '--no-build', 'app'], check=False)
            running = run(command + ['ps', '--status', 'running', '-q', 'app']).stdout.strip()
            migration_id = run(command + ['ps', '-a', '-q', 'migrate']).stdout.strip()
            migration = json.loads(run(['docker', 'inspect', migration_id]).stdout)[0] if migration_id else {}
            if failed.returncode == 0 or running or migration.get('State', {}).get('ExitCode') != 42:
                raise RuntimeError('Failed migration did not gate app startup')
            evidence['negative_gate'] = 'passed: intentionally failing migration prevents app running'
            print('Failed migration gate passed', flush=True)
            evidence['result'] = 'passed'
        except Exception as exc:
            evidence['result'] = 'failed'
            evidence['error'] = str(exc)
            raise
        finally:
            cleanup = run(command + ['down', '--volumes', '--timeout', '10'], check=False)
            evidence['cleanup'] = 'passed' if cleanup.returncode == 0 else 'failed; inspect exact project label'
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            if cleanup.returncode:
                raise RuntimeError(f'Cleanup failed for exact project {project}')
    print(f'Evidence: {args.evidence.resolve()}')


if __name__ == '__main__':
    main()
