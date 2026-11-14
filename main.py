#!/usr/bin/env python3
import os
import subprocess
import sys

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
            "[!] Скрипт необходимо запускать с правами root (через sudo).",
            file=sys.stderr,
        )
        sys.exit(1)

    print("[+] Установка Tailscale...")
    run_cmd("curl -fsSL https://tailscale.com/install.sh | sh", shell=True)

    print("[+] Запуск службы tailscaled...")
    run_cmd(["systemctl", "enable", "--now", "tailscaled"])

    print("[+] Подключение к сети и включение Tailscale SSH...")
    run_cmd(
        ["tailscale", "up", f"--authkey={TAILSCALE_AUTH_KEY}", "--ssh"],
        shell=False,
    )

    print("\n[+] Готово! Выданный IP-адрес в сети Tailscale:")
    run_cmd(["tailscale", "ip", "-4"])


if __name__ == "__main__":
    main()
  
