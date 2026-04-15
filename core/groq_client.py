import json
import re

from core import log

PROMPT = (
    "Из текста ниже извлеки отдельные элементы согласно инструкции.\n"
    "Верни ТОЛЬКО JSON массив строк, без пояснений, без markdown.\n"
    "Инструкция: {instruction}\n"
    "Текст: {text}"
)


def _extract_json_list(s):
    # иногда модель заворачивает ответ в текст — выдёргиваем первый [ ... ]
    if not s:
        return None
    m = re.search(r"\[[\s\S]*\]", s)
    if not m:
        return None
    return m.group(0)


def extract(api_key, instruction, text, model="llama-3.3-70b-versatile"):
    from groq import Groq
    client = Groq(api_key=api_key)
    lg = log.get()
    lg.info("ai extract start model=%s instr_len=%d text_len=%d",
            model, len(instruction or ""), len(text or ""))
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT.format(
            instruction=instruction, text=text)}],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r'^```[a-z]*\n?', '', raw).rstrip('`').strip()
    if not raw:
        raise ValueError("AI вернул пустой ответ")

    try:
        res = json.loads(raw)
    except Exception:
        chunk = _extract_json_list(raw)
        if not chunk:
            raise ValueError(f"AI вернул не JSON: {raw[:120]}")
        res = json.loads(chunk)

    if not isinstance(res, list):
        raise ValueError("AI вернул не массив")

    lg.info("ai extract ok items=%d", len(res))
    return res
