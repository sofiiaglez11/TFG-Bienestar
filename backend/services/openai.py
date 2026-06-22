import os
from openai import OpenAI
from dotenv import load_dotenv

from services import base_bot

load_dotenv()

# TODO
class OpenAIService(base_bot):
    def __init__(self):
        self.client = OpenAI() # reads the OPENAI_API_KEY from .env automatically
        self.model = "gpt-4o-mini" 

    