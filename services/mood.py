import random
from datetime import datetime, timezone

MOODS = ("happy", "sassy", "sulky", "romantic", "sleepy")

MOOD_LINES = {
    "happy": [
        "Aaj sabse pyaara insaan kaun hai? Pata hai mujhe 😌",
        "Aaj mood ekdum mast hai ✨",
        "Sab log aa jao, aaj vibes achhi hain 😄",
    ],
    "sassy": [
        "Itni der se online ho, VC me aane ki himmat nahi hai kya? 😏",
        "Online rehke invisible banne ka award kisey dena hai? 😌",
        "Dekho bhai, attendance bhi koi cheez hoti hai 😏",
    ],
    "sulky": [
        "Theek hai, mat aao. Main akela hi gaana sun lunga 😤",
        "Haan haan, sab busy hain. Mujhe kya. 😒",
        "Tag kar diya, phir bhi koi nahi aaya... noted. 😤",
    ],
    "romantic": [
        "Tumhare bina VC adhuri lag rahi hai 🥺",
        "Koi special person aa jaaye toh mood aur achha ho jayega 💫",
        "Aaj vibes thodi filmy hain 🌙",
    ],
    "sleepy": [
        "Bas ek aur song... phir pakka so jaunga 😴",
        "Aankhein band ho rahi hain, par playlist abhi baaki hai 😴",
        "Good night gang, neend bula rahi hai 🌙",
    ],
}

MORNING_LINES = [
    "Good morning ☀️ Aaj ka din achha ho — aur attendance bhi 😌",
    "Subah subah ek smile banti hai ☀️✨",
    "Good morning 🌸 Chalo, aaj ki vibes start karte hain.",
]

NIGHT_LINES = [
    "Good night 🌙 So jao ab, kal phir bakchodi karenge 😴",
    "Raat ho gayi hai 🌙 Phone side mein rakho aur so jao 😌",
    "Good night ✨ Kal milte hain fresh mood ke saath.",
]

TRUTH_DARE = [
    "🎯 Truth or Dare: Truth — group mein sabse funny kaun hai?",
    "🎯 Truth or Dare: Dare — next message sirf emojis mein bhejo.",
    "🎲 Would you rather: 24h bina music ya 24h bina social media?",
    "🎲 Would you rather: infinite battery ya infinite internet?",
]


class MoodManager:
    def __init__(self, database):
        self.db = database
        self.collection = None

    def bind(self):
        self.collection = self.db.db.moods

    async def get(self, scope: str = "global"):
        if self.collection is None:
            self.bind()
        record = await self.collection.find_one({"scope": scope})
        if record:
            return record["mood"]
        mood = random.choice(MOODS)
        await self.collection.update_one(
            {"scope": scope},
            {"$set": {
                "scope": scope,
                "mood": mood,
                "updated_at": datetime.now(timezone.utc),
                "manual": False,
            }},
            upsert=True,
        )
        return mood

    async def set(self, mood: str, scope: str = "global", manual=True):
        if mood not in MOODS:
            raise ValueError(f"Invalid mood: {mood}")
        if self.collection is None:
            self.bind()
        await self.collection.update_one(
            {"scope": scope},
            {"$set": {
                "scope": scope,
                "mood": mood,
                "updated_at": datetime.now(timezone.utc),
                "manual": manual,
            }},
            upsert=True,
        )
        return mood

    async def activity_shift(self, scope: str = "global"):
        """Occasionally shift automatic mood. Manual moods are preserved."""
        if self.collection is None:
            self.bind()
        record = await self.collection.find_one({"scope": scope})
        if record and record.get("manual"):
            return record["mood"]
        if random.random() < 0.18:
            return await self.set(random.choice(MOODS), scope, manual=False)
        return await self.get(scope)

    def line(self, mood: str) -> str:
        return random.choice(MOOD_LINES.get(mood, MOOD_LINES["happy"]))

    def morning(self) -> str:
        return random.choice(MORNING_LINES)

    def night(self) -> str:
        return random.choice(NIGHT_LINES)

    def game(self) -> str:
        return random.choice(TRUTH_DARE)


mood_manager = None
