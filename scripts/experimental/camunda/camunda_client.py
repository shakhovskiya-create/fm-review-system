#!/usr/bin/env python3
"""
Camunda Cloud Client - пробная интеграция.

Поддерживает:
1. Console API (аутентификация, кластеры, участники)
2. Zeebe REST API v2 (топология, деплой BPMN-процессов)

Требует: переменные окружения (см. README.md)
"""

import json
import urllib.request
import urllib.parse
import ssl
import sys
import os
import uuid
import glob as globmod

# Отключаем SSL-верификацию для корп. прокси (если нужно)
ssl._create_default_https_context = ssl._create_unverified_context


class CamundaClient:
    """Клиент для Camunda 8 Cloud Console API."""

    def __init__(self, client_id, client_secret,
                 oauth_url='https://login.cloud.camunda.io/oauth/token',
                 console_url='https://api.cloud.camunda.io',
                 audience='api.cloud.camunda.io'):
        self.client_id = client_id
        self.client_secret = client_secret
        self.oauth_url = oauth_url
        self.console_url = console_url
        self.audience = audience
        self._token = None

    def authenticate(self):
        """Получить OAuth токен через client_credentials."""
        data = urllib.parse.urlencode({
            'grant_type': 'client_credentials',
            'audience': self.audience,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }).encode()

        req = urllib.request.Request(
            self.oauth_url,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        try:
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read())
            self._token = result['access_token']
            expires = result.get('expires_in', '?')
            print(f"[OK] Аутентификация успешна. Токен действителен {expires} сек.")
            return True
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            print(f"[ОШИБКА] Аутентификация: HTTP {e.code}")
            print(f"  Ответ: {body[:200]}")
            return False
        except Exception as e:
            print(f"[ОШИБКА] Аутентификация: {e}")
            return False

    def _api_get(self, endpoint):
        """GET запрос к Console API."""
        if not self._token:
            raise RuntimeError("Не аутентифицирован. Вызовите authenticate() первым.")

        url = f"{self.console_url}{endpoint}"
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {self._token}',
            'Accept': 'application/json'
        })

        try:
            resp = urllib.request.urlopen(req, timeout=15)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            print(f"[ОШИБКА] GET {endpoint}: HTTP {e.code}")
            print(f"  Ответ: {body[:300]}")
            return None

    def list_clusters(self):
        """Получить список кластеров."""
        data = self._api_get('/clusters')
        if data is None:
            return []
        clusters = data if isinstance(data, list) else data.get('clusters', data.get('items', []))
        return clusters

    def get_cluster(self, cluster_id):
        """Получить детали кластера."""
        return self._api_get(f'/clusters/{cluster_id}')

    def list_members(self):
        """Получить список членов организации."""
        return self._api_get('/members')

    def explore(self):
        """Разведка: показать все доступное."""
        print("\n=== CAMUNDA CLOUD: РАЗВЕДКА ===\n")

        # Кластеры
        print("--- Кластеры ---")
        clusters = self.list_clusters()
        if not clusters:
            print("  Кластеров нет (или нет доступа)")
        else:
            for i, c in enumerate(clusters):
                cid = c.get('uuid', c.get('id', '?'))
                name = c.get('name', '?')
                status = c.get('status', c.get('ready', '?'))
                region = c.get('generation', {}).get('name', c.get('region', '?'))
                print(f"  [{i+1}] {name} ({cid})")
                print(f"      Статус: {status}, Регион: {region}")
                # Показать plan type если есть
                plan = c.get('planType', c.get('plan', {}))
                if plan:
                    print(f"      План: {plan}")

        # Члены организации
        print("\n--- Члены организации ---")
        members = self.list_members()
        if members:
            member_list = members if isinstance(members, list) else members.get('members', members.get('items', []))
            for m in member_list[:5]:
                name = m.get('name', m.get('email', '?'))
                roles = m.get('roles', [])
                print(f"  - {name} ({', '.join(roles) if roles else 'нет ролей'})")
            if len(member_list) > 5:
                print(f"  ... и еще {len(member_list) - 5}")
        else:
            print("  Нет данных")

        return clusters


class ZeebeClient:
    """Клиент для Camunda 8 Zeebe REST API v2."""

    def __init__(self, client_id, client_secret, cluster_id, region,
                 oauth_url='https://login.cloud.camunda.io/oauth/token'):
        self.client_id = client_id
        self.client_secret = client_secret
        self.cluster_id = cluster_id
        self.region = region
        self.oauth_url = oauth_url
        self.base_url = f'https://{region}.zeebe.camunda.io/{cluster_id}/v2'
        self._token = None

    def authenticate(self):
        """Получить OAuth токен для Zeebe API (audience: zeebe.camunda.io)."""
        data = urllib.parse.urlencode({
            'grant_type': 'client_credentials',
            'audience': 'zeebe.camunda.io',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }).encode()

        req = urllib.request.Request(
            self.oauth_url,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        try:
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read())
            self._token = result['access_token']
            expires = result.get('expires_in', '?')
            print(f"[OK] Zeebe auth: токен получен ({expires} сек)")
            return True
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            print(f"[ОШИБКА] Zeebe auth: HTTP {e.code} - {body[:200]}")
            return False

    def topology(self):
        """Получить топологию кластера."""
        req = urllib.request.Request(f'{self.base_url}/topology', headers={
            'Authorization': f'Bearer {self._token}',
            'Accept': 'application/json'
        })
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            print(f"[ОШИБКА] Topology: HTTP {e.code}")
            return None

    def deploy_bpmn(self, bpmn_path):
        """Задеплоить BPMN-файл в кластер (POST /v2/deployments)."""
        if not self._token:
            raise RuntimeError("Не аутентифицирован")

        with open(bpmn_path, 'rb') as f:
            bpmn_content = f.read()

        filename = os.path.basename(bpmn_path)
        boundary = uuid.uuid4().hex
        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="resources"; filename="{filename}"\r\n'
            f'Content-Type: application/octet-stream\r\n'
            f'\r\n'
        ).encode() + bpmn_content + f'\r\n--{boundary}--\r\n'.encode()

        req = urllib.request.Request(
            f'{self.base_url}/deployments',
            data=body,
            method='POST',
            headers={
                'Authorization': f'Bearer {self._token}',
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'Accept': 'application/json'
            }
        )

        try:
            resp = urllib.request.urlopen(req, timeout=30)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            print(f"[ОШИБКА] Deploy {filename}: HTTP {e.code}")
            print(f"  {error_body[:300]}")
            return None

    def deploy_all(self, bpmn_dir):
        """Задеплоить все BPMN из каталога."""
        files = sorted(globmod.glob(os.path.join(bpmn_dir, '*.bpmn')))
        if not files:
            print("Нет .bpmn файлов для деплоя")
            return

        print(f"\nДеплой {len(files)} BPMN в кластер {self.cluster_id}...\n")

        ok, fail = 0, 0
        for fp in files:
            name = os.path.basename(fp)
            sys.stdout.write(f"  {name} ... ")
            sys.stdout.flush()
            result = self.deploy_bpmn(fp)
            if result:
                key = result.get('deploymentKey', '?')
                print(f"OK (key={key})")
                ok += 1
            else:
                fail += 1

        print(f"\nДеплой: {ok} OK, {fail} ошибок")
        return ok, fail


def main():
    """Точка входа."""
    args = sys.argv[1:]
    mode = args[0] if args else 'console'

    if mode == 'deploy':
        # Деплой BPMN через Zeebe API
        client_id = os.environ.get('ZEEBE_CLIENT_ID')
        client_secret = os.environ.get('ZEEBE_CLIENT_SECRET')
        cluster_id = os.environ.get('CAMUNDA_CLUSTER_ID')
        region = os.environ.get('CAMUNDA_CLUSTER_REGION', 'dsm-1')

        if not client_id or not client_secret or not cluster_id:
            print("[ОШИБКА] Установите переменные:")
            print("  export ZEEBE_CLIENT_ID='...'")
            print("  export ZEEBE_CLIENT_SECRET='...'")
            print("  export CAMUNDA_CLUSTER_ID='...'")
            print("  export CAMUNDA_CLUSTER_REGION='dsm-1'")
            sys.exit(1)

        zeebe = ZeebeClient(client_id, client_secret, cluster_id, region)

        print("=== ZEEBE: ДЕПЛОЙ BPMN ===\n")
        print(f"Кластер: {cluster_id}")
        print(f"Регион: {region}")
        print(f"Client ID: {client_id[:8]}...")

        if not zeebe.authenticate():
            sys.exit(1)

        # Топология
        topo = zeebe.topology()
        if topo:
            brokers = topo.get('brokers', [])
            print(f"Топология: {len(brokers)} брокеров")
            for b in brokers:
                print(f"  Broker {b.get('nodeId')}: {b.get('version')} ({b.get('host')})")

        # Деплой
        output_dir = os.path.join(os.path.dirname(__file__), 'output')
        bpmn_path = args[1] if len(args) > 1 else None
        if bpmn_path:
            result = zeebe.deploy_bpmn(bpmn_path)
            if result:
                print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            zeebe.deploy_all(output_dir)

    else:
        # Console API (по умолчанию)
        client_id = os.environ.get('CAMUNDA_CONSOLE_CLIENT_ID')
        client_secret = os.environ.get('CAMUNDA_CONSOLE_CLIENT_SECRET')
        oauth_url = os.environ.get('CAMUNDA_OAUTH_URL', 'https://login.cloud.camunda.io/oauth/token')
        console_url = os.environ.get('CAMUNDA_CONSOLE_BASE_URL', 'https://api.cloud.camunda.io')
        audience = os.environ.get('CAMUNDA_CONSOLE_OAUTH_AUDIENCE', 'api.cloud.camunda.io')

        if not client_id or not client_secret:
            print("[ОШИБКА] Установите переменные:")
            print("  export CAMUNDA_CONSOLE_CLIENT_ID='...'")
            print("  export CAMUNDA_CONSOLE_CLIENT_SECRET='...'")
            sys.exit(1)

        client = CamundaClient(client_id, client_secret, oauth_url, console_url, audience)

        print("=== CAMUNDA CLOUD: ПРОБНОЕ ПОДКЛЮЧЕНИЕ ===\n")
        print(f"OAuth URL: {oauth_url}")
        print(f"Console URL: {console_url}")
        print(f"Client ID: {client_id[:8]}...")
        print()

        if not client.authenticate():
            sys.exit(1)

        clusters = client.explore()

        # Сохранить результат
        output = {
            'authenticated': True,
            'clusters': clusters,
            'console_url': console_url
        }
        output_path = os.path.join(os.path.dirname(__file__), 'output', 'camunda_info.json')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Результат сохранен: {output_path}")


if __name__ == '__main__':
    main()
