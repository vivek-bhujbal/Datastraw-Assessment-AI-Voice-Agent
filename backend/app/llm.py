from .config import Settings
from .gemini import Gemini, response_text
from .schemas import Outcome


class GeminiLLM:
    def __init__(self, config: Settings):
        self.config = config
        self.client = Gemini(config.gemini_api_key)

    async def stream(self, messages, tools, prompt):
        return self.client.stream({
            "model": self.config.llm_model, "input": messages,
            "system_instruction": prompt, "tools": tools,
            "generation_config": {"max_output_tokens": 1600, "thinking_level": "low", "thinking_summaries": "none"}
        })

    async def summary(self, messages):
        result = await self.client.create({
            "model": self.config.llm_model,
            "system_instruction": "\n".join(item["content"] for item in messages if item["role"] == "system"),
            "input": "\n".join(item["content"] for item in messages if item["role"] == "user"),
            "response_format": {"type": "text", "mime_type": "application/json", "schema": Outcome.model_json_schema()},
            "generation_config": {"max_output_tokens": 2000, "thinking_level": "low"}
        })
        return Outcome.model_validate_json(response_text(result))

    async def close(self):
        await self.client.close()

