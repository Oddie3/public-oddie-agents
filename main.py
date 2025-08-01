import os, json, datetime, requests, openai
from tinydb import TinyDB
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

openai.api_key = os.getenv("OPENAI_API_KEY")
NOTION_TOKEN, NOTION_PARENT = os.getenv("NOTION_TOKEN"), os.getenv("NOTION_PARENT")
creds = Credentials.from_service_account_file("gmail_sa.json", scopes=["https://www.googleapis.com/auth/gmail.readonly"])
gmail = build("gmail", "v1", credentials=creds)
db = TinyDB("digests.db.json")                               # Tiny memory layer

def summarize_gmail_threads():
    threads = gmail.users().threads().list(userId="me", maxResults=10).execute().get("threads", [])
    msgs = [gmail.users().threads().get(userId="me", id=t["id"], format="metadata").execute() for t in threads]
    body = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Summarise emails"},{"role": "user", "content": json.dumps(msgs)}],
    ).choices[0].message.content
    return body

def post_to_notion(content):
    requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "parent": {"page_id": NOTION_PARENT},
            "properties": {"title": [{"text": {"content": f"Daily Brief {datetime.date.today()}"}}]},
            "children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": content}}]}}],
        },
        timeout=15,
    )

if __name__ == "__main__":
    digest = summarize_gmail_threads()
    post_to_notion(digest)
    db.insert({"date": str(datetime.date.today()), "digest_len": len(digest)})
