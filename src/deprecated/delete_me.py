from openai import OpenAI

from dotenv import load_dotenv

import os

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI()

for m in client.models.list().data:
    print(m.id)