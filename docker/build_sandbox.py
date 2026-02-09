
import subprocess
import os
import sys
from colorama import init, Fore

init(autoreset=True)

IMAGE_NAME = "mewact-runner"
DOCKERFILE = "Dockerfile.runner" # In same dir now


def build():
    if not os.path.exists(DOCKERFILE):
        print(f"{Fore.RED}[!] {DOCKERFILE} not found!")
        return

    print(f"{Fore.CYAN}[*] Building Docker Image '{IMAGE_NAME}'...")
    try:
        cmd = ["docker", "build", "-t", IMAGE_NAME, "-f", DOCKERFILE, "."]
        subprocess.check_call(cmd)
        print(f"{Fore.GREEN}[+] Build Successful! Sandbox ready.")
        print(f"{Fore.YELLOW}[!] Enable it in config.py: SANDBOX_ENABLED = True")
    except subprocess.CalledProcessError:
        print(f"{Fore.RED}[!] Build Failed. Is Docker running?")
    except FileNotFoundError:
        print(f"{Fore.RED}[!] Docker not found. Install Docker Desktop.")

if __name__ == "__main__":
    build()
