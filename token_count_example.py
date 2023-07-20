import openai
import os
from prompt_token_count import num_tokens_from_messages
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.environ["OPENAI_API_KEY"]


def get_completion_with_tokens(
    messages, prompt, model_name="gpt-3.5-turbo"
):  # tuple: str, dict: {"prompt_tokens": #, "completion_tokens": #, "total_tokens": #}
    messages.append({"role": "user", "content": prompt})
    response = openai.ChatCompletion.create(
        model=model_name, messages=messages, temperature=0
    )
    messages.append(response.choices[0].message)
    return response.choices[0].message["content"], response.usage


models = [
    "gpt-3.5-turbo-0301",
    "gpt-3.5-turbo-0613",
    "gpt-3.5-turbo",
    "gpt-4-0314",
    "gpt-4-0613",
    "gpt-4",
]

for i, model in enumerate(models):
    print("{}: {}".format(i, model))

user_model = models[int(input("Select model: "))]

messages = []
user_in = input("--> ")
while user_in != "quit":
    response, usage = get_completion_with_tokens(messages, user_in, user_model)
    print("AI: {}".format(response))
    print(
        "\n# {}: {} COUNTED; {} ACTUAL #\n".format(
            user_model,
            num_tokens_from_messages(messages, user_model),
            usage["total_tokens"],
        )
    )
    user_in = input("--> ")

print("EXIT")
