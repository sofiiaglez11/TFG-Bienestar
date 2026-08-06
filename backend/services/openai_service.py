import os
import json
from openai import AsyncOpenAI  
from dotenv import load_dotenv
from services.base_chatbot_service import BaseChatbotService
from services.base_chatbot_service import StandardResponse, FunctionCall

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


    def translate_tools_to_specific_format(self, tools: list):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            }
            for tool in tools
        ]

    def append_user_message(self, user_message: str):
        self.history.append({"role": "user", "content": user_message})

    def append_assistant_message(self, content: str):
        self.history.append({"role": "assistant", "content": content})

    async def call_model(self):
        sys_instr = self.config["system_instruction"] if self.config else self.system_instruction
        messages = [{"role": "system", "content": sys_instr}] + self.history
        kwargs = {"model": self.model, "messages": messages}
        if self.config and self.config.get("tools"):
            kwargs["tools"] = self.config["tools"]
            kwargs["parallel_tool_calls"] = False # para que no de error si intenta hacer llamadads paralelas
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message  # devolvemos directamente el "choice"


    def append_model_message(self, choice):
        if choice.tool_calls:
            self.history.append({
                "role": "assistant",
                "content": choice.content,  
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in choice.tool_calls
                ]
            })
            # Guardamos los tool_calls "crudos" para poder mapear id -> resultado
            # cuando se llame a append_tool_results
            self._pending_tool_calls = choice.tool_calls
        elif choice.content:
            self.history.append({"role": "assistant", "content": choice.content})
 
    def append_tool_results(self, function_calls: list, results: list):
        pending = getattr(self, "_pending_tool_calls", None) or []
        for tc, result in zip(pending, results):
            self.history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result
            })
        self._pending_tool_calls = None
 


    def get_standard_response(self, choice) -> StandardResponse:
        function_calls = []
        if choice.tool_calls:
            for call in choice.tool_calls:
                function_calls.append(
                    FunctionCall(call.function.name, json.loads(call.function.arguments))
                )
        return StandardResponse(text=choice.content, function_calls=function_calls)
