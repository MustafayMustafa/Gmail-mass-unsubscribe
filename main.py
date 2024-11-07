import base64
import os.path
import sqlite3
import sys
import urllib
from email.message import EmailMessage
from typing import List, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def connect_to_db() -> Tuple[sqlite3.Cursor, sqlite3.Connection]:
    conn = sqlite3.connect("unsubscribed.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS unsubscribed (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mailto_link TEXT UNIQUE)
        """
    )
    conn.commit()

    return cursor, conn


def check_if_duplicate(cursor, mailto):
    cursor.execute("SELECT 1 FROM unsubscribed WHERE mailto_link = ?", (mailto,))
    return cursor.fetchone() is not None


def register_action(cursor, connection, mailto):
    cursor.execute("INSERT INTO unsubscribed (mailto_link) VALUES (?)", (mailto,))
    connection.commit()


def authenticate():
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ]
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return creds


def get_blacklist_patterns():
    with open("blacklist.txt", "r") as f:
        return [line.strip() for line in f.readlines()]


def get_emails_list(next_page_token, service) -> List:
    blacklist_patterns = get_blacklist_patterns()
    query_pattern = "newer_than:1y " + " ".join(blacklist_patterns)

    try:
        return (
            service.users()
            .messages()
            .list(userId="me", q=query_pattern, pageToken=next_page_token)
            .execute()
        )
    except HttpError as e:
        print(e)
        sys.exit(1)


def extract_mailto(headers):
    for header in headers:
        if header["name"].lower() == "list-unsubscribe":
            header_values = header["value"].split(",")
            for value in header_values:
                if "mailto" in value:
                    return value.strip("<> ")
    return None


def parse_mailto(mailto):
    parsed = urllib.parse.urlparse(mailto)
    email_address = parsed.path
    query_params = urllib.parse.parse_qs(parsed.query)
    subject = query_params.get("subject", [""])[0]
    body = query_params.get("body", [""])[0]

    return email_address, urllib.parse.unquote(subject), urllib.parse.unquote(body)


def send(address, subject, body, service) -> bool:
    try:
        message = EmailMessage()
        message.set_content(body)
        message["To"] = address
        message["From"] = "me"
        message["Subject"] = subject
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"raw": encoded_message}

        service.users().messages().send(userId="me", body=create_message).execute()
    except HttpError as error:
        print(f"An error occurred: {error}")
        return False

    return True


def unsubscribe(email_list, service, cursor, conn) -> int:
    counter = 0
    status = None

    messages = email_list.get("messages", [])
    if not messages:
        return 0

    # extract data from message
    for msg in messages:
        status = None
        id = msg["id"]
        message = (
            service.users().messages().get(userId="me", id=id, format="full").execute()
        )
        payload = message.get("payload", {})
        headers = payload.get("headers", [])

        mailto = extract_mailto(headers)
        if mailto:
            address, subject, body = parse_mailto(mailto)
            subject = subject if subject else "unsubscribe"

            if not check_if_duplicate(cursor, mailto):
                status = send(address, subject, body, service)
        if status:
            counter += 1
            print(f"Unsubscribed from '{address}'")
            register_action(cursor, conn, mailto)

    return counter


def main():
    db_cursor, db_conn = connect_to_db()
    credentials = authenticate()
    try:
        service = build("gmail", "v1", credentials=credentials)
    except HttpError as e:
        print(f"Error occured initialsiing the service. {e}")
        sys.exit(1)

    next_page_token = None
    unsubscribe_count = 0
    while True:
        emails = get_emails_list(next_page_token, service)
        next_page_token = emails.get("nextPageToken")
        unsubscribe_count += unsubscribe(emails, service, db_cursor, db_conn)

        # reached end of query, exit
        if not next_page_token:
            break
        print(f"Total mail lists unsubscribed: {unsubscribe_count}")


if __name__ == "__main__":
    main()
