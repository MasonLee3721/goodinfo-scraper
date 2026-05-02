"""
啟動時檢查 goodinfo-scraper repo 是否存在，不存在才 clone
執行：uv run python3 setup.py
"""
import os, subprocess

REPO_DIR = "/home/agent/goodinfo-scraper"
REPO_URL = "https://github.com/MasonLee3721/goodinfo-scraper.git"

def get_token():
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()

def check_and_clone():
    # 檢查 repo 是否存在且是有效的 git repo
    if os.path.isdir(os.path.join(REPO_DIR, ".git")):
        print(f"repo 已存在：{REPO_DIR}，略過 clone")
        return

    print("repo 不存在，開始 clone...")
    token = get_token()
    auth_url = REPO_URL.replace("https://", f"https://{token}@")
    subprocess.run(["git", "clone", auth_url, REPO_DIR], check=True)
    print("clone 完成")

if __name__ == "__main__":
    check_and_clone()
