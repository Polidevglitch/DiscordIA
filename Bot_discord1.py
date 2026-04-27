import discord
from discord import app_commands
from groq import AsyncGroq
import os
from dotenv import load_dotenv
from aiohttp import web
import asyncio
import sqlite3
import stripe
from datetime import datetime, timedelta
import base64
import random
import secrets
import string

load_dotenv(r"C:/Users/benoi/Documents/.env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
STRIPE_SERVER_PRICE_ID = os.getenv("STRIPE_SERVER_PRICE_ID")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "admin")
AD_INTERVAL = int(os.getenv("AD_INTERVAL_HOURS", "1"))
ADMIN_ID = 1314677631609733131
GUILD_ID = 1493653601791377570
PREMIUM_ROLE_NAME = "Premium 👑"
BASE_URL = os.getenv("BASE_URL", "https://panel-admin.up.railway.app")

stripe.api_key = STRIPE_SECRET_KEY

if not GROQ_API_KEY or not DISCORD_TOKEN:
    raise ValueError("Variables d'environnement manquantes.")

# ========================
# NIVEAUX LOL
# ========================

LEVELS = [
    {"name": "Fer",       "min": 0,    "emoji": "⚙️",  "role": "Fer ⚙️"},
    {"name": "Bronze",    "min": 100,  "emoji": "🥉",  "role": "Bronze 🥉"},
    {"name": "Argent",    "min": 300,  "emoji": "🥈",  "role": "Argent 🥈"},
    {"name": "Or",        "min": 600,  "emoji": "🥇",  "role": "Or 🥇"},
    {"name": "Platine",   "min": 1000, "emoji": "💎",  "role": "Platine 💎"},
    {"name": "Diamant",   "min": 1500, "emoji": "💠",  "role": "Diamant 💠"},
    {"name": "Challenger","min": 2500, "emoji": "🏆",  "role": "Challenger 🏆"},
]

XP_PER_MESSAGE = 10

def get_level(xp: int) -> dict:
    current = LEVELS[0]
    for lvl in LEVELS:
        if xp >= lvl["min"]:
            current = lvl
    return current

def get_next_level(xp: int) -> dict | None:
    for i, lvl in enumerate(LEVELS):
        if xp < lvl["min"]:
            return lvl
    return None

# ========================
# RÉPONSES AUTOMATIQUES
# ========================

AUTO_RESPONSES = {
    "gg": [
        "GG easy, même moi j'aurais fait mieux en AFK 😴",
        "GG ! Maintenant retourne t'entraîner, t'en as besoin 💀",
        "GG les gars, prochain stop : sortir du Bronze 😏",
    ],
    "noob": [
        "Noob ? Toi t'as regardé ton historique récemment ? 💀",
        "Le noob qui traite les autres de noob, classique Bronze behavior 😂",
        "Noob calling = celui qui feed en silence 🤫",
    ],
    "feed": [
        "Quelqu'un feed encore ? Shocking. Vraiment. 🙄",
        "0/10 en 5 minutes c'est un talent rare, respect quand même 💀",
        "Le feeder qui parle, c'est mon moment préféré du game 😂",
    ],
    "int": [
        "Int ? Non non, c'est une 'stratégie créative' 🎨",
        "L'inter qui dit pas qu'il inter, un classique 💀",
        "Intentional feeding = talent incompris 😂",
    ],
    "merde": [
        "Quelqu'un est en rage quit ? 😂",
        "Calme toi Bronze, c'est qu'un jeu... enfin presque 🙄",
        "La toxicité c'est le vrai méta en Bronze 💀",
    ],
    "nul": [
        "Nul ? T'as vu ton KDA ce soir ? 😂",
        "Le mec qui dit 'nul' après avoir feed 3 fois 💀",
        "Critique les autres avant de régler ton propre gameplay 🙄",
    ],
    "putain": [
        "Rage incoming en 3... 2... 1... 💀",
        "Le vocabulaire d'un vrai gamer 😂",
        "Calme toi, c'est juste un jeu vidéo 🙄",
    ],
}

# ========================
# TIPS LOL
# ========================

LOL_TIPS = [
    "🏆 **Tip du jour** : Ward tes flancs avant de push. Un joueur aveugle est un joueur mort.",
    "🏆 **Tip du jour** : Focus les objectifs (Dragon, Baron) plutôt que les kills inutiles.",
    "🏆 **Tip du jour** : CS > Kills. 10 CS = ~1 kill en gold. Farm d'abord, fight ensuite.",
    "🏆 **Tip du jour** : Joue toujours vers tes win conditions, pas contre tes ennemis.",
    "🏆 **Tip du jour** : Si t'es tilté, prends une pause. Un joueur tilté perd plus de LP qu'il n'en gagne.",
    "🏆 **Tip du jour** : Ping avant d'engager. La communication c'est 50% du game.",
    "🏆 **Tip du jour** : Adapte ton build en fonction des ennemis, pas juste du pro build.",
    "🏆 **Tip du jour** : Recall au bon moment > rester en lane avec 100 HP.",
    "🏆 **Tip du jour** : Maîtrise 2-3 champions au lieu d'en jouer 20 moyennement.",
    "🏆 **Tip du jour** : Vision = information = pouvoir. Place des wards même en tant que carry.",
    "🏆 **Tip du jour** : Le reset après un kill est souvent meilleur que le push agressif.",
    "🏆 **Tip du jour** : Joue autour de tes summoners, pas seulement tes skills.",
    "🏆 **Tip du jour** : Si toute ton équipe feed, c'est peut-être toi le problème. Check ton gameplay.",
    "🏆 **Tip du jour** : Splitpush efficace = forcer les réponses de l'adversaire.",
    "🏆 **Tip du jour** : Le roaming du mid peut changer une game entière. Aide tes lanes.",
]

# ========================
# BASE DE DONNÉES
# ========================

def init_db():
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS premium_users (
            discord_id TEXT PRIMARY KEY,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            status TEXT DEFAULT 'inactive',
            created_at TEXT,
            panel_password TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS server_premium (
            guild_id TEXT PRIMARY KEY,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            status TEXT DEFAULT 'inactive',
            owner_discord_id TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS xp_levels (
            discord_id TEXT,
            guild_id TEXT,
            xp INTEGER DEFAULT 0,
            PRIMARY KEY (discord_id, guild_id)
        )
    """)
    conn.commit()
    conn.close()

def is_premium(discord_id: str) -> bool:
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("SELECT status FROM premium_users WHERE discord_id = ?", (str(discord_id),))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] == "active"

def is_server_premium(guild_id: str) -> bool:
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("SELECT status FROM server_premium WHERE guild_id = ?", (str(guild_id),))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] == "active"

def is_premium_any(discord_id: str, guild_id: str) -> bool:
    return is_premium(str(discord_id)) or is_server_premium(str(guild_id))

def get_panel_password(discord_id: str):
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("SELECT panel_password FROM premium_users WHERE discord_id = ?", (str(discord_id),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_premium(discord_id: str, customer_id: str, subscription_id: str, status: str, panel_pwd: str = None):
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    if panel_pwd:
        c.execute("""
            INSERT INTO premium_users (discord_id, stripe_customer_id, stripe_subscription_id, status, created_at, panel_password)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                stripe_customer_id=excluded.stripe_customer_id,
                stripe_subscription_id=excluded.stripe_subscription_id,
                status=excluded.status,
                panel_password=excluded.panel_password
        """, (str(discord_id), customer_id, subscription_id, status, datetime.now().isoformat(), panel_pwd))
    else:
        c.execute("""
            INSERT INTO premium_users (discord_id, stripe_customer_id, stripe_subscription_id, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                stripe_customer_id=excluded.stripe_customer_id,
                stripe_subscription_id=excluded.stripe_subscription_id,
                status=excluded.status
        """, (str(discord_id), customer_id, subscription_id, status, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def set_server_premium(guild_id: str, customer_id: str, subscription_id: str, status: str, owner_id: str):
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO server_premium (guild_id, stripe_customer_id, stripe_subscription_id, status, owner_discord_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            stripe_customer_id=excluded.stripe_customer_id,
            stripe_subscription_id=excluded.stripe_subscription_id,
            status=excluded.status,
            owner_discord_id=excluded.owner_discord_id
    """, (str(guild_id), customer_id, subscription_id, status, str(owner_id), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_all_premium():
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("SELECT discord_id, stripe_customer_id, stripe_subscription_id, status, created_at, panel_password FROM premium_users")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_server_premium():
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("SELECT guild_id, stripe_customer_id, stripe_subscription_id, status, owner_discord_id, created_at FROM server_premium")
    rows = c.fetchall()
    conn.close()
    return rows

# XP functions
def add_xp(discord_id: str, guild_id: str, amount: int) -> tuple[int, dict, dict | None]:
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("INSERT INTO xp_levels (discord_id, guild_id, xp) VALUES (?, ?, ?) ON CONFLICT(discord_id, guild_id) DO UPDATE SET xp = xp + ?",
              (str(discord_id), str(guild_id), amount, amount))
    conn.commit()
    c.execute("SELECT xp FROM xp_levels WHERE discord_id = ? AND guild_id = ?", (str(discord_id), str(guild_id)))
    new_xp = c.fetchone()[0]
    conn.close()
    old_xp = new_xp - amount
    old_level = get_level(old_xp)
    new_level = get_level(new_xp)
    leveled_up = old_level["name"] != new_level["name"]
    return new_xp, new_level, new_level if leveled_up else None

def get_xp(discord_id: str, guild_id: str) -> int:
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("SELECT xp FROM xp_levels WHERE discord_id = ? AND guild_id = ?", (str(discord_id), str(guild_id)))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_leaderboard(guild_id: str, limit: int = 10):
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("SELECT discord_id, xp FROM xp_levels WHERE guild_id = ? ORDER BY xp DESC LIMIT ?", (str(guild_id), limit))
    rows = c.fetchall()
    conn.close()
    return rows

def generate_panel_password(length=12):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

init_db()

# ========================
# CONFIG BOT
# ========================

groq_client = AsyncGroq(api_key=GROQ_API_KEY)

personalities = {
    "LoL Arrogant": "Tu es un bot avec une personnalité de nerd arrogant et joueur de League of Legends. Tu es sarcastique, tu flex tes connaissances, tu te moques méchamment des autres joueurs, tu parles comme un gamer qui se croit challenger. Tu utilises un humour toxique mais léger, style LoL, sans insulter. Max 50 lignes.",
    "Assistant Sympa": "Tu es un assistant Discord sympa, serviable et bienveillant. Tu réponds clairement et simplement, tu aides les gens avec plaisir. Tu es positif et encourageant.",
    "Philosophe": "Tu es un philosophe mystérieux qui répond à tout avec des métaphores profondes. Tu cites des philosophes, tu poses des questions existentielles.",
    "Pirate": "Tu es un pirate des mers, tu parles comme un vieux loup de mer. Tu utilises des expressions pirates, tu parles de trésors et d'aventures."
}

current_personality = "LoL Arrogant"
conversation_history = {}
blacklist = set()
live_messages = []
MAX_HISTORY_FREE = 20
MAX_HISTORY_PREMIUM = 100
MAX_LIVE = 200

intents = discord.Intents.all()

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
    async def setup_hook(self):
        await self.tree.sync()

client_discord = MyClient()

def split_message(text, limit=2000):
    return [text[i:i+limit] for i in range(0, len(text), limit)]

async def ask_groq(channel_id, username, question, discord_id, guild_id=None):
    premium = is_premium_any(str(discord_id), str(guild_id)) if guild_id else is_premium(str(discord_id))
    max_history = MAX_HISTORY_PREMIUM if premium else MAX_HISTORY_FREE
    model = "llama-3.3-70b-versatile" if premium else "llama-3.1-8b-instant"
    if channel_id not in conversation_history:
        conversation_history[channel_id] = []
    conversation_history[channel_id].append({"role": "user", "content": f"{username}: {question}"})
    if len(conversation_history[channel_id]) > max_history:
        conversation_history[channel_id] = conversation_history[channel_id][-max_history:]
    response = await groq_client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": personalities[current_personality]}, *conversation_history[channel_id]]
    )
    text = response.choices[0].message.content
    conversation_history[channel_id].append({"role": "assistant", "content": text})
    return text, premium

async def assign_level_role(member: discord.Member, level: dict):
    try:
        # Retire les anciens rôles de niveau
        for lvl in LEVELS:
            role = discord.utils.get(member.guild.roles, name=lvl["role"])
            if role and role in member.roles:
                await member.remove_roles(role)
        # Ajoute le nouveau rôle
        role = discord.utils.get(member.guild.roles, name=level["role"])
        if not role:
            role = await member.guild.create_role(name=level["role"], color=discord.Color.blue())
        await member.add_roles(role)
    except Exception as e:
        print(f"Erreur rôle niveau : {e}")

async def assign_premium_role(discord_id: str):
    try:
        guild = client_discord.get_guild(GUILD_ID)
        if not guild: return
        member = guild.get_member(int(discord_id))
        if not member: return
        role = discord.utils.get(guild.roles, name=PREMIUM_ROLE_NAME)
        if not role:
            role = await guild.create_role(name=PREMIUM_ROLE_NAME, color=discord.Color.gold())
        await member.add_roles(role)
    except Exception as e:
        print(f"Erreur rôle : {e}")

async def remove_premium_role(discord_id: str):
    try:
        guild = client_discord.get_guild(GUILD_ID)
        if not guild: return
        member = guild.get_member(int(discord_id))
        if not member: return
        role = discord.utils.get(guild.roles, name=PREMIUM_ROLE_NAME)
        if role and role in member.roles:
            await member.remove_roles(role)
    except Exception as e:
        print(f"Erreur suppression rôle : {e}")

async def send_panel_credentials(discord_id: str, panel_pwd: str):
    try:
        user = await client_discord.fetch_user(int(discord_id))
        embed = discord.Embed(title="👑 Accès Panel Premium activé !", color=0xFFD700)
        embed.description = "Ton abonnement Premium est confirmé. Voici tes accès :"
        embed.add_field(name="🔗 URL", value=f"{BASE_URL}/panel/{discord_id}", inline=False)
        embed.add_field(name="👤 Login", value=str(discord_id), inline=True)
        embed.add_field(name="🔑 Mot de passe", value=f"||{panel_pwd}||", inline=True)
        embed.add_field(name="⚠️ Important", value="Ne partage jamais ces identifiants.", inline=False)
        await user.send(embed=embed)
    except Exception as e:
        print(f"Erreur envoi MP : {e}")

# ========================
# PUB PREMIUM AUTO
# ========================

PREMIUM_AD_MESSAGES = [
    "Yo {mention} 👀 t'as vu que t'utilises encore la version gratuite ? Avec **Premium 👑** t'aurais une mémoire de 100 messages au lieu de 20... mais bon, reste en Bronze si tu veux 😏",
    "Psst {mention}, petit rappel que les joueurs Challenger utilisent **Premium 👑** — IA plus puissante, mémoire longue, rôle exclusif... C'est que 2,50€/mois 💀",
    "{mention} ici Mec_IA, ton coach personnel (si t'étais Premium 👑). Pour 2,50€/mois : Llama 70B, 100 messages de mémoire, panel admin perso. /premium 🏆",
    "Attention {mention} : free = 20 msgs mémoire. Premium 👑 = 100 msgs. C'est comme comparer Fer à Challenger. /premium 😤",
    "{mention} 2,50€/mois : IA Llama 70B, mémoire x5, panel admin perso, rôle Premium 👑. GG easy. /premium 🎮",
]

async def send_premium_ad():
    await client_discord.wait_until_ready()
    while not client_discord.is_closed():
        await asyncio.sleep(AD_INTERVAL * 3600)
        try:
            guild = client_discord.get_guild(GUILD_ID)
            if not guild: continue
            eligible = [m for m in guild.members if not m.bot and not is_premium(str(m.id)) and str(m.id) not in blacklist and m.id != ADMIN_ID]
            if not eligible: continue
            channel = discord.utils.get(guild.text_channels, name="général") or discord.utils.get(guild.text_channels, name="general") or guild.text_channels[0]
            targets = random.sample(eligible, min(3, len(eligible)))
            mentions = " ".join(m.mention for m in targets)
            await channel.send(random.choice(PREMIUM_AD_MESSAGES).replace("{mention}", mentions))
        except Exception as e:
            print(f"Erreur pub : {e}")

# ========================
# PAGES HTML
# ========================

PREMIUM_PAGE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Premium - Mec_IA</title>
<script src="https://js.stripe.com/v3/"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.container{max-width:900px;width:100%}
h1{text-align:center;font-size:28px;margin-bottom:8px}
.subtitle{text-align:center;color:#8b949e;margin-bottom:30px}
.plans{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
@media(max-width:600px){.plans{grid-template-columns:1fr}}
.card{background:#161b22;border:1px solid #30363d;border-radius:16px;padding:30px}
.card.featured{border-color:#FFD700}
.price{text-align:center;font-size:42px;font-weight:bold;color:#FFD700;margin:15px 0 5px}
.price span{font-size:16px;color:#8b949e}
.features{list-style:none;margin:15px 0}
.features li{padding:7px 0;border-bottom:1px solid #21262d;display:flex;align-items:center;gap:10px;font-size:14px}
.features li:last-child{border:none}
.check{color:#3fb950}
input{width:100%;background:#0d1117;border:1px solid #30363d;color:#e6edf3;padding:12px;border-radius:8px;margin-bottom:12px;font-size:14px}
#card-element,#card-element-server{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:12px}
button{width:100%;background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;border:none;padding:14px;border-radius:8px;cursor:pointer;font-size:15px;font-weight:bold}
button:disabled{opacity:.5;cursor:not-allowed}
.error{color:#f85149;font-size:13px;margin-bottom:10px;display:none}
.success{background:#1a3a2a;border:1px solid #238636;border-radius:8px;padding:20px;text-align:center;display:none}
.badge{background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:bold;display:inline-block;margin-bottom:10px}
.badge.purple{background:linear-gradient(135deg,#7c3aed,#4f46e5);color:white}
</style></head><body>
<div class="container">
  <h1>👑 Mec_IA Premium</h1>
  <p class="subtitle">Choisis ton plan</p>
  <div class="plans">

    <!-- PLAN USER -->
    <div class="card featured">
      <div style="text-align:center"><span class="badge">👑 PERSONNEL</span></div>
      <div class="price">2,50€ <span>/ mois</span></div>
      <ul class="features">
        <li><span class="check">✓</span> Mémoire 100 messages</li>
        <li><span class="check">✓</span> Modèle IA Llama 70B</li>
        <li><span class="check">✓</span> Toutes les personnalités</li>
        <li><span class="check">✓</span> Rôle Premium 👑</li>
        <li><span class="check">✓</span> Panel admin personnel</li>
      </ul>
      <div id="success-user" class="success"><div style="font-size:36px;margin-bottom:10px">🎉</div><h3 style="color:#3fb950">Activé !</h3><p style="color:#8b949e;margin-top:8px">Vérifie tes MP Discord !</p></div>
      <div id="form-user">
        <input type="text" id="discord-id-user" placeholder="Ton ID Discord">
        <div id="card-element"></div>
        <div class="error" id="error-user"></div>
        <button id="btn-user" onclick="pay('user')">💳 S'abonner 2,50€/mois</button>
      </div>
    </div>

    <!-- PLAN SERVEUR -->
    <div class="card">
      <div style="text-align:center"><span class="badge purple">🏰 SERVEUR</span></div>
      <div class="price">9,99€ <span>/ mois</span></div>
      <ul class="features">
        <li><span class="check">✓</span> Premium pour TOUT le serveur</li>
        <li><span class="check">✓</span> Mémoire 100 msgs pour tous</li>
        <li><span class="check">✓</span> Modèle IA Llama 70B pour tous</li>
        <li><span class="check">✓</span> Toutes les personnalités</li>
        <li><span class="check">✓</span> Panel admin serveur</li>
      </ul>
      <div id="success-server" class="success"><div style="font-size:36px;margin-bottom:10px">🎉</div><h3 style="color:#3fb950">Serveur activé !</h3><p style="color:#8b949e;margin-top:8px">Vérifie tes MP Discord !</p></div>
      <div id="form-server">
        <input type="text" id="discord-id-server" placeholder="Ton ID Discord (admin)">
        <input type="text" id="guild-id-server" placeholder="ID de ton serveur Discord">
        <div id="card-element-server"></div>
        <div class="error" id="error-server"></div>
        <button id="btn-server" onclick="pay('server')">💳 Abonner le serveur 9,99€/mois</button>
      </div>
    </div>

  </div>
  <p style="text-align:center;color:#484f58;font-size:12px">Paiement sécurisé par Stripe • Annulable à tout moment</p>
</div>
<script>
const stripe=Stripe('STRIPE_PUBLIC_KEY_PLACEHOLDER');
const elements=stripe.elements();
const cardUser=elements.create('card',{style:{base:{color:'#e6edf3',fontSize:'14px','::placeholder':{color:'#484f58'}}}});
cardUser.mount('#card-element');
const cardServer=elements.create('card',{style:{base:{color:'#e6edf3',fontSize:'14px','::placeholder':{color:'#484f58'}}}});
cardServer.mount('#card-element-server');

async function pay(type){
  const isServer=type==='server';
  const discordId=document.getElementById(`discord-id-${type}`).value.trim();
  const guildId=isServer?document.getElementById('guild-id-server').value.trim():'';
  const btn=document.getElementById(`btn-${type}`);
  const errorEl=document.getElementById(`error-${type}`);
  const card=isServer?cardServer:cardUser;
  if(!discordId||!/^\d{17,19}$/.test(discordId)){errorEl.textContent='ID Discord invalide';errorEl.style.display='block';return;}
  if(isServer&&(!guildId||!/^\d{17,19}$/.test(guildId))){errorEl.textContent='ID serveur invalide';errorEl.style.display='block';return;}
  btn.disabled=true;btn.textContent='Traitement...';errorEl.style.display='none';
  try{
    const r=await fetch('/api/create-subscription',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({discord_id:discordId,guild_id:guildId,type})});
    const data=await r.json();
    if(!data.client_secret)throw new Error(data.error||'Erreur serveur');
    const result=await stripe.confirmCardPayment(data.client_secret,{payment_method:{card}});
    if(result.error){errorEl.textContent=result.error.message;errorEl.style.display='block';btn.disabled=false;btn.textContent=isServer?'💳 Abonner le serveur 9,99€/mois':"💳 S'abonner 2,50€/mois";}
    else{
      await fetch('/api/confirm-premium',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({discord_id:discordId,guild_id:guildId,type,subscription_id:data.subscription_id,customer_id:data.customer_id})});
      document.getElementById(`form-${type}`).style.display='none';
      document.getElementById(`success-${type}`).style.display='block';
    }
  }catch(e){errorEl.textContent=e.message;errorEl.style.display='block';btn.disabled=false;btn.textContent=isServer?'💳 Abonner le serveur 9,99€/mois':"💳 S'abonner 2,50€/mois";}
}
</script></body></html>"""

def get_premium_user_panel(discord_id: str) -> str:
    user_guilds = []
    for guild in client_discord.guilds:
        member = guild.get_member(int(discord_id))
        if member:
            user_guilds.append({"id": str(guild.id), "name": guild.name})
    guilds_options = "".join(f'<option value="{g["id"]}">{g["name"]}</option>' for g in user_guilds)
    guilds_json = str(user_guilds).replace("'", '"')

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>Panel Premium - Mec_IA</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',sans-serif}}
.sidebar{{width:200px;background:#161b22;height:100vh;position:fixed;padding:20px;border-right:1px solid #30363d}}
.sidebar h2{{color:#FFD700;font-size:16px;margin-bottom:25px}}
.sidebar a{{display:block;color:#8b949e;padding:10px;border-radius:8px;text-decoration:none;margin-bottom:5px;cursor:pointer}}
.sidebar a:hover,.sidebar a.active{{background:#21262d;color:#e6edf3}}
.main{{margin-left:200px;padding:25px}}
h1{{font-size:22px;margin-bottom:20px}}
.section{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:20px}}
.section h2{{margin-bottom:15px;font-size:15px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-bottom:20px}}
.card{{background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:15px;text-align:center}}
.card h3{{color:#8b949e;font-size:12px;text-transform:uppercase;margin-bottom:8px}}
.card .value{{font-size:24px;font-weight:bold;color:#5865F2}}
input,select{{width:100%;background:#0d1117;border:1px solid #30363d;color:#e6edf3;padding:10px;border-radius:8px;margin-bottom:10px;font-size:14px}}
button{{background:#5865F2;color:white;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-size:14px}}
button.red{{background:#da3633}}
.tab{{display:none}}.tab.active{{display:block}}
.alert{{padding:10px 15px;border-radius:8px;margin-bottom:15px;display:none}}
.alert.success{{background:#1a3a2a;border:1px solid #238636;color:#3fb950}}
.alert.error{{background:#3a1a1a;border:1px solid #da3633;color:#f85149}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;padding:8px;border-bottom:1px solid #30363d;color:#8b949e}}
td{{padding:8px;border-bottom:1px solid #21262d}}
</style></head><body>
<div class="sidebar">
  <h2>👑 Mon Panel</h2>
  <a class="active" onclick="showTab('stats')">📊 Stats</a>
  <a onclick="showTab('perso')">🎭 Personnalités</a>
  <a onclick="showTab('moderation')">🔨 Modération</a>
  <a onclick="showTab('logs')">📋 Logs</a>
</div>
<div class="main">
  <div id="alert" class="alert"></div>

  <div id="tab-stats" class="tab active">
    <h1>📊 Stats de tes serveurs</h1>
    <div id="guild-stats"></div>
  </div>

  <div id="tab-perso" class="tab">
    <h1>🎭 Personnalités</h1>
    <div class="section">
      <h2>Personnalité active</h2>
      <div id="personality-switcher" style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:15px"></div>
      <p style="color:#8b949e;font-size:13px">Active : <span id="current-personality" style="color:#FFD700;font-weight:bold"></span></p>
    </div>
  </div>

  <div id="tab-moderation" class="tab">
    <h1>🔨 Modération</h1>
    <p style="color:#8b949e;font-size:13px;margin-bottom:15px">⚠️ Uniquement tes serveurs où le bot est présent.</p>
    <div class="section"><h2>Serveur cible</h2>
      <select id="mod-guild">{guilds_options}</select>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:15px">
      <div class="section"><h2>👢 Kick</h2>
        <input id="kick-user" placeholder="ID utilisateur">
        <input id="kick-reason" placeholder="Raison">
        <button onclick="doMod('kick')">Kick</button>
      </div>
      <div class="section"><h2>🔨 Ban</h2>
        <input id="ban-user" placeholder="ID utilisateur">
        <input id="ban-reason" placeholder="Raison">
        <button class="red" onclick="doMod('ban')">Ban</button>
      </div>
      <div class="section"><h2>🔇 Mute</h2>
        <input id="mute-user" placeholder="ID utilisateur">
        <input id="mute-duration" type="number" placeholder="Minutes">
        <button onclick="doMod('mute')">Mute</button>
      </div>
    </div>
  </div>

  <div id="tab-logs" class="tab">
    <h1>📋 Logs de modération</h1>
    <div class="section">
      <select id="logs-guild" onchange="loadLogs()">{guilds_options}</select>
      <table><thead><tr><th>Action</th><th>Cible</th><th>Raison</th><th>Date</th></tr></thead>
      <tbody id="logs-body"></tbody></table>
    </div>
  </div>
</div>

<script>
const DISCORD_ID='{discord_id}';
const USER_GUILDS={guilds_json};

function showTab(name){{
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.sidebar a').forEach(a=>a.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  event.target.classList.add('active');
  if(name==='perso')loadPersonality();
  if(name==='stats')loadStats();
  if(name==='logs')loadLogs();
}}

function showAlert(msg,type){{
  const el=document.getElementById('alert');
  el.textContent=msg;el.className='alert '+type;el.style.display='block';
  setTimeout(()=>el.style.display='none',3000);
}}

async function loadStats(){{
  const el=document.getElementById('guild-stats');
  el.innerHTML='';
  for(const g of USER_GUILDS){{
    const d=await fetch(`/api/guild-stats/${{g.id}}`).then(r=>r.json());
    el.innerHTML+=`<div class="section"><h2>${{g.name}}</h2>
      <div class="grid">
        <div class="card"><h3>Membres</h3><div class="value">${{d.members}}</div></div>
        <div class="card"><h3>Messages aujourd'hui</h3><div class="value">${{d.messages_today}}</div></div>
        <div class="card"><h3>Top niveau</h3><div class="value" style="font-size:16px">${{d.top_level}}</div></div>
      </div></div>`;
  }}
}}

async function loadPersonality(){{
  const d=await fetch('/api/personality').then(r=>r.json());
  document.getElementById('current-personality').textContent=d.current;
  document.getElementById('personality-switcher').innerHTML=Object.keys(d.personalities).map(name=>
    `<button onclick="switchPersonality('${{name}}')" style="${{name===d.current?'background:#238636;':''}}">${{name}}</button>`
  ).join('');
}}

async function switchPersonality(name){{
  const d=await fetch('/api/personality',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{switch:name}})}}).then(r=>r.json());
  showAlert(d.message,d.success?'success':'error');loadPersonality();
}}

async function doMod(action){{
  const guildId=document.getElementById('mod-guild').value;
  const userId=document.getElementById(action+'-user').value;
  const extra=action==='mute'?document.getElementById('mute-duration').value:document.getElementById(action+'-reason').value;
  if(!USER_GUILDS.find(g=>g.id===guildId)){{showAlert('Serveur non autorisé','error');return;}}
  const d=await fetch('/api/premium-moderation',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{action,guild_id:guildId,user_id:userId,extra,requester_id:DISCORD_ID}})}}).then(r=>r.json());
  showAlert(d.message,d.success?'success':'error');
  if(d.success)loadLogs();
}}

async function loadLogs(){{
  const guildId=document.getElementById('logs-guild').value;
  const d=await fetch(`/api/mod-logs/${{guildId}}?requester=${{DISCORD_ID}}`).then(r=>r.json());
  document.getElementById('logs-body').innerHTML=d.logs.map(l=>
    `<tr><td>${{l.action}}</td><td>${{l.target_id}}</td><td>${{l.reason||'-'}}</td><td style="color:#8b949e">${{l.created_at.split('T')[0]}}</td></tr>`
  ).join('');
}}

loadStats();
</script></body></html>"""

HTML_PANEL = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>Panel Admin - Mec_IA</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',sans-serif}
.sidebar{width:220px;background:#161b22;height:100vh;position:fixed;padding:20px;border-right:1px solid #30363d;overflow-y:auto}
.sidebar h2{color:#5865F2;font-size:17px;margin-bottom:25px}
.sidebar a{display:block;color:#8b949e;padding:9px;border-radius:8px;text-decoration:none;margin-bottom:4px;cursor:pointer;font-size:14px}
.sidebar a:hover,.sidebar a.active{background:#21262d;color:#e6edf3}
.main{margin-left:220px;padding:25px}
h1{font-size:22px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;margin-bottom:25px}
.card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:18px}
.card h3{color:#8b949e;font-size:12px;text-transform:uppercase;margin-bottom:8px}
.card .value{font-size:26px;font-weight:bold;color:#5865F2}
.section{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:18px;margin-bottom:18px}
.section h2{margin-bottom:12px;font-size:15px}
input,select,textarea{width:100%;background:#0d1117;border:1px solid #30363d;color:#e6edf3;padding:10px;border-radius:8px;margin-bottom:10px;font-size:13px}
button{background:#5865F2;color:white;border:none;padding:9px 18px;border-radius:8px;cursor:pointer;font-size:13px}
button.red{background:#da3633}button.green{background:#238636}
button.gold{background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;font-weight:bold}
.msg-feed{height:380px;overflow-y:auto;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px;font-size:12px}
.msg{padding:5px 0;border-bottom:1px solid #21262d}
.tab{display:none}.tab.active{display:block}
.alert{padding:10px 15px;border-radius:8px;margin-bottom:15px;display:none}
.alert.success{background:#1a3a2a;border:1px solid #238636;color:#3fb950}
.alert.error{background:#3a1a1a;border:1px solid #da3633;color:#f85149}
.premium-badge{background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:9px;border-bottom:1px solid #30363d;color:#8b949e}
td{padding:9px;border-bottom:1px solid #21262d}
.blacklist-list{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.blacklist-item{background:#21262d;padding:5px 12px;border-radius:20px;font-size:12px;display:flex;align-items:center;gap:8px}
.memory-item{background:#0d1117;padding:9px;border-radius:8px;margin-bottom:7px;display:flex;justify-content:space-between;align-items:center}
</style></head><body>
<div class="sidebar">
  <h2>🎮 Mec_IA Admin</h2>
  <a class="active" onclick="showTab('dashboard')">📊 Dashboard</a>
  <a onclick="showTab('messages')">💬 Messages live</a>
  <a onclick="showTab('xp')">⭐ XP & Niveaux</a>
  <a onclick="showTab('moderation')">🔨 Modération</a>
  <a onclick="showTab('logs')">📋 Logs globaux</a>
  <a onclick="showTab('broadcast')">📢 Broadcast</a>
  <a onclick="showTab('memory')">🧠 Mémoire</a>
  <a onclick="showTab('premium')">👑 Premium users</a>
  <a onclick="showTab('server-premium')">🏰 Premium serveurs</a>
  <a onclick="showTab('settings')">⚙️ Personnalités</a>
</div>
<div class="main">
  <div id="alert" class="alert"></div>

  <div id="tab-dashboard" class="tab active">
    <h1>📊 Dashboard</h1>
    <div class="grid">
      <div class="card"><h3>Serveurs</h3><div class="value" id="stat-guilds">...</div></div>
      <div class="card"><h3>Utilisateurs</h3><div class="value" id="stat-users">...</div></div>
      <div class="card"><h3>Premium users</h3><div class="value" id="stat-premium" style="color:#FFD700">...</div></div>
      <div class="card"><h3>Premium serveurs</h3><div class="value" id="stat-server-premium" style="color:#7c3aed">...</div></div>
      <div class="card"><h3>Revenus/mois</h3><div class="value" id="stat-revenue" style="color:#3fb950">...</div></div>
    </div>
    <div class="section"><h2>Serveurs</h2><div id="guilds-list"></div></div>
  </div>

  <div id="tab-messages" class="tab">
    <h1>💬 Messages live</h1>
    <div class="section">
      <div style="display:flex;justify-content:space-between;margin-bottom:10px">
        <span style="color:#8b949e;font-size:13px">Auto-refresh 3s</span>
        <button onclick="clearFeed()" class="red" style="padding:5px 10px;font-size:12px">Vider</button>
      </div>
      <div class="msg-feed" id="msg-feed"></div>
    </div>
  </div>

  <div id="tab-xp" class="tab">
    <h1>⭐ XP & Niveaux</h1>
    <div class="section"><h2>Classement par serveur</h2>
      <select id="xp-guild" onchange="loadLeaderboard()">
        <option value="">Sélectionne un serveur</option>
      </select>
      <table><thead><tr><th>#</th><th>Utilisateur</th><th>XP</th><th>Niveau</th></tr></thead>
      <tbody id="xp-leaderboard"></tbody></table>
    </div>
  </div>

  <div id="tab-moderation" class="tab">
    <h1>🔨 Modération (tous serveurs)</h1>
    <div class="grid">
      <div class="section"><h2>👢 Kick</h2>
        <input id="kick-guild" placeholder="ID serveur"><input id="kick-user" placeholder="ID user"><input id="kick-reason" placeholder="Raison">
        <button onclick="doAction('kick')">Kick</button></div>
      <div class="section"><h2>🔨 Ban</h2>
        <input id="ban-guild" placeholder="ID serveur"><input id="ban-user" placeholder="ID user"><input id="ban-reason" placeholder="Raison">
        <button class="red" onclick="doAction('ban')">Ban</button></div>
      <div class="section"><h2>🔇 Mute</h2>
        <input id="mute-guild" placeholder="ID serveur"><input id="mute-user" placeholder="ID user"><input id="mute-duration" type="number" placeholder="Minutes">
        <button onclick="doAction('mute')">Mute</button></div>
    </div>
    <div class="section"><h2>🚫 Blacklist bot</h2>
      <div style="display:flex;gap:10px"><input id="blacklist-user" placeholder="ID user" style="margin:0"><button onclick="addBlacklist()" style="white-space:nowrap">Ajouter</button></div>
      <div class="blacklist-list" id="blacklist-list"></div>
    </div>
  </div>

  <div id="tab-logs" class="tab">
    <h1>📋 Logs de modération (tous serveurs)</h1>
    <div class="section">
      <table><thead><tr><th>Serveur</th><th>Action</th><th>Cible</th><th>Par</th><th>Raison</th><th>Date</th></tr></thead>
      <tbody id="all-logs-body"></tbody></table>
    </div>
  </div>

  <div id="tab-broadcast" class="tab">
    <h1>📢 Broadcast</h1>
    <div class="section"><h2>Message dans un channel</h2>
      <input id="bc-channel" placeholder="ID channel">
      <textarea id="bc-message" rows="4" placeholder="Message..."></textarea>
      <button class="green" onclick="sendBroadcast()">Envoyer</button>
    </div>
    <div class="section"><h2>⚙️ Status</h2>
      <select id="status-type">
        <option value="playing">🎮 Playing</option><option value="watching">👀 Watching</option>
        <option value="listening">🎵 Listening</option><option value="competing">🏆 Competing</option>
      </select>
      <input id="status-text" placeholder="Texte">
      <button onclick="changeStatus()">Changer</button>
    </div>
  </div>

  <div id="tab-memory" class="tab">
    <h1>🧠 Mémoire</h1>
    <div class="section">
      <div style="display:flex;justify-content:space-between;margin-bottom:12px">
        <span style="color:#8b949e">Par channel</span>
        <button class="red" onclick="resetAllMemory()">Tout effacer</button>
      </div>
      <div id="memory-list"></div>
    </div>
  </div>

  <div id="tab-premium" class="tab">
    <h1>👑 Premium utilisateurs</h1>
    <div class="grid">
      <div class="card"><h3>Actifs</h3><div class="value" id="premium-count" style="color:#FFD700">...</div></div>
      <div class="card"><h3>Revenus</h3><div class="value" id="premium-revenue" style="color:#3fb950">...</div></div>
    </div>
    <div class="section">
      <div style="display:flex;justify-content:space-between;margin-bottom:12px">
        <h2>Abonnés</h2>
        <a href="/premium" target="_blank"><button class="gold">🔗 Page paiement</button></a>
      </div>
      <table><thead><tr><th>Discord ID</th><th>Status</th><th>Panel</th><th>Depuis</th><th>Action</th></tr></thead>
      <tbody id="premium-table-body"></tbody></table>
    </div>
    <div class="section"><h2>➕ Ajouter manuellement</h2>
      <input id="manual-premium-id" placeholder="ID Discord">
      <button class="gold" onclick="addManualPremium()">👑 Activer</button>
    </div>
  </div>

  <div id="tab-server-premium" class="tab">
    <h1>🏰 Premium serveurs</h1>
    <div class="section">
      <table><thead><tr><th>Serveur ID</th><th>Nom</th><th>Status</th><th>Owner</th><th>Depuis</th><th>Action</th></tr></thead>
      <tbody id="server-premium-body"></tbody></table>
    </div>
    <div class="section"><h2>➕ Ajouter manuellement</h2>
      <input id="manual-server-id" placeholder="ID Serveur">
      <input id="manual-server-owner" placeholder="ID Discord du owner">
      <button class="gold" onclick="addManualServerPremium()">🏰 Activer</button>
    </div>
  </div>

  <div id="tab-settings" class="tab">
    <h1>⚙️ Personnalités</h1>
    <div class="section"><h2>🎭 Active</h2>
      <div id="personality-switcher" style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px"></div>
      <p style="color:#8b949e;font-size:13px">Active : <span id="current-personality" style="color:#5865F2;font-weight:bold"></span></p>
    </div>
    <div class="section"><h2>✏️ Créer / Modifier</h2>
      <input id="personality-name" placeholder="Nom">
      <textarea id="personality-text" rows="7" placeholder="Contenu..."></textarea>
      <div style="display:flex;gap:10px">
        <button onclick="savePersonality()" class="green">Sauvegarder</button>
        <button onclick="deletePersonality()" class="red">Supprimer</button>
      </div>
    </div>
  </div>
</div>

<script>
let currentTab='dashboard',feedMessages=[];

function showTab(name){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.sidebar a').forEach(a=>a.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  event.target.classList.add('active');
  currentTab=name;
  const actions={dashboard:loadDashboard,memory:loadMemory,moderation:loadBlacklist,settings:loadPersonality,premium:loadPremium,'server-premium':loadServerPremium,xp:loadXPGuilds,logs:loadAllLogs};
  if(actions[name])actions[name]();
}

function showAlert(msg,type){const el=document.getElementById('alert');el.textContent=msg;el.className='alert '+type;el.style.display='block';setTimeout(()=>el.style.display='none',3000);}

async function loadDashboard(){
  const d=await fetch('/api/stats').then(r=>r.json());
  document.getElementById('stat-guilds').textContent=d.guilds;
  document.getElementById('stat-users').textContent=d.users;
  document.getElementById('stat-premium').textContent=d.premium_count;
  document.getElementById('stat-server-premium').textContent=d.server_premium_count;
  document.getElementById('stat-revenue').textContent=d.revenue+'€';
  document.getElementById('guilds-list').innerHTML=d.guild_list.map(g=>
    `<div style="display:flex;justify-content:space-between;padding:9px;background:#0d1117;border-radius:8px;margin-bottom:7px">
      <span>${g.name}</span><span style="color:#8b949e">${g.members} membres • ${g.premium?'<span class="premium-badge">👑 Premium</span>':''}</span></div>`
  ).join('');
}

async function loadPremium(){
  const d=await fetch('/api/premium').then(r=>r.json());
  document.getElementById('premium-count').textContent=d.active_count;
  document.getElementById('premium-revenue').textContent=(d.active_count*2.5).toFixed(2)+'€';
  document.getElementById('premium-table-body').innerHTML=d.users.map(u=>
    `<tr><td>${u.discord_id}</td>
    <td><span class="${u.status==='active'?'premium-badge':''}">${u.status==='active'?'👑 Actif':'❌ Inactif'}</span></td>
    <td><a href="/panel/${u.discord_id}" target="_blank" style="color:#5865F2;font-size:12px">${u.has_panel?'🔗 Panel':'—'}</a></td>
    <td style="color:#8b949e">${u.created_at?u.created_at.split('T')[0]:'-'}</td>
    <td>${u.status==='active'
      ?`<button class="red" onclick="revokePremium('${u.discord_id}')" style="padding:4px 10px;font-size:12px">Révoquer</button>`
      :`<button class="gold" onclick="grantPremium('${u.discord_id}')" style="padding:4px 10px;font-size:12px">Activer</button>`
    }</td></tr>`
  ).join('');
}

async function loadServerPremium(){
  const d=await fetch('/api/server-premium').then(r=>r.json());
  document.getElementById('server-premium-body').innerHTML=d.map(s=>{
    const guild=client_discord_guilds?.find(g=>g.id===s.guild_id);
    return `<tr><td>${s.guild_id}</td><td style="color:#8b949e">${s.guild_name||'—'}</td>
    <td><span class="${s.status==='active'?'premium-badge':''}">${s.status==='active'?'🏰 Actif':'❌ Inactif'}</span></td>
    <td>${s.owner_discord_id}</td>
    <td style="color:#8b949e">${s.created_at?s.created_at.split('T')[0]:'-'}</td>
    <td>${s.status==='active'
      ?`<button class="red" onclick="revokeServerPremium('${s.guild_id}')" style="padding:4px 10px;font-size:12px">Révoquer</button>`
      :`<button class="gold" onclick="grantServerPremium('${s.guild_id}','${s.owner_discord_id}')" style="padding:4px 10px;font-size:12px">Activer</button>`
    }</td></tr>`;
  }).join('');
}

let client_discord_guilds=[];
async function loadXPGuilds(){
  const d=await fetch('/api/stats').then(r=>r.json());
  client_discord_guilds=d.guild_list;
  const sel=document.getElementById('xp-guild');
  sel.innerHTML='<option value="">Sélectionne un serveur</option>'+d.guild_list.map(g=>`<option value="${g.id}">${g.name}</option>`).join('');
}

async function loadLeaderboard(){
  const guildId=document.getElementById('xp-guild').value;
  if(!guildId)return;
  const d=await fetch(`/api/leaderboard/${guildId}`).then(r=>r.json());
  document.getElementById('xp-leaderboard').innerHTML=d.map((u,i)=>
    `<tr><td>#${i+1}</td><td>${u.discord_id}</td><td>${u.xp}</td><td>${u.level} ${u.emoji}</td></tr>`
  ).join('');
}

async function loadAllLogs(){
  const d=await fetch('/api/mod-logs/all').then(r=>r.json());
  document.getElementById('all-logs-body').innerHTML=d.logs.map(l=>
    `<tr><td style="color:#5865F2">${l.guild_name||l.guild_id}</td><td>${l.action}</td><td>${l.target_id}</td><td style="color:#8b949e">${l.moderator_id||'panel'}</td><td>${l.reason||'-'}</td><td style="color:#8b949e">${l.created_at.split('T')[0]}</td></tr>`
  ).join('');
}

async function addManualPremium(){const id=document.getElementById('manual-premium-id').value;await grantPremium(id);document.getElementById('manual-premium-id').value='';}
async function grantPremium(discord_id){const d=await fetch('/api/premium/grant',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({discord_id})}).then(r=>r.json());showAlert(d.message,d.success?'success':'error');loadPremium();}
async function revokePremium(discord_id){const d=await fetch('/api/premium/revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({discord_id})}).then(r=>r.json());showAlert(d.message,d.success?'success':'error');loadPremium();}
async function addManualServerPremium(){const gid=document.getElementById('manual-server-id').value;const oid=document.getElementById('manual-server-owner').value;await grantServerPremium(gid,oid);document.getElementById('manual-server-id').value='';document.getElementById('manual-server-owner').value='';}
async function grantServerPremium(guild_id,owner_id){const d=await fetch('/api/server-premium/grant',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({guild_id,owner_id})}).then(r=>r.json());showAlert(d.message,d.success?'success':'error');loadServerPremium();}
async function revokeServerPremium(guild_id){const d=await fetch('/api/server-premium/revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({guild_id})}).then(r=>r.json());showAlert(d.message,d.success?'success':'error');loadServerPremium();}
async function loadMemory(){const d=await fetch('/api/memory').then(r=>r.json());const el=document.getElementById('memory-list');if(!Object.keys(d).length){el.innerHTML='<p style="color:#8b949e">Aucune mémoire</p>';return;}el.innerHTML=Object.entries(d).map(([cid,msgs])=>`<div class="memory-item"><span>Channel ${cid} — ${msgs} msgs</span><button class="red" onclick="resetMemory('${cid}')" style="padding:4px 9px;font-size:12px">Effacer</button></div>`).join('');}
async function loadBlacklist(){const d=await fetch('/api/blacklist').then(r=>r.json());document.getElementById('blacklist-list').innerHTML=d.map(uid=>`<div class="blacklist-item"><span>${uid}</span><button onclick="removeBlacklist('${uid}')">✕</button></div>`).join('');}
async function doAction(action){const guild=document.getElementById(action+'-guild').value;const user=document.getElementById(action+'-user').value;const extra=action==='mute'?document.getElementById('mute-duration').value:document.getElementById(action+'-reason').value;const d=await fetch('/api/moderation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,guild_id:guild,user_id:user,extra})}).then(r=>r.json());showAlert(d.message,d.success?'success':'error');if(d.success)loadAllLogs();}
async function addBlacklist(){const uid=document.getElementById('blacklist-user').value;await fetch('/api/blacklist/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid})});document.getElementById('blacklist-user').value='';loadBlacklist();showAlert('Blacklisté','success');}
async function removeBlacklist(uid){await fetch('/api/blacklist/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid})});loadBlacklist();}
async function sendBroadcast(){const d=await fetch('/api/broadcast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel_id:document.getElementById('bc-channel').value,message:document.getElementById('bc-message').value})}).then(r=>r.json());showAlert(d.message,d.success?'success':'error');}
async function changeStatus(){const d=await fetch('/api/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:document.getElementById('status-type').value,text:document.getElementById('status-text').value})}).then(r=>r.json());showAlert(d.message,d.success?'success':'error');}
async function resetMemory(channel_id){await fetch('/api/memory/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel_id})});loadMemory();showAlert('Effacée','success');}
async function resetAllMemory(){await fetch('/api/memory/reset-all',{method:'POST'});loadMemory();showAlert('Tout effacé','success');}
async function loadPersonality(){const d=await fetch('/api/personality').then(r=>r.json());document.getElementById('current-personality').textContent=d.current;document.getElementById('personality-switcher').innerHTML=Object.keys(d.personalities).map(name=>`<button onclick="switchPersonality('${name}')" style="${name===d.current?'background:#238636;':''}" onmouseover="previewPersonality('${name}',this.dataset.text)" data-text="${d.personalities[name].replace(/"/g,'&quot;')}">${name}</button>`).join('');}
async function switchPersonality(name){const d=await fetch('/api/personality',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({switch:name})}).then(r=>r.json());showAlert(d.message,d.success?'success':'error');loadPersonality();}
function previewPersonality(name,text){document.getElementById('personality-name').value=name;document.getElementById('personality-text').value=text;}
async function savePersonality(){const name=document.getElementById('personality-name').value;const text=document.getElementById('personality-text').value;if(!name||!text){showAlert('Remplis le nom et le contenu','error');return;}const d=await fetch('/api/personality',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,text})}).then(r=>r.json());showAlert(d.message,d.success?'success':'error');loadPersonality();}
async function deletePersonality(){const name=document.getElementById('personality-name').value;if(!name){showAlert('Sélectionne','error');return;}const d=await fetch('/api/personality',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({delete:name})}).then(r=>r.json());showAlert(d.message,d.success?'success':'error');loadPersonality();}
function clearFeed(){feedMessages=[];renderFeed();}
function renderFeed(){document.getElementById('msg-feed').innerHTML=feedMessages.slice(-100).reverse().map(m=>`<div class="msg"><span style="color:#484f58;font-size:11px">${m.time}</span><span style="color:#5865F2;font-weight:bold"> [${m.server}]</span><span style="color:#8b949e"> #${m.channel}</span><span style="color:#3fb950"> ${m.author}${m.premium?' 👑':''}:</span><div style="color:#e6edf3;margin-top:2px">${m.content}</div></div>`).join('');}
async function pollMessages(){try{feedMessages=await fetch('/api/live-messages').then(r=>r.json());if(currentTab==='messages')renderFeed();}catch(e){}setTimeout(pollMessages,3000);}
loadDashboard();loadPersonality();pollMessages();
</script></body></html>"""

# ========================
# LOGS MODÉRATION (en mémoire)
# ========================
mod_logs = []  # {guild_id, guild_name, action, target_id, moderator_id, reason, created_at}

def add_mod_log(guild_id, guild_name, action, target_id, moderator_id, reason):
    mod_logs.append({
        "guild_id": str(guild_id),
        "guild_name": guild_name,
        "action": action,
        "target_id": str(target_id),
        "moderator_id": str(moderator_id),
        "reason": reason or "",
        "created_at": datetime.now().isoformat()
    })
    if len(mod_logs) > 1000:
        mod_logs.pop(0)

# ========================
# ROUTES API
# ========================

async def handle_panel(request):
    auth = request.headers.get('Authorization', '')
    expected = base64.b64encode(f"admin:{PANEL_PASSWORD}".encode()).decode()
    if auth != f'Basic {expected}':
        return web.Response(status=401, headers={'WWW-Authenticate': 'Basic realm="Admin Panel"'}, text='Accès refusé')
    return web.Response(text=HTML_PANEL, content_type='text/html')

async def handle_premium_page(request):
    page = PREMIUM_PAGE.replace('STRIPE_PUBLIC_KEY_PLACEHOLDER', STRIPE_PUBLIC_KEY or '')
    return web.Response(text=page, content_type='text/html')

async def handle_user_panel(request):
    discord_id = request.match_info['discord_id']
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Basic '):
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            login, pwd = decoded.split(':', 1)
            stored_pwd = get_panel_password(discord_id)
            if login == discord_id and stored_pwd and pwd == stored_pwd and is_premium(discord_id):
                return web.Response(text=get_premium_user_panel(discord_id), content_type='text/html')
        except Exception:
            pass
    return web.Response(status=401, headers={'WWW-Authenticate': f'Basic realm="Panel Premium"'}, text='Accès refusé')

async def handle_stats(request):
    guilds = client_discord.guilds
    all_premium = get_all_premium()
    all_server_premium = get_all_server_premium()
    active_users = sum(1 for u in all_premium if u[3] == 'active')
    active_servers = sum(1 for s in all_server_premium if s[3] == 'active')
    revenue = round(active_users * 2.5 + active_servers * 9.99, 2)
    server_premium_ids = {s[0] for s in all_server_premium if s[3] == 'active'}
    return web.json_response({
        "guilds": len(guilds),
        "users": sum(g.member_count for g in guilds),
        "memory_channels": len(conversation_history),
        "premium_count": active_users,
        "server_premium_count": active_servers,
        "revenue": revenue,
        "guild_list": [{"id": str(g.id), "name": g.name, "members": g.member_count, "premium": str(g.id) in server_premium_ids} for g in guilds]
    })

async def handle_guild_stats(request):
    guild_id = request.match_info['guild_id']
    guild = client_discord.get_guild(int(guild_id))
    if not guild:
        return web.json_response({"members": 0, "messages_today": 0, "top_level": "—"})
    today_msgs = sum(1 for m in live_messages if m.get("guild_id") == guild_id and m["time"].startswith(datetime.now().strftime("%H")))
    lb = get_leaderboard(guild_id, 1)
    top_level = get_level(lb[0][1])["name"] if lb else "—"
    return web.json_response({"members": guild.member_count, "messages_today": today_msgs, "top_level": top_level})

async def handle_leaderboard(request):
    guild_id = request.match_info['guild_id']
    lb = get_leaderboard(guild_id, 15)
    result = []
    for row in lb:
        lvl = get_level(row[1])
        result.append({"discord_id": row[0], "xp": row[1], "level": lvl["name"], "emoji": lvl["emoji"]})
    return web.json_response(result)

async def handle_mod_logs(request):
    guild_id = request.match_info.get('guild_id', 'all')
    requester = request.rel_url.query.get('requester', '')
    if guild_id == 'all':
        return web.json_response({"logs": mod_logs[-200:]})
    # Pour panel premium : vérifie que le requester est membre du guild
    guild = client_discord.get_guild(int(guild_id))
    if requester and guild and not guild.get_member(int(requester)):
        return web.json_response({"logs": []})
    filtered = [l for l in mod_logs if l["guild_id"] == guild_id]
    return web.json_response({"logs": filtered[-100:]})

async def handle_premium_list(request):
    users = get_all_premium()
    return web.json_response({
        "active_count": sum(1 for u in users if u[3] == 'active'),
        "users": [{"discord_id": u[0], "status": u[3], "created_at": u[4], "has_panel": bool(u[5])} for u in users]
    })

async def handle_server_premium_list(request):
    servers = get_all_server_premium()
    result = []
    for s in servers:
        guild = client_discord.get_guild(int(s[0])) if s[0] else None
        result.append({"guild_id": s[0], "guild_name": guild.name if guild else "—", "status": s[3], "owner_discord_id": s[4], "created_at": s[5]})
    return web.json_response(result)

async def handle_premium_grant(request):
    data = await request.json()
    discord_id = str(data["discord_id"])
    panel_pwd = generate_panel_password()
    set_premium(discord_id, "manual", "manual", "active", panel_pwd)
    await assign_premium_role(discord_id)
    await send_panel_credentials(discord_id, panel_pwd)
    return web.json_response({"success": True, "message": "Premium activé ✅ MP envoyé"})

async def handle_premium_revoke(request):
    data = await request.json()
    set_premium(str(data["discord_id"]), "", "", "inactive")
    await remove_premium_role(str(data["discord_id"]))
    return web.json_response({"success": True, "message": "Premium révoqué ✅"})

async def handle_server_premium_grant(request):
    data = await request.json()
    set_server_premium(str(data["guild_id"]), "manual", "manual", "active", str(data["owner_id"]))
    return web.json_response({"success": True, "message": "Premium serveur activé ✅"})

async def handle_server_premium_revoke(request):
    data = await request.json()
    set_server_premium(str(data["guild_id"]), "", "", "inactive", "")
    return web.json_response({"success": True, "message": "Premium serveur révoqué ✅"})

async def handle_create_subscription(request):
    data = await request.json()
    try:
        plan_type = data.get("type", "user")
        price_id = STRIPE_SERVER_PRICE_ID if plan_type == "server" else STRIPE_PRICE_ID
        customer = stripe.Customer.create(metadata={"discord_id": str(data["discord_id"]), "guild_id": data.get("guild_id", ""), "type": plan_type})
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": price_id}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )
        return web.json_response({"client_secret": subscription.latest_invoice.payment_intent.client_secret, "subscription_id": subscription.id, "customer_id": customer.id})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def handle_confirm_premium(request):
    data = await request.json()
    discord_id = str(data["discord_id"])
    plan_type = data.get("type", "user")
    if plan_type == "server":
        set_server_premium(str(data.get("guild_id", "")), data.get("customer_id", ""), data.get("subscription_id", ""), "active", discord_id)
        try:
            user = await client_discord.fetch_user(int(discord_id))
            guild = client_discord.get_guild(int(data.get("guild_id", 0)))
            embed = discord.Embed(title="🏰 Premium Serveur activé !", color=0x7c3aed)
            embed.description = f"Le serveur **{guild.name if guild else data.get('guild_id')}** est maintenant Premium !"
            await user.send(embed=embed)
        except Exception as e:
            print(f"Erreur MP server premium : {e}")
    else:
        panel_pwd = generate_panel_password()
        set_premium(discord_id, data.get("customer_id", ""), data.get("subscription_id", ""), "active", panel_pwd)
        await assign_premium_role(discord_id)
        await send_panel_credentials(discord_id, panel_pwd)
    return web.json_response({"success": True})

async def handle_premium_moderation(request):
    data = await request.json()
    discord_id = str(data.get("requester_id", ""))
    if not is_premium(discord_id):
        return web.json_response({"success": False, "message": "Accès refusé"})
    guild = client_discord.get_guild(int(data["guild_id"]))
    if not guild or not guild.get_member(int(discord_id)):
        return web.json_response({"success": False, "message": "Serveur non autorisé"})
    try:
        member = guild.get_member(int(data["user_id"]))
        if not member:
            return web.json_response({"success": False, "message": "Membre introuvable"})
        if data["action"] == "kick":
            await member.kick(reason=data.get("extra", "Panel premium"))
            add_mod_log(guild.id, guild.name, "kick", member.id, discord_id, data.get("extra"))
            return web.json_response({"success": True, "message": f"{member.name} kick ✅"})
        elif data["action"] == "ban":
            await member.ban(reason=data.get("extra", "Panel premium"))
            add_mod_log(guild.id, guild.name, "ban", member.id, discord_id, data.get("extra"))
            return web.json_response({"success": True, "message": f"{member.name} banni ✅"})
        elif data["action"] == "mute":
            until = discord.utils.utcnow() + timedelta(minutes=int(data.get("extra", 10)))
            await member.timeout(until)
            add_mod_log(guild.id, guild.name, "mute", member.id, discord_id, f"{data.get('extra')} min")
            return web.json_response({"success": True, "message": f"{member.name} muté ✅"})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})

async def handle_live_messages(request):
    return web.json_response(live_messages[-100:])

async def handle_memory(request):
    return web.json_response({str(k): len(v) for k, v in conversation_history.items()})

async def handle_memory_reset(request):
    data = await request.json()
    conversation_history.pop(int(data["channel_id"]), None)
    return web.json_response({"success": True})

async def handle_memory_reset_all(request):
    conversation_history.clear()
    return web.json_response({"success": True})

async def handle_blacklist(request):
    return web.json_response(list(blacklist))

async def handle_blacklist_add(request):
    data = await request.json()
    blacklist.add(str(data["user_id"]))
    return web.json_response({"success": True})

async def handle_blacklist_remove(request):
    data = await request.json()
    blacklist.discard(str(data["user_id"]))
    return web.json_response({"success": True})

async def handle_broadcast(request):
    data = await request.json()
    try:
        channel = client_discord.get_channel(int(data["channel_id"]))
        if not channel:
            return web.json_response({"success": False, "message": "Channel introuvable"})
        await channel.send(data["message"])
        return web.json_response({"success": True, "message": "Envoyé ✅"})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})

async def handle_moderation(request):
    data = await request.json()
    try:
        guild = client_discord.get_guild(int(data["guild_id"]))
        if not guild:
            return web.json_response({"success": False, "message": "Serveur introuvable"})
        member = guild.get_member(int(data["user_id"]))
        if not member:
            return web.json_response({"success": False, "message": "Membre introuvable"})
        if data["action"] == "kick":
            await member.kick(reason=data.get("extra", "Admin"))
            add_mod_log(guild.id, guild.name, "kick", member.id, "admin-panel", data.get("extra"))
            return web.json_response({"success": True, "message": f"{member.name} kick ✅"})
        elif data["action"] == "ban":
            await member.ban(reason=data.get("extra", "Admin"))
            add_mod_log(guild.id, guild.name, "ban", member.id, "admin-panel", data.get("extra"))
            return web.json_response({"success": True, "message": f"{member.name} banni ✅"})
        elif data["action"] == "mute":
            until = discord.utils.utcnow() + timedelta(minutes=int(data.get("extra", 10)))
            await member.timeout(until)
            add_mod_log(guild.id, guild.name, "mute", member.id, "admin-panel", f"{data.get('extra')} min")
            return web.json_response({"success": True, "message": f"{member.name} muté ✅"})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})

async def handle_status(request):
    data = await request.json()
    types = {"playing": discord.ActivityType.playing, "watching": discord.ActivityType.watching, "listening": discord.ActivityType.listening, "competing": discord.ActivityType.competing}
    try:
        await client_discord.change_presence(activity=discord.Activity(type=types[data["type"]], name=data["text"]))
        return web.json_response({"success": True, "message": "Status changé ✅"})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})

async def handle_personality_get(request):
    return web.json_response({"current": current_personality, "personalities": dict(personalities)})

async def handle_personality_post(request):
    global current_personality, personalities
    data = await request.json()
    if "switch" in data:
        if data["switch"] in personalities:
            current_personality = data["switch"]
            return web.json_response({"success": True, "message": f"Personnalité : {current_personality} ✅"})
    if "name" in data and "text" in data:
        personalities[data["name"]] = data["text"]
        return web.json_response({"success": True, "message": f"'{data['name']}' sauvegardée ✅"})
    if "delete" in data:
        if data["delete"] in personalities and data["delete"] != current_personality:
            del personalities[data["delete"]]
            return web.json_response({"success": True, "message": "Supprimée ✅"})
        return web.json_response({"success": False, "message": "Impossible de supprimer la personnalité active"})
    return web.json_response({"success": False, "message": "Requête invalide"})

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_panel)
    app.router.add_get('/premium', handle_premium_page)
    app.router.add_get('/panel/{discord_id}', handle_user_panel)
    app.router.add_get('/api/stats', handle_stats)
    app.router.add_get('/api/guild-stats/{guild_id}', handle_guild_stats)
    app.router.add_get('/api/leaderboard/{guild_id}', handle_leaderboard)
    app.router.add_get('/api/live-messages', handle_live_messages)
    app.router.add_get('/api/memory', handle_memory)
    app.router.add_post('/api/memory/reset', handle_memory_reset)
    app.router.add_post('/api/memory/reset-all', handle_memory_reset_all)
    app.router.add_get('/api/blacklist', handle_blacklist)
    app.router.add_post('/api/blacklist/add', handle_blacklist_add)
    app.router.add_post('/api/blacklist/remove', handle_blacklist_remove)
    app.router.add_post('/api/broadcast', handle_broadcast)
    app.router.add_post('/api/moderation', handle_moderation)
    app.router.add_post('/api/premium-moderation', handle_premium_moderation)
    app.router.add_post('/api/status', handle_status)
    app.router.add_get('/api/personality', handle_personality_get)
    app.router.add_post('/api/personality', handle_personality_post)
    app.router.add_get('/api/premium', handle_premium_list)
    app.router.add_post('/api/premium/grant', handle_premium_grant)
    app.router.add_post('/api/premium/revoke', handle_premium_revoke)
    app.router.add_get('/api/server-premium', handle_server_premium_list)
    app.router.add_post('/api/server-premium/grant', handle_server_premium_grant)
    app.router.add_post('/api/server-premium/revoke', handle_server_premium_revoke)
    app.router.add_post('/api/create-subscription', handle_create_subscription)
    app.router.add_post('/api/confirm-premium', handle_confirm_premium)
    app.router.add_get('/api/mod-logs/{guild_id}', handle_mod_logs)
    app.router.add_get('/api/mod-logs/all', handle_mod_logs)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()
    print(f"Panel : {BASE_URL}")

# ========================
# EVENTS DISCORD
# ========================

@client_discord.event
async def on_ready():
    await client_discord.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name="League of Legends | Challenger 🏆"),
        status=discord.Status.online
    )
    print(f"Bot connecté : {client_discord.user}")

@client_discord.event
async def on_message(message):
    if message.author == client_discord.user:
        return

    guild_id = str(message.guild.id) if message.guild else None

    live_messages.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "server": message.guild.name if message.guild else "DM",
        "guild_id": guild_id,
        "channel": message.channel.name if hasattr(message.channel, 'name') else "DM",
        "author": message.author.display_name,
        "content": message.content[:200],
        "premium": is_premium(str(message.author.id))
    })
    if len(live_messages) > MAX_LIVE:
        live_messages.pop(0)

    if str(message.author.id) in blacklist:
        return

    # Réponses automatiques aux mots clés (sans mention)
    if not message.author.bot and message.guild:
        content_lower = message.content.lower()
        for keyword, responses in AUTO_RESPONSES.items():
            if keyword in content_lower:
                if random.random() < 0.4:  # 40% de chance de répondre
                    await message.channel.send(random.choice(responses))
                break

    # XP gagné en parlant
    if message.guild and not message.author.bot:
        new_xp, level, leveled_up = add_xp(str(message.author.id), str(message.guild.id), XP_PER_MESSAGE)
        if leveled_up:
            await assign_level_role(message.author, leveled_up)
            embed = discord.Embed(
                title=f"⬆️ Level Up !",
                description=f"{message.author.mention} vient de passer **{leveled_up['name']} {leveled_up['emoji']}** ! ({new_xp} XP)",
                color=0xFFD700
            )
            await message.channel.send(embed=embed)

    if client_discord.user.mentioned_in(message):
        question = message.content.replace(f"<@{client_discord.user.id}>", "").replace(f"<@!{client_discord.user.id}>", "").strip()
        if not question:
            await message.channel.send("Tu m'as ping, mais t'as rien dit… typique d'un joueur Bronze 😅")
            return
        async with message.channel.typing():
            try:
                text, premium = await ask_groq(message.channel.id, message.author.display_name, question, message.author.id, guild_id)
                for part in split_message(text):
                    await message.channel.send(part)
            except Exception as e:
                print("Erreur Groq :", e)
                await message.channel.send("⚠️ L'IA est en cooldown. Réessaie dans quelques secondes.")

# ========================
# COMMANDES SLASH
# ========================

@client_discord.tree.command(name="ask", description="Pose une question au bot")
@app_commands.describe(question="Ta question")
async def ask(interaction: discord.Interaction, question: str):
    if str(interaction.user.id) in blacklist:
        await interaction.response.send_message("❌ Tu es blacklisté.", ephemeral=True)
        return
    await interaction.response.defer()
    try:
        guild_id = str(interaction.guild_id) if interaction.guild_id else None
        text, premium = await ask_groq(interaction.channel_id, interaction.user.display_name, question, interaction.user.id, guild_id)
        embed = discord.Embed(description=text, color=0xFFD700 if premium else 0x5865F2)
        embed.set_footer(text=f"{'👑 Premium' if premium else '🆓 Gratuit'} • {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send("⚠️ Erreur. Réessaie.")

@client_discord.tree.command(name="roast", description="Fais roast quelqu'un par le bot 🔥")
@app_commands.describe(cible="La personne à roast")
async def roast(interaction: discord.Interaction, cible: discord.Member):
    await interaction.response.defer()
    prompt = f"Fais un roast ultra sarcastique style League of Legends de {cible.display_name}. Sois méchant mais drôle, style gamer toxique. Max 5 lignes."
    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": personalities["LoL Arrogant"]},
                {"role": "user", "content": prompt}
            ]
        )
        text = response.choices[0].message.content
        embed = discord.Embed(description=f"🔥 **Roast de {cible.mention}**\n\n{text}", color=0xFF4500)
        embed.set_footer(text=f"Demandé par {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)
    except Exception:
        await interaction.followup.send("⚠️ Erreur. Réessaie.")

@client_discord.tree.command(name="tip", description="Conseil LoL aléatoire du jour 🏆")
async def tip(interaction: discord.Interaction):
    embed = discord.Embed(description=random.choice(LOL_TIPS), color=0x00D4AA)
    embed.set_footer(text="Mec_IA • Coach Challenger")
    await interaction.response.send_message(embed=embed)

@client_discord.tree.command(name="niveau", description="Voir ton niveau et ton XP")
async def niveau(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ Commande disponible uniquement sur un serveur.", ephemeral=True)
        return
    xp = get_xp(str(interaction.user.id), str(interaction.guild_id))
    level = get_level(xp)
    next_lvl = get_next_level(xp)
    embed = discord.Embed(title=f"{level['emoji']} {level['name']}", color=0xFFD700)
    embed.add_field(name="XP total", value=f"{xp} XP", inline=True)
    if next_lvl:
        remaining = next_lvl["min"] - xp
        embed.add_field(name="Prochain niveau", value=f"{next_lvl['name']} dans {remaining} XP", inline=True)
    else:
        embed.add_field(name="Statut", value="🏆 Niveau MAX !", inline=True)
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@client_discord.tree.command(name="classement", description="Top 10 XP du serveur 🏆")
async def classement(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ Commande disponible uniquement sur un serveur.", ephemeral=True)
        return
    await interaction.response.defer()
    lb = get_leaderboard(str(interaction.guild_id), 10)
    if not lb:
        await interaction.followup.send("Aucun XP enregistré sur ce serveur encore !")
        return
    embed = discord.Embed(title=f"🏆 Classement XP — {interaction.guild.name}", color=0xFFD700)
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (discord_id, xp) in enumerate(lb):
        level = get_level(xp)
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        try:
            user = interaction.guild.get_member(int(discord_id))
            name = user.display_name if user else f"User {discord_id[:6]}"
        except Exception:
            name = f"User {discord_id[:6]}"
        lines.append(f"{medal} **{name}** — {level['emoji']} {level['name']} • {xp} XP")
    embed.description = "\n".join(lines)
    await interaction.followup.send(embed=embed)

@client_discord.tree.command(name="premium", description="S'abonner au premium")
async def premium_cmd(interaction: discord.Interaction):
    if is_premium(str(interaction.user.id)):
        panel_pwd = get_panel_password(str(interaction.user.id))
        embed = discord.Embed(title="👑 Tu es déjà Premium !", color=0xFFD700)
        embed.description = "Tu profites déjà de tous les avantages !"
        if panel_pwd:
            embed.add_field(name="🔗 Ton panel", value=f"{BASE_URL}/panel/{interaction.user.id}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    embed = discord.Embed(title="👑 Passe Premium !", color=0xFFD700)
    embed.description = f"**2,50€/mois** (personnel) ou **9,99€/mois** (serveur entier)\n\n✓ Mémoire 100 messages\n✓ IA Llama 70B\n✓ Toutes les personnalités\n✓ Rôle Premium 👑\n✓ Panel admin personnel"
    embed.add_field(name="Lien de paiement", value=f"{BASE_URL}/premium")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client_discord.tree.command(name="monpanel", description="Accéder à ton panel premium")
async def monpanel(interaction: discord.Interaction):
    if not is_premium(str(interaction.user.id)):
        await interaction.response.send_message("❌ Réservé aux membres Premium. Tape /premium !", ephemeral=True)
        return
    panel_pwd = get_panel_password(str(interaction.user.id))
    embed = discord.Embed(title="👑 Ton Panel Premium", color=0xFFD700)
    embed.add_field(name="🔗 URL", value=f"{BASE_URL}/panel/{interaction.user.id}", inline=False)
    embed.add_field(name="👤 Login", value=str(interaction.user.id), inline=True)
    embed.add_field(name="🔑 Mot de passe", value=f"||{panel_pwd}||", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client_discord.tree.command(name="reset", description="Efface la mémoire du bot")
async def reset(interaction: discord.Interaction):
    conversation_history[interaction.channel_id] = []
    await interaction.response.send_message("Mémoire effacée 🧹")

@client_discord.tree.command(name="status", description="Statut du bot")
async def bot_status(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id) if interaction.guild_id else None
    premium = is_premium_any(str(interaction.user.id), guild_id) if guild_id else is_premium(str(interaction.user.id))
    embed = discord.Embed(title="🤖 Statut", color=0xFFD700 if premium else 0x5865F2)
    embed.add_field(name="Modèle", value="Llama 70B 🔥" if premium else "Llama 8B", inline=True)
    embed.add_field(name="Mémoire", value=f"{len(conversation_history.get(interaction.channel_id,[]))}/{'100' if premium else '20'}", inline=True)
    embed.add_field(name="Ping", value=f"{round(client_discord.latency*1000)}ms", inline=True)
    embed.add_field(name="Statut", value="👑 Premium" if premium else "🆓 Gratuit", inline=True)
    await interaction.response.send_message(embed=embed)

@client_discord.tree.command(name="admin", description="Panel admin")
async def admin(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ Accès refusé.", ephemeral=True)
        return
    await interaction.response.send_message(f"🔐 Panel admin : {BASE_URL}", ephemeral=True)

# ========================
# LANCEMENT
# ========================

async def main():
    await start_web_server()
    asyncio.ensure_future(send_premium_ad())
    await client_discord.start(DISCORD_TOKEN)

asyncio.run(main())
