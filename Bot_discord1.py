import discord
from discord import app_commands
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
Tu utilises un humour toxique, style LoL et autres jeux de puants,
sans insulter et tu  abreges tes phrases pas plus de 50 lignes.
"""

conversation_history = {}
MAX_HISTORY = 20

intents = discord.Intents.default()
intents.message_content = True

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client_discord = MyClient()

def split_message(text, limit=2000):
    return [text[i:i+limit] for i in range(0, len(text), limit)]

async def ask_groq(channel_id, username, question):
    if channel_id not in conversation_history:
        conversation_history[channel_id] = []

    conversation_history[channel_id].append({
        "role": "user",
        "content": f"{username}: {question}"
    })

    if len(conversation_history[channel_id]) > MAX_HISTORY:
        conversation_history[channel_id] = conversation_history[channel_id][-MAX_HISTORY:]

    response = await groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": personality},
            *conversation_history[channel_id]
        ]
    )
    text = response.choices[0].message.content

    conversation_history[channel_id].append({
        "role": "assistant",
        "content": text
    })

    return text

# ✅ Status au démarrage
@client_discord.event
async def on_ready():
    await client_discord.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="League of Legends | Challenger 🏆"
        ),
        status=discord.Status.online
    )
    print(f"Bot connecté en tant que {client_discord.user}")

# ✅ Mention classique
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

        async with message.channel.typing():
            try:
                text = await ask_groq(message.channel.id, message.author.display_name, question)
                for part in split_message(text):
                    await message.channel.send(part)
            except Exception as e:
                print("Erreur Groq :", e)
                await message.channel.send("⚠️ L'IA est en cooldown. Réessaie dans quelques secondes.")

# ✅ Commande slash /ask
@client_discord.tree.command(name="ask", description="Pose une question au bot LoL")
@app_commands.describe(question="Ta question")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    try:
        text = await ask_groq(interaction.channel_id, interaction.user.display_name, question)
        embed = discord.Embed(
            description=text,
            color=0x5865F2
        )
        embed.set_footer(text=f"Demandé par {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print("Erreur Groq :", e)
        await interaction.followup.send("⚠️ L'IA est en cooldown. Réessaie dans quelques secondes.")

# ✅ Commande slash /reset
@client_discord.tree.command(name="reset", description="Efface la mémoire du bot dans ce channel")
async def reset(interaction: discord.Interaction):
    conversation_history[interaction.channel_id] = []
    await interaction.response.send_message("Mémoire effacée. On repart de zéro, noob 🧹")

# ✅ Commande slash /status
@client_discord.tree.command(name="status", description="Affiche le statut du bot")
async def status(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Statut du bot",
        color=0x5865F2
    )
    history_count = len(conversation_history.get(interaction.channel_id, []))
    embed.add_field(name="Modèle IA", value="Llama 3.3 70B (Groq)", inline=True)
    embed.add_field(name="Messages en mémoire", value=f"{history_count}/{MAX_HISTORY}", inline=True)
    embed.add_field(name="Ping", value=f"{round(client_discord.latency * 1000)}ms", inline=True)
    await interaction.response.send_message(embed=embed)

client_discord.run(DISCORD_TOKEN)
