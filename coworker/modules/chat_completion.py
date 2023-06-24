import json
import aiohttp

from typing import Optional

from ..decorators.check_key import check_key_decorator
from ..decorators.error_handling import handle_errors_with_retry
from ..modules.logging import Logger


class ChatCompletionModule:
    async def message_chatgpt(self, text: str, model: str, temperature: float, max_tokens: int) -> str:
        pass

class OpenAIChatCompletionModule(ChatCompletionModule): 
    open_ai_key: Optional[str] = None

    def __init__(self, open_ai_key: str) -> None:
        self.open_ai_key = open_ai_key
        self.logger = Logger.get_instance(name="chat_completion_logger")

    @check_key_decorator
    @handle_errors_with_retry()
    async def message_chatgpt(self, messages: str, model: str, temperature=0.1, max_tokens=4000) -> str:
        
        self.logger.log_gpt_prompt(prompt=messages)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.open_ai_key}",
        }

        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens is not None:
            data["max_tokens"] = max_tokens

        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.openai.com/v1/chat/completions", headers=headers, data=json.dumps(data)) as response:
                response.raise_for_status()

                json_response = await response.json()
                self.logger.log_finish_reason(json_response['choices'][0]['finish_reason'])
                self.logger.log_gpt_response(json_response["choices"][0]["message"]["content"])

                return json_response["choices"][0]["message"]["content"]
