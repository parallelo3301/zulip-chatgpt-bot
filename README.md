# Zulip ChatGPT bot

Mostly ChatGPT generated experimental bot. [You can read a related blog article.](https://blog.parallelo3301.org/blog/creating-a-zulip-bot-with-chatgpt/)

## How to use the bot

As it's a Chat bot style, it works in a conversation. This context may affect future questions, so if you want to start new conversation, you can use this:

### New conversation 

To start a new conversation (as it fetches the history for up to 6K tokens, depends on the model and settings) just write `!new` subcommand anywhere in the message.

#### Examples

```
Message: new My name is XY.
Message: @GPT new My name is XY.
Message: @GPT new New day is coming. How are you?
```

### Generally + Private message

You can simply write a direct message to the bot, and he will answer your prompt.

#### Examples

```
# Conversation; all possible messages until the token `new` are sent in the conversation
Message: new My name is XY.
GPT: ...
Message: What is my name?

# Single prompt; only the current prompt is being sent
Message: new My name is XY.
GPT: ...
Message: new What is my name?
```

### Public + private streams

You will need to active the bot by mentioning him, like `@GPT`

Those activations are then being replaced in the prompt.

To start a new conversation, you can do the same thing like in private messages.

For private streams

> Warning: I have not fully tested it with private streams yet, but there may be problems if the stream's history is Protected and bot is added as a subscriber there.


#### Examples

```
# Conversation; e.g. with previous messages
Message: @GPT !new My name is XY.
GPT: ...
Message: @GPT What is my name?

# Single prompt; only the current prompt is being sent without previous context
Message: My name is XY. @GPT
GPT: ...
# as the !new subcommand is used, GPT will not know your name
Message: @GPT !new What is my name?
```


## Running the bot

Steps to do:

1. Add Zulip Generic bot called `GPT`, and download/update the `.zuliprc`
2. [Obtain OpenAI API key](https://platform.openai.com/account/api-keys)
3. Install `python3`, `pip` and `git`
4. (optional) Create virtual env

<br>

```shell
git clone https://github.com/parallelo3301/zulip-chatgpt-bot
cd zulip-chatgpt-bot

cp .env-example .env
nano .env # fill OPENAI_API_KEY

cp .zuliprc-example .zuliprc
nano .zuliprc # replace with your config

python3 -m venv env # optional
source env/bin/activate # optional

pip install -r requirements.txt
python3 bot.py
```

4. You may also want to modify the system message in `bot.py` which says: `{"role": "system", "content": "You are an internal chatbot assistant in a software development company."}`
