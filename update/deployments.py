import os
import subprocess
import shutil
import paramiko
from dotenv import load_dotenv

# Define file paths
ENV_FILE = "deployments.env"
DEPLOY_DIR = "./deploy"
KEY_DIR = "./key"

# Function to add SSH key using paramiko
def add_ssh_key(key_path):
    try:
        # Create a paramiko SSH client
        ssh = paramiko.SSHClient()
        
        # Automatically add host keys if missing
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Load the private key (no passphrase)
        private_key = paramiko.RSAKey.from_private_key_file(key_path)
        
        # Add the key to the client
        ssh.get_transport().connect(username='git', pkey=private_key)
        print(f"Successfully added SSH key: {key_path}")
    except Exception as e:
        print(f"Error adding SSH key with paramiko: {e}")

# Initialize Git executable and environment for Windows or non-Windows systems
if os.name == 'nt':  # Windows
    GIT_PATH = shutil.which("git")

    if GIT_PATH is None:
        GIT_PATH = os.path.abspath(os.path.join("..", "venv", "GIT", "bin"))
        GIT_EXECUTABLE = os.path.abspath(os.path.join(GIT_PATH, "git.exe"))
    else:
        GIT_EXECUTABLE = os.path.abspath(GIT_PATH)

    PYTHON_CMD = "python"  # On Windows, just use 'python'

    if GIT_EXECUTABLE:
        os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
        print(f"Git executable set to: {GIT_EXECUTABLE}")
    else:
        print("Git executable could not be set. Ensure Git is installed.")

else:  # Non-Windows (Linux, macOS)
    GIT_EXECUTABLE = shutil.which("git")
    PYTHON_CMD = "python3" if shutil.which("python3") else "python"

    if GIT_EXECUTABLE:
        os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
        print(f"Git executable set to default path: {GIT_EXECUTABLE}")
    else:
        print("Git executable not found on the system.")

# Create default .env if it doesn't exist
if not os.path.exists(ENV_FILE):
    with open(ENV_FILE, "w") as f:
        f.writelines([ 
            "placeholder=./key/key\n",
            "placeholder=./key/key\n",
            "placeholder=./key/key\n",
            "placeholder=./key/key\n",
        ])
    print(f"Created {ENV_FILE} with placeholder values.")

# Load .env file
load_dotenv(ENV_FILE)

# Ensure deploy directory exists
os.makedirs(DEPLOY_DIR, exist_ok=True)
os.makedirs(KEY_DIR, exist_ok=True)

# Read deployments from .env
deployments = {}
with open(ENV_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if "=" in line and line != "placeholder=":
            repo_branch, deploy_key = line.split("=", 1)
            if deploy_key and repo_branch != "placeholder":
                deployments[repo_branch] = deploy_key

# If no valid deployments found, print message and exit
if not deployments:
    print("No deployments to manage. Press enter to continue...")
    input()
    exit(0)

# Process deployments
latest_commits = {}
for repo_branch, deploy_key in deployments.items():
    # Parse the repo_branch to get account, repo, and branch
    account_repo, branch = repo_branch.rsplit("/", 1)
    account, repo = account_repo.split("/", 1)  # Split into account and repo name
    
    repo_dir = os.path.join(DEPLOY_DIR, repo_branch.replace("/", "_"))  # Avoiding slashes in folder names

    # Ensure the repo folder exists
    if not os.path.exists(repo_dir):
        os.makedirs(repo_dir)

    # Set up SSH key and command
    abs_deploy_key = os.path.abspath(deploy_key)
    add_ssh_key(abs_deploy_key)  # Add the SSH key to the SSH client

    try:
        # Build the GitHub URL for cloning with /tree/{branch}
        repo_url = f"git@github.com:{account}/{repo}.git"
        if os.path.exists(os.path.join(repo_dir, ".git")):
            subprocess.run([GIT_EXECUTABLE, "fetch", "--all"], cwd=repo_dir, check=True)
            subprocess.run([GIT_EXECUTABLE, "clean", "-fd"], cwd=repo_dir, check=True)
            subprocess.run([GIT_EXECUTABLE, "reset", "--hard", f"origin/{branch}"], cwd=repo_dir, check=True)
            subprocess.run([GIT_EXECUTABLE, "pull", "--rebase", "--force", "--no-ff"], cwd=repo_dir, check=True)
        else:
            subprocess.run([GIT_EXECUTABLE, "clone", "-b", branch, repo_url, repo_dir], check=True)

        # Get latest commit hash
        result = subprocess.run([GIT_EXECUTABLE, "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True)
        latest_commits[repo_branch] = result.stdout.strip()

        print(f"Updated {repo_branch} -> {repo_dir}")

    except subprocess.CalledProcessError as e:
        print(f"Error processing {repo_branch}: {e}")

print("Deployment process completed.")
input("Press Enter to exit...")
exit(0)
