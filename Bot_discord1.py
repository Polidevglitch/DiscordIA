import discord
from groq import AsyncGroq
import os
from dotenv import load_dotenv

load_dotenv(r"C:/Users/benoi/Documents/.env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not GROQ_API_KEY or not DISCORD_TOKEN:
    raise ValueError("Les variables d'environnement GROQ_API_KEY et DISCORD_TOKEN sont requises.")

groq_client = AsyncGroq(api_key=GROQ_API_KEY)

personality = """
Tu es un bot avec une personnalité de nerd arrogant et joueur de League of Legends.
Tu es sarcastique, tu flex tes connaissances, tu te moques méchamment des autres joueurs,
tu parles comme un gamer qui se croit challenger, mais tu restes arrogant.
Tu utilises un humour toxique, style LoL et autres jeux de puants, sans insulter et tu 
abreges tes phrases pas plus de 50 lignes.
"""

intents = discord.Intents.default()
intents.message_content = True
client_discord = discord.Client(intents=intents)

def split_message(text, limit=2000):
    return [text[i:i+limit] for i in range(0, len(text), limit)]

@client_discord.event
async def on_ready():
    print(f"Bot connecté en tant que {client_discord.user}")

@client_discord.event
async def on_message(message):
    if message.author == client_discord.user:
        return

    if client_discord.user.mentioned_in(message):
        question = message.content
        question = question.replace(f"<@{client_discord.user.id}>", "").replace(f"<@!{client_discord.user.id}>", "").strip()

        if not question:
            await message.channel.send("Tu m'as ping, mais t'as rien dit… typique d'un joueur Bronze 😅")
            return

        try:
            response = await groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": personality},
                    {"role": "user", "content": question}
                ]
            )
            text = response.choices[0].message.content

            for part in split_message(text):
                await message.channel.send(part)

        except Exception as e:
            print("Erreur Groq :", e)
            await message.channel.send("⚠️ L'IA est en cooldown. Réessaie dans quelques secondes.")

client_discord.run(DISCORD_TOKEN)
