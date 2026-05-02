"""
傳送圖片或訊息到 Discord
用法：python3 discord_send.py <channel_id> <image_path> [message]
"""
import os, sys, requests

def send_image(channel_id: str, image_path: str, message: str = ""):
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN 未設定")
        return False
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {token}"}
    with open(image_path, "rb") as f:
        r = requests.post(url, headers=headers,
                          data={"content": message},
                          files={"files[0]": (os.path.basename(image_path), f)})
    if r.status_code in (200, 201):
        print(f"✅ 已傳送：{os.path.basename(image_path)}")
        return True
    else:
        print(f"❌ 失敗 {r.status_code}: {r.text[:200]}")
        return False

def send_text(channel_id: str, message: str):
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        return False
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json={"content": message})
    return r.status_code in (200, 201)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法：python3 discord_send.py <channel_id> <image_path> [message]")
        sys.exit(1)
    send_image(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
