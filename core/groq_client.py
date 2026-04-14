import json
import re

PROMPT = (
    "Из текста ниже извлеки отдельные элементы согласно инструкции.\n"
    "Верни ТОЛЬКО JSON массив строк, без пояснений, без markdown.\n"
    "Инструкция: {instruction}\n"
    "Текст: {text}"
)


def extract(api_key, instruction, text):
    from groq import Groq
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": PROMPT.format(
            instruction=instruction, text=text)}],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r'^```[a-z]*\n?', '', raw).rstrip('`').strip()
    return json.loads(raw)
