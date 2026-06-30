import os
import json
from openai import AsyncOpenAI  
from dotenv import load_dotenv
from services.base_bot import BaseChatbotService
from services.base_bot import StandardResponse, FunctionCall

load_dotenv()

class OpenAIService(BaseChatbotService):
    def __init__(self):
        super().__init__()
        # self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.client = AsyncOpenAI(
            api_key=os.getenv("NVIDIA_API_KEY"),
            base_url="https://integrate.api.nvidia.com/v1"
        )

        # self.model = "gpt-4o-mini"
        self.model = "meta/llama-3.1-70b-instruct"
        # self.model = "nvidia/nemotron-3-super"

    def set_config(self, config):
        self.config = {
            "tools": self.translate_tools_to_specific_format(config),
            "system_instruction": (
                "Eres una IA experta en bienestar laboral y gestión del tiempo. "
                "Tu objetivo es ayudar al usuario a gestionar su fatiga y mejorar su día. "
                "Tienes acceso a herramientas de Clockify mediante el protocolo MCP para consultar "
                "proyectos, registrar tiempos o ver espacios de trabajo reales. Responde siempre en español."
            )
        }

    def translate_tools_to_specific_format(self, config):
        openai_tools = []
        if hasattr(config, 'tools') and config.tools:
            for tool in config.tools[0].function_declarations:
                openai_tools.append({
                    "type": "function",
                    "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
                })
        return openai_tools

    def append_user_message(self, user_message: str):
        self.history.append({"role": "user", "content": user_message})

    async def call_model(self):
        messages = [{"role": "system", "content": self.config["system_instruction"]}] + self.history
        kwargs = {"model": self.model, "messages": messages}
        if self.config.get("tools"):
            kwargs["tools"] = self.config["tools"]
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message  # devolvemos directamente el "choice"

    def append_model_message(self, choice):
        if choice.content:
            self.history.append({"role": "assistant", "content": choice.content})

    def get_standard_response(self, choice) -> StandardResponse:
        function_calls = []
        if choice.tool_calls:
            for call in choice.tool_calls:
                function_calls.append(
                    FunctionCall(call.function.name, json.loads(call.function.arguments))
                )
        return StandardResponse(text=choice.content, function_calls=function_calls)
