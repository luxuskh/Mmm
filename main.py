#!/usr/bin/env python3
import os
import subprocess
import sys
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


def main():
    if os.geteuid() != 0:
        print(
            "[!] Скрипт необходимо запускать с правами root.", file=sys.stderr
        )
        sys.exit(1)

    # 1. Скачиваем и запускаем установщик через Python (без curl)
    print("[+] Скачивание и установка Tailscale...")
    install_script = "/tmp/install_tailscale.sh"
    urllib.request.urlretrieve(
        "https://tailscale.com/install.sh", install_script
    )
    run_cmd(["sh", install_script])

    # 2. Запуск демона tailscaled напрямую в фоне (без systemd)
    print("[+] Запуск демона tailscaled в фоновом режиме...")
    os.makedirs("/var/run/tailscale", exist_ok=True)
    os.makedirs("/var/lib/tailscale", exist_ok=True)

    daemon_cmd = [
        "tailscaled",
        "--state=/var/lib/tailscale/tailscaled.state",
        "--socket=/var/run/tailscale/tailscaled.sock",
    ]
    # Если в контейнере отсутствует /dev/net/tun, переключаемся в userspace-режим
    if not os.path.exists("/dev/net/tun"):
        print(
            "[*] /dev/net/tun не найден, используется режим"
            " userspace-networking"
        )
        daemon_cmd.append("--tun=userspace-networking")

    subprocess.Popen(daemon_cmd)
    time.sleep(3)  # Даём демону 3 секунды на инициализацию сокета

    # 3. Авторизация узла и включение Tailscale SSH
    print("[+] Подключение к сети и включение Tailscale SSH...")
    run_cmd([
        "tailscale",
        "--socket=/var/run/tailscale/tailscaled.sock",
        "up",
        f"--authkey={TAILSCALE_AUTH_KEY}",
        "--ssh",
    ])

    # 4. Проверка статуса
    print("\n[+] Готово! Выданный IP-адрес в сети Tailscale:")
    run_cmd([
        "tailscale",
        "--socket=/var/run/tailscale/tailscaled.sock",
        "ip",
        "-4",
    ])

    # Удерживаем процесс активным, чтобы контейнер не завершился после настройки
    print("[*] Контейнер работает и доступен по Tailscale SSH...")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
    
