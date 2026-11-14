#!/usr/bin/env python3
import os
import platform
import subprocess
import sys
import tarfile
import time
import urllib.request

TAILSCALE_AUTH_KEY = (
    "tskey-auth-kSDCXpyPbB11CNTRL-N53LaNp5ic1M6sWesKFTc1TH2LkstkRVM"
)


def run_cmd(cmd, shell=False):
    """Выполняет системную команду и проверяет код возврата."""
    print(f"[*] Выполняю: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        subprocess.run(cmd, shell=shell, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Ошибка при выполнении команды: {e}", file=sys.stderr)
        sys.exit(1)


def install_tailscale_static():
    """Скачивает и распаковывает статические бинарники Tailscale без curl/wget."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        print(f"[!] Неподдерживаемая архитектура: {machine}", file=sys.stderr)
        sys.exit(1)

    # Получаем актуальную версию стабильной ветки
    version_url = (
        f"https://pkgs.tailscale.com/stable/?mode=json&os=linux&arch={arch}"
    )
    import json

    with urllib.request.urlopen(version_url) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        tarball_name = data["Tarballs"][arch]

    download_url = f"https://pkgs.tailscale.com/stable/{tarball_name}"
    tar_path = "/tmp/tailscale.tgz"

    print(f"[+] Скачивание {tarball_name}...")
    urllib.request.urlretrieve(download_url, tar_path)

    print("[+] Распаковка бинарников в /usr/local/bin...")
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith("/tailscale") or member.name.endswith(
                "/tailscaled"
            ):
                member.name = os.path.basename(member.name)
                tar.extract(member, path="/usr/local/bin")

    os.chmod("/usr/local/bin/tailscale", 0o755)
    os.chmod("/usr/local/bin/tailscaled", 0o755)
    os.remove(tar_path)


def main():
    if os.geteuid() != 0:
        print(
            "[!] Скрипт необходимо запускать с правами root.", file=sys.stderr
        )
        sys.exit(1)

    install_tailscale_static()

    print("[+] Запуск демона tailscaled в фоновом режиме...")
    os.makedirs("/var/run/tailscale", exist_ok=True)
    os.makedirs("/var/lib/tailscale", exist_ok=True)

    daemon_cmd = [
        "/usr/local/bin/tailscaled",
        "--state=/var/lib/tailscale/tailscaled.state",
        "--socket=/var/run/tailscale/tailscaled.sock",
    ]
    if not os.path.exists("/dev/net/tun"):
        print("[*] /dev/net/tun не найден, включаем userspace-networking")
        daemon_cmd.append("--tun=userspace-networking")

    subprocess.Popen(daemon_cmd)
    time.sleep(3)

    print("[+] Подключение к сети и включение Tailscale SSH...")
    run_cmd([
        "/usr/local/bin/tailscale",
        "--socket=/var/run/tailscale/tailscaled.sock",
        "up",
        f"--authkey={TAILSCALE_AUTH_KEY}",
        "--ssh",
    ])

    print("\n[+] Готово! Выданный IP-адрес в сети Tailscale:")
    run_cmd([
        "/usr/local/bin/tailscale",
        "--socket=/var/run/tailscale/tailscaled.sock",
        "ip",
        "-4",
    ])

    print("[*] Контейнер активен и готов принимать подключения по SSH...")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
    
