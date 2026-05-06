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
    token = get_token()
    auth_url = REPO_URL.replace("https://", f"https://{token}@")

    if os.path.isdir(os.path.join(REPO_DIR, ".git")):
        print(f"repo 已存在：{REPO_DIR}，執行 git pull 同步歷史資料...")
        subprocess.run(["git", "remote", "set-url", "origin", auth_url], cwd=REPO_DIR, check=True)
        # 先 stash 避免 unstaged changes 衝突
        subprocess.run(["git", "stash"], cwd=REPO_DIR, check=False)
        subprocess.run(["git", "pull", "--rebase"], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "stash", "pop"], cwd=REPO_DIR, check=False)
        print("git pull 完成")
        return

    print("repo 不存在，開始 clone...")
    subprocess.run(["git", "clone", auth_url, REPO_DIR], check=True)
    print("clone 完成")

if __name__ == "__main__":
    check_and_clone()
