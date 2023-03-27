import os
import logging
import re
import openai
from collections import deque
import zulip
from dotenv import load_dotenv
from io import StringIO
from html.parser import HTMLParser

# Load the .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)

# Set up GPT-3 API key
openai.api_key = os.environ['OPENAI_API_KEY']

# Set up Zulip client
client = zulip.Client(config_file=".zuliprc")

MODEL_TOKEN_SENT_LIMIT = int(os.environ['MODEL_TOKEN_SENT_LIMIT'])
MODEL_TOKEN_RECEIVED_LIMIT = int(os.environ['MODEL_TOKEN_RECEIVED_LIMIT'])
MODEL_NAME = os.environ['MODEL_NAME']


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def send_reply(reply, message):
    if message['type'] == 'private':
        response = {
            'type': 'private',
            'to': message['sender_email'],
            'content': reply,
        }
    else:
        response = {
            'type': 'stream',
            'to': message['display_recipient'],
            'subject': message['subject'],
            'content': reply,
        }
    client.send_message(response)


def get_gpt3_response(messages):
    response = openai.ChatCompletion.create(
        model=MODEL_NAME,
        messages=messages
    )

    return response.choices[0].message.content.strip()


def fetch_previous_messages(client, message, token_limit=MODEL_TOKEN_SENT_LIMIT):
    if message['type'] == 'private':
        query = {
            'anchor': message['id'],
            'num_before': 50,  # adjust this value as needed
            'num_after': 0,
            'narrow': [{'operand': message['sender_email'], 'operator': 'pm-with'}],
        }
    else:
        query = {
            'anchor': message['id'],
            'num_before': 50,  # adjust this value as needed
            'num_after': 0,
            'narrow': [{'operand': message['display_recipient'], 'operator': 'stream'}],
        }

    previous_messages = client.get_messages(query)['messages']
    previous_messages.reverse()

    messages = []
    token_count = 0
    stop = False
    for msg in previous_messages:
        content = strip_tags(msg['content']).strip()

        if message['type'] == 'stream':
            content = re.sub("/gpt|@GPT", "", content)
            content = content.strip()

        content_chunks = content.strip().lower().split()
        if content_chunks and content_chunks[0] == 'new':
            content = content.replace('new ', '', 1).strip()
            stop = True

        tokens = len(content.split())
        token_count += tokens

        if token_count > token_limit:
            break

        # todo role assistant dle id
        if client.email == msg['sender_email']:
            role = "assistant"
        else:
            role = "user"
        
        messages.append({"role": role, "content": content.strip()})

        if stop:
            break

    messages.reverse()
    return messages


def handle_message(event):
    if event['type'] != 'message':
        return

    msg = event['message']
    content = strip_tags(msg['content'].strip())

    if msg['sender_email'] == client.email:
        return

    if msg['type'] == 'private' or re.search("/gpt|@\*\*GPT\*\*", content):
        if msg['type'] == 'stream':
            content = re.sub("/gpt|@\*\*GPT\*\*", "", content)
            content = content.strip()

        content_chunks = content.strip().lower().split()

        messages = [
            {"role": "system", "content": "You are an internal chatbot assistant in a software development company."},
        ]

        if content_chunks and content_chunks[0] == 'new':
            messages.append(
                {"role": "user", "content": f"{content.replace('new ', '', 1)}"})
        else:
            content_tokens = len(content.split())
            previous_messages = fetch_previous_messages(
                client, msg, MODEL_TOKEN_SENT_LIMIT - content_tokens)
            messages = messages + previous_messages

        response = get_gpt3_response(messages)
        send_reply(response, msg)


def main():
    logging.info("Starting the GPT Zulip bot...")
    client.call_on_each_event(handle_message, event_types=['message'])


if __name__ == "__main__":
    main()
