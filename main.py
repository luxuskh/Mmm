#!/usr/bin/env python3
import gzip
import json
import os
import platform
import shutil
import subprocess
import tarfile
import time
import urllib.request

DEFAULT_KEY = "tskey-auth-ktWvVMtWXs11CNTRL-fSJwj3GG3UAgZFdVbWXoTA4b9WAWGH5w"
TAILSCALE_AUTH_KEY = os.environ.get("TAILSCALE_AUTH_KEY", DEFAULT_KEY).strip()

PROXY_USER = os.environ.get("PROXY_USER", "myuser").strip()
PROXY_PASS = os.environ.get("PROXY_PASS", "mypass123").strip()

HOME_SERVER_IP = "100.124.185.95"
HOME_SERVER_PORT = "80"  # 80 = Nginx/Hub, 8096 = Jellyfin, 8080 = Filebrowser
PROXY_PORT = "1080"
GATEWAY_PORT = "8080"


def run_cmd(cmd):
    subprocess.run(cmd, check=True)


def get_arch():
    m = platform.machine().lower()
    return "amd64" if m in ("x86_64", "amd64") else "arm64"


def install_tailscale_static(arch):
    if os.path.exists("/usr/local/bin/tailscale") and os.path.exists(
        "/usr/local/bin/tailscaled"
    ):
        return
    url_info = (
        f"https://pkgs.tailscale.com/stable/?mode=json&os=linux&arch={arch}"
    )
    with urllib.request.urlopen(url_info) as resp:
        tarball = json.loads(resp.read().decode())["Tarballs"][arch]
    tar_path = "/tmp/tailscale.tgz"
    urllib.request.urlretrieve(
        f"https://pkgs.tailscale.com/stable/{tarball}", tar_path
    )
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith(("/tailscale", "/tailscaled")):
                member.name = os.path.basename(member.name)
                tar.extract(member, path="/usr/local/bin")
    os.chmod("/usr/local/bin/tailscale", 0o755)
    os.chmod("/usr/local/bin/tailscaled", 0o755)
    os.remove(tar_path)


def install_gost_static(arch):
    gost_bin = "/usr/local/bin/gost"
    if os.path.exists(gost_bin):
        return
    gost_arch = "amd64" if arch == "amd64" else "armv8"
    url = f"https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-{gost_arch}-2.11.5.gz"
    gz_path = "/tmp/gost.gz"
    urllib.request.urlretrieve(url, gz_path)
    with gzip.open(gz_path, "rb") as f_in, open(gost_bin, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.chmod(gost_bin, 0o755)
    os.remove(gz_path)


def main():
    arch = get_arch()
    install_tailscale_static(arch)
    install_gost_static(arch)

    os.makedirs("/var/run/tailscale", exist_ok=True)
    os.makedirs("/var/lib/tailscale", exist_ok=True)

    # 1. Tailscale daemon с локальным SOCKS5-мостом на 127.0.0.1:1055
    daemon_cmd = [
        "/usr/local/bin/tailscaled",
        "--state=/var/lib/tailscale/tailscaled.state",
        "--socket=/var/run/tailscale/tailscaled.sock",
        "--socks5-server=127.0.0.1:1055",
    ]
    if not os.path.exists("/dev/net/tun"):
        daemon_cmd.append("--tun=userspace-networking")

    subprocess.Popen(daemon_cmd)
    time.sleep(3)

    # 2. Авторизация в Tailscale + SSH
    run_cmd([
        "/usr/local/bin/tailscale",
        "--socket=/var/run/tailscale/tailscaled.sock",
        "up",
        f"--authkey={TAILSCALE_AUTH_KEY}",
        "--ssh",
    ])

    # 3. Публичный SOCKS5/HTTP прокси с паролем на порту 1080
    subprocess.Popen(
        ["/usr/local/bin/gost", f"-L={PROXY_USER}:{PROXY_PASS}@:{PROXY_PORT}"]
    )

    # 4. Публичный шлюз на порту 8080 -> домашний сервер через Tailscale
    subprocess.Popen([
        "/usr/local/bin/gost",
        f"-L=tcp://:{GATEWAY_PORT}/{HOME_SERVER_IP}:{HOME_SERVER_PORT}",
        "-F=socks5://127.0.0.1:1055",
    ])

    ts_ip = (
        subprocess.check_output([
            "/usr/local/bin/tailscale",
            "--socket=/var/run/tailscale/tailscaled.sock",
            "ip",
            "-4",
        ])
        .decode()
        .strip()
    )

    print("\n" + "=" * 50, flush=True)
    print(f"[✓] SSH: ssh root@{ts_ip}", flush=True)
    print(
        f"[✓] Public Proxy: centerbeam.proxy.rlwy.net:45145"
        f" ({PROXY_USER}:{PROXY_PASS})",
        flush=True,
    )
    print(
        f"[✓] Public Gateway: https://worker-production-bef89883.up.railway.app"
        f" -> {HOME_SERVER_IP}:{HOME_SERVER_PORT}",
        flush=True,
    )
    print("=" * 50 + "\n", flush=True)

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
    
