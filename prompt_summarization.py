import openai
from dotenv import load_dotenv
import os
import datetime

load_dotenv()  # Necessary library call to load .env
openai.api_key = os.environ["OPENAI_API_KEY"]  # Sets OpenAI API key from .env

LOW_THRES = 200  # Values, note that as LOW_THRES is lowered, greater chance of data loss in conversation
MEDIUM_THRES = 600
CONVO_THRESHOLD = MEDIUM_THRES

DELIMITER = "###"


# This is a very standard function to get openai completion
# PARAMS: messages: A list of dicts, prompt: string that holds the prompt, model_name: model to be used string
def get_completion_with_tokens(
    messages, prompt, model_name="gpt-3.5-turbo"
):  # tuple: str, dict: {"prompt_tokens": #, "completion_tokens": #, "total_tokens": #}
    messages.append({"role": "user", "content": prompt})
    response = openai.ChatCompletion.create(
        model=model_name, messages=messages, temperature=0
    )
    messages.append(response.choices[0].message)
    return response.choices[0].message["content"], response.usage


# f: file
def sum_history(messages, f, model_name="gpt-3.5-turbo"):
    messages_str = ""
    with open(f, "a") as file:
        for message in messages:  # msg: {"role": str, "content": str}
            messages_str += (
                f"""{message["role"]}: {message["content"]}\n"""  # role: content
            )
            file.write(f"{str(message)}\n")

        file.write("### RUN SUMMARIZER ###")
        # close

    summarizer_prompt = f"""
    Summarize the following conversation between an AI assistant and a user, the conversation is delimited by {DELIMITER}.\
    Messages from the user have greater importance while summarizing.\
    Try limiting your summary to {int(LOW_THRES * 3/4)} words.\
    {DELIMITER}\
    {messages_str}
    {DELIMITER}
    """

    messages_summary, usage = get_completion_with_tokens(
        [], summarizer_prompt, model_name
    )

    with open("sums.txt", "w") as file1:
        file1.write(messages_summary)
        # close

    behavior_prompt = f"""
    You are a friendly AI assistant that can hold conversations for a long duration.\
    The summary of the conversation you have so far is delimited with {DELIMITER}.\
    Use the summary to answer questions from the user.\
    {DELIMITER}\
    {messages_summary}\
    {DELIMITER}
    """

    new_messages = [{"role": "system", "content": behavior_prompt}]
    return new_messages, usage


# f: FILE
def handle_new_message(messages, new_message, f, model_name="gpt-3.5-turbo"):
    response, usage = get_completion_with_tokens(messages, new_message, model_name)

    tokens = usage["total_tokens"]
    if usage["total_tokens"] > CONVO_THRESHOLD:
        with open(f, "a") as file:
            file.write(
                f"### Following conversation took {usage['total_tokens']} Tokens ###\n"
            )
            # close

        messages, usage = sum_history(messages, file_name, model_name)
        tokens = usage["total_tokens"]

    return response, messages, tokens


# MAIN
user_in = input("--> ")

file_name = "log.txt"
with open(file_name, "w") as file:
    file.write("New conversation {}".format(datetime.datetime.today))

active_tokens = 0
messages = []
while user_in != "quit":
    if user_in.lower() == "usage":
        print("ACTIVE TOKENS: {}".format(active_tokens))
    else:
        response, messages, active_tokens = handle_new_message(
            messages, user_in, file_name
        )
        print("AI: {}".format(response))
    user_in = input("--> ")

print("EXIT")
