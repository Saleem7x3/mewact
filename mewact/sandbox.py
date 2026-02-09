
import subprocess
import time
import os
import sys
from colorama import Fore
from . import config

# Requires Docker Desktop installed and running
IMAGE_NAME = "mewact-runner"

class SandboxManager:
    def __init__(self):
        self.container_id = None
        self.enabled = config.SANDBOX_ENABLED
        if self.enabled:
            # Check if docker is available
            if not self._check_docker():
                print(f"{Fore.YELLOW}[!] Docker not found or not running. Sandbox disabled.")
                self.enabled = False
    
    def _check_docker(self):
        try:
            subprocess.run(["docker", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except:
            return False

    def start(self):
        if not self.enabled: return
        print(f"{Fore.CYAN}[*] Starting Sandbox Container ({IMAGE_NAME})...")
        try:
            # Run detached, keep alive with 'tail -f /dev/null' or similar
            # Assuming image exists. If not, user needs to build it.
            cmd = [
                "docker", "run", "-d", "--rm", 
                "--name", "mewact_sandbox",
                IMAGE_NAME, 
                "tail", "-f", "/dev/null"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.container_id = result.stdout.strip()
                print(f"{Fore.GREEN}[+] Sandbox started: {self.container_id[:12]}")
            else:
                print(f"{Fore.RED}[!] Failed to start sandbox: {result.stderr}")
                self.enabled = False
        except Exception as e:
            print(f"{Fore.RED}[!] Error starting sandbox: {e}")
            self.enabled = False

    def stop(self):
        if self.container_id:
            print(f"{Fore.CYAN}[*] Stopping Sandbox...")
            subprocess.run(["docker", "stop", self.container_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.container_id = None

    def execute(self, code, timeout=10):
        if not self.enabled or not self.container_id:
            return "Sandbox not active."
        
        # Escape code for command line - simpler to write to file inside container
        # 1. Write code to file inside container
        try:
            # Escape quotes for echo
            # This is fragile for complex code. Better: docker cp
            # For robustness, let's use a temporary python file
            
            # Create temp local file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as tf:
                tf.write(code)
                temp_filename = tf.name
            
            # Copy to container
            ctr_path = "/app/script.py"
            subprocess.run(["docker", "cp", temp_filename, f"{self.container_id}:{ctr_path}"], check=True)
            os.remove(temp_filename)
            
            # Execute
            cmd = ["docker", "exec", self.container_id, "python", ctr_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            output = result.stdout
            if result.stderr:
                output += f"\nStderr: {result.stderr}"
            return output.strip()
            
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out."
        except Exception as e:
            return f"Error executing in sandbox: {e}"

