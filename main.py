import os, json, datetime, requests, openai
from tinydb import TinyDB
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import pickle

load_dotenv()


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('gmail_sa.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)


openai.api_key = os.getenv("OPENAI_API_KEY")
NOTION_TOKEN, NOTION_PARENT = os.getenv("NOTION_TOKEN"), os.getenv("NOTION_PARENT")
gmail = get_gmail_service()
db = TinyDB("digests.db.json")                               # Tiny memory layer

def summarize_gmail_threads():
    threads = gmail.users().threads().list(userId="me", maxResults=20).execute().get("threads", [])
    filtered_msgs = []
    for t in threads:
        thread = gmail.users().threads().get(userId="me", id=t["id"], format="metadata").execute()
        # Look at the labelIds of the first message in each thread
        msgs = thread.get("messages", [])
        if not msgs:
            continue
        label_ids = msgs[0].get("labelIds", [])
        if (
            ("CATEGORY_UPDATES" in label_ids or "INBOX" in label_ids)
            and "CATEGORY_PROMOTIONS" not in label_ids
        ):
            filtered_msgs.append(thread)

    body = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Summarize these emails as a single, readable paragraph for a daily brief. Don't use lists or bullet points."},
            {"role": "user", "content": json.dumps(filtered_msgs)}
        ],
    ).choices[0].message.content
    return body


def post_to_notion(content):
    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "parent": {"page_id": NOTION_PARENT},
            "properties": {"title": [{"text": {"content": f"Daily Brief {datetime.date.today()}"}}]},
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    }
                }
            ],
        },
        timeout=15,
    )
    print("Notion API response status:", response.status_code)
    print("Notion API response body:", response.text)

    

if __name__ == "__main__":
    print("Starting Gmail summarization agent...")
    digest = summarize_gmail_threads()
    print("Summary complete! Posting to Notion...")
    post_to_notion(digest)
    print("Posted to Notion! Logging in DB...")
    db.insert({"date": str(datetime.date.today()), "digest_len": len(digest)})
    print("All done!")
