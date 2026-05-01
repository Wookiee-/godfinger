import os
import time
import psutil
import subprocess
import sys
import json

# === CONFIG ===
target_file = "mbiided.x86.exe"
max_depth = 25

# === Check autostart.cfg ===
def should_autostart():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'autostart.cfg'))

    # Check if autostart.cfg exists, if not create it with '1' as the default value
    if not os.path.exists(config_path):
        print("[AUTO-START] autostart.cfg not found. Creating it with default value (1).")
        try:
            with open(config_path, 'w') as f:
                # Writing comment and default value (1)
                f.write("# This file controls whether the auto-start feature is enabled or disabled.\n")
                f.write("# Value '1' means auto-start is enabled, and value '0' means it is disabled.\n")
                f.write("# Default value is '1'.\n")
                f.write("1\n")  # Default to 1
        except Exception as e:
            print(f"[ERROR] Failed to create autostart.cfg: {e}")
            sys.exit(1)

    # Read the value from the config file
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                return line == '1'
    except FileNotFoundError:
        print("[AUTO-START] Failed to read autostart.cfg.")
        return False

    return False

# NEW: Function to check if a specific server instance is running (by port)
def is_instance_running(process_name, port):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if process_name.lower() in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'])
                if f"net_port {port}" in cmdline:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
            continue
    return False

def get_godfinger_config():
    current_dir = os.getcwd()
    depth = 0
    while depth < max_depth:
        config_path = os.path.join(current_dir, "godfingerCfg.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                return cfg
            except Exception as e:
                print(f"[AUTO-START] Error reading godfingerCfg.json: {e}")
                return None
        current_dir = os.path.dirname(current_dir)
        depth += 1
    print(f"[AUTO-START] godfingerCfg.json not found after searching {max_depth} directories.")
    return None

if not should_autostart():
    sys.exit(0)

cfg = get_godfinger_config()
if not cfg or "Instances" not in cfg or not isinstance(cfg["Instances"], list):
    print("[AUTO-START] No valid Instances found in godfingerCfg.json. Nothing to launch.")
    sys.exit(0)

current_dir = os.getcwd()
depth = 0
while depth < max_depth:
    print(f"[AUTO-START] Searching for {target_file} in: {current_dir}")
    if os.path.exists(os.path.join(current_dir, target_file)):
        full_path = os.path.join(current_dir, target_file)
        print(f"[AUTO-START] Found {target_file} at: {full_path}")
        for instance in cfg["Instances"]:
            port = str(instance.get("port", "29070"))
            log_file = instance.get("logFilename", "server.log")
            if not is_instance_running(target_file, port):
                print(f"[AUTO-START] {target_file} instance on port {port} is not running. Launching...")
                args = [
                    full_path,
                    "--debug",
                    "+set", "g_log", log_file,
                    "+set", "g_logExplicit", "3",
                    "+set", "g_logClientInfo", "1",
                    "+set", "g_logSync", "4",
                    "+set", "com_logChat", "2",
                    "+set", "dedicated", "2",
                    "+set", "fs_game", "MBII",
                    "+exec", "server.cfg",
                    "+set", "net_port", port
                ]
                if os.name == "nt":
                    subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
                time.sleep(5)
            else:
                print(f"[AUTO-START] {target_file} instance on port {port} is already running.")
        break
    current_dir = os.path.dirname(current_dir)
    depth += 1
    if current_dir == os.path.abspath(os.sep):
        print(f"[AUTO-START] {target_file} not found in any parent directories!")
        print(f"[AUTO-START] Ensure godfinger installation is placed in a recursive subdirectory of JKA/GameData for automated starts.")
        break
    if depth >= max_depth:
        print(f"[AUTO-START] Reached max depth ({max_depth}) while searching for {target_file}.")
        break
if depth >= max_depth:
    print(f"[AUTO-START] Could not find {target_file} after {max_depth} attempts.")
    print(f"[AUTO-START] Ensure godfinger installation is placed in a recursive subdirectory of JKA/GameData for automated starts.")
