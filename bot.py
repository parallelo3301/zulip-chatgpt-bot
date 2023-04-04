import os
import logging
import re
import openai
import zulip
from dotenv import load_dotenv
import tiktoken
import sqlite3

# Load the .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect('data.db')

# Set up GPT-3 API key
openai.api_key = os.environ['OPENAI_API_KEY']

# Set up Zulip client
client = zulip.Client(config_file=".zuliprc")

DEFAULT_MODEL_NAME = os.environ['DEFAULT_MODEL_NAME']
BOT_NAME = os.environ['BOT_NAME']
VERSION = "1.0.0"


def num_tokens_from_messages(messages, model="gpt-3.5-turbo"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    # note: future models may deviate from this
    if model == "gpt-3.5-turbo-0301" or model == "gpt-3.5-turbo" or model == "gpt-4":
        num_tokens = 0
        for message in messages:
            # every message follows <im_start>{role/name}\n{content}<im_end>\n
            num_tokens += 4
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += -1  # role is always required and always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not presently implemented for model {model}.
  See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")


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


def get_gpt3_response(messages, model=DEFAULT_MODEL_NAME):
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
    )

    return response.choices[0].message.content.strip()


def print_help(msg):
    # return multiline string with help message
    help_message = """# ChatGPT Assistant
This is a chatbot assistant that uses OpenAI's ChatGPT API to generate responses to your messages.

## How to use

To use the bot, simply mention it in a message, e.g. @**{bot}** hello!. The bot will then generate a response and send it back to you.
You can also write a private message to the bot without mentioning it.

## Subcommands

Subcommands are words starting with an exclamation mark, e.g. `!new`.
You can use the following subcommands to control the bot:

### General:
- `!help` - show this help message

### Context:
- `!topic` - use context from the current topic (default behaviour; subcommand not implemented/needed)
- `!stream` - use context from the current stream
- `!new` - start a new conversation; no previous context (by default, the bot will use context from the previous conversation which may affect the generated response)
- `!contexts` - (not implemented yet) list all available contexts (e.g. `!cicada`, `!frankie`)
- `!cicada` - (not implemented yet) add system context for Cicada; this may provide more accurate responses

### Model:
- `!gpt3` - use GPT-3.5 Turbo (default; 4K tokens, up to 2.5K for input)
- `!gpt4` - use GPT-4 (8K tokens, up to 6K for input)

### Global settings (not implemented yet):
- `!set` - show current settings
- `!set subcommand Cicada "Cicada is a Bitcoin and Monero wallet..."` - set your default model to GPT-3.5 Turbo

### User settings (not implemented yet):
- `!me` - show your current settings
- `!me model gpt3` - set your default model to GPT-3.5 Turbo
- `!me model gpt4` - set your default model to GPT-4

## Example usage
- `@{bot} !gpt4 !stream Can you summarise previous messages?` - use GPT-4 and context from the current stream
- `@{bot} !new I have a question...` - start a new conversation using GPT-3.5 Turbo and no context (previous messages will be ignored)

Bot version: {version}
""".format(bot=BOT_NAME, version=VERSION)
    send_reply(help_message, msg)


def get_subcommands(content):
    content_chunks = content.strip().split()
    subcommands = [word.lower().replace("!", "")
                   for word in content_chunks if word.startswith("!")]
    return subcommands


def remove_subcommands(content, subcommands):
    for subcommand in subcommands:
        content = re.sub(f"!{subcommand} ", "", content, flags=re.IGNORECASE).strip()
        content = re.sub(f"!{subcommand}", "", content, flags=re.IGNORECASE).strip()
    return content


def with_previous_messages(client, msg, messages, subcommands, token_limit):
    if msg['type'] == 'private':
        query = {
            'anchor': msg['id'],
            'num_before': 100,  # adjust this value as needed
            'num_after': 0,
            'apply_markdown': False,
            'include_anchor': False,
            'narrow': [{'operand': msg['sender_email'], 'operator': 'pm-with'}],
        }
    else:
        narrow = [
            {'operand': msg['display_recipient'], 'operator': 'stream'},
        ]

        # filter to topic by default
        if ("stream" not in subcommands):
            narrow.append({'operand': msg['subject'], 'operator': 'topic'})

        query = {
            'anchor': msg['id'],
            'num_before': 100,  # adjust this value as needed
            'num_after': 0,
            'apply_markdown': False,
            'include_anchor': False,
            'narrow': narrow,
        }

    previous_messages = client.get_messages(query)['messages']
    previous_messages.reverse()

    new_messages = messages.copy()

    for msg in previous_messages:
        content = msg['content'].strip()

        # remove mentions of the bot
        content = re.sub("@\*\*{bot}\*\*".format(bot=BOT_NAME), "", content)
        content = content.strip()

        if client.email == msg['sender_email']:
            role = "assistant"
        else:
            role = "user"

        new_messages.insert(1, {"role": role, "content": content.strip()})
        tokens = num_tokens_from_messages(messages=new_messages)

        if tokens > token_limit:
            # remove message from index 1
            new_messages = new_messages[:1] + new_messages[2:]
            break

    return new_messages


def handle_message(event):
    if event['type'] != 'message':
        return

    msg = event['message']
    content = msg['content'].strip()

    if msg['sender_email'] == client.email:
        return

    if msg['type'] != 'private' and not re.search("@\*\*{bot}\*\*".format(bot=BOT_NAME), content):
        return

    # first get rid of the command or mention trigger
    content = re.sub("@\*\*{bot}\*\*".format(bot=BOT_NAME), "", content)
    content = content.strip()

    # get subcommands (words starting with exclamation mark)
    subcommands = get_subcommands(content)
    content = remove_subcommands(content, subcommands)
    
    if subcommands and "help" in subcommands:
        print_help(msg)
        return

    model_tokens = {
        # input limit for GPT-3.5 Turbo (context 4k, prompt 2.5k, response 1.5k)
        'gpt-3.5-turbo': 2500,
        'gpt-3.5-turbo-0301': 2500,
        # input limit for GPT-4 (context 8k, prompt 6k, response 2k)
        'gpt-4': 6000,
    }

    model = DEFAULT_MODEL_NAME or 'gpt-3.5-turbo'

    # available_models = ['gpt-3.5-turbo', 'gpt-3.5-turbo-0301', 'gpt4']
    # TODO get default model from settings or check !settings

    if "gpt3" in subcommands:
        model = 'gpt-3.5-turbo'
    elif "gpt4" in subcommands:
        model = 'gpt-4'

    token_limit = model_tokens[model]

    messages = [
        {"role": "system", "content": "You are an internal chatbot assistant in a software development company called Flexiana."},
        {"role": "user", "content": f"{content}"},
    ]

    if "contexts" in subcommands:
        send_reply("This functionality is not implemented yet.", msg)
        return

    if "me" in subcommands:
        send_reply("This functionality is not implemented yet.", msg)
        return
    
    if "set" in subcommands:
        send_reply("This functionality is not implemented yet.", msg)
        return
    
    ##
    # TODO process the rest of the subcommands (like !cicada !frankie ...)
    ##

    if not subcommands or "new" not in subcommands:
        messages = with_previous_messages(
            client, msg, messages, subcommands, token_limit)

    response = get_gpt3_response(messages, model=model)
    send_reply(response, msg)


def main():
    logging.info("Starting the GPT Zulip bot...")
    client.call_on_each_event(handle_message, event_types=['message'])


if __name__ == "__main__":
    main()
