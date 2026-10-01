import logging

import aiohttp

from config import settings
from services.mood import MOODS, MOOD_LINES

logger = logging.getLogger(__name__)

MOOD_INSTRUCTIONS = {
    "happy": "Warm, cheerful, energetic, friendly and inviting. Use light emojis.",
    "sassy": "Playfully teasing and confident. Light roast only; never abusive, hateful, sexual, or humiliating.",
    "sulky": "Cute, mildly dramatic and mock-sulky. Sound disappointed that everyone is quiet, but stay friendly.",
    "romantic": "Soft, cute and mildly flirty PG style. No sexual content and do not target minors.",
    "sleepy": "Sleepy, lazy, cute and short. Sound like you are running out of energy.",
}

SYSTEM_PROMPT = """You generate short Telegram group tagging messages for a userbot.
Return ONLY the message text. Do not include usernames, @mentions, Telegram links, headings,
quotes, explanations, or meta-commentary. Keep it natural and concise, normally 1-3 sentences.
Follow the requested mood. Never include sexual content, harassment, threats, hate, or instructions
to evade Telegram limits. The message will be followed by a generated mention list."""


class GroqMoodGenerator:
    def __init__(self):
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    async def generate(
        self,
        mood: str,
        instruction: str | None = None,
        group_title: str | None = None,
        member_count: int = 0,
    ) -> str:
        mood = mood if mood in MOODS else "happy"
        fallback = MOOD_LINES[mood][0]
        if not settings.groq_api_key:
            return fallback

        user_prompt = (
            f"Mood: {mood}.\n"
            f"Style: {MOOD_INSTRUCTIONS[mood]}\n"
            f"Group: {group_title or 'Telegram group'}\n"
            f"People being invited: {member_count}\n"
            f"Admin's intent/custom instruction: {instruction or 'Invite everyone to come back and participate.'}\n"
            "Write one fresh group message that matches the mood and intent."
        )
        payload = {
            "model": settings.groq_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.9,
            "max_tokens": 120,
        }
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=settings.groq_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        logger.warning("Groq returned HTTP %s", response.status)
                        return fallback
                    data = await response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            content = " ".join(str(content).split()).strip().strip('"')
            if not content:
                return fallback
            return content[:500]
        except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, IndexError) as exc:
            logger.warning("Groq generation failed: %s", exc)
            return fallback


groq_mood = GroqMoodGenerator()
