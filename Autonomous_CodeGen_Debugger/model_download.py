# Use a pipeline as a high-level helper
from transformers import pipeline

pipe = pipeline("text-generation", model="openai/gpt-oss-20b")
messages = [
    {"role": "user", "content": "Who are you?"},
]
pipe(messages)