from transformers import pipeline

pipe = pipeline(
    "text-generation",
    model="Qwen/Qwen2.5-3B-Instruct",
    device_map="auto",
)

messages = [
    {
        "role": "system",
        "content": """
You are a business analyst.

Classify the statement into one of:
- rule
- claim
- action_item
- ignore

Return JSON only.
""",
    },
    {
        "role": "user",
        "content": """
the petco charge was dog food for baxter lol, used business card by accident
""",
    },
]

result = pipe(
    messages,
    max_new_tokens=50,
)

print(result[0]["generated_text"][-1]["content"])