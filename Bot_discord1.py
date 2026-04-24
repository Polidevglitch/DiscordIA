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

load_dotenv(r"C:/Users/benoi/Documents/.env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "admin")
ADMIN_ID = 1314677631609733131
GUILD_ID = 1493653601791377570
PREMIUM_ROLE_NAME = "Premium 👑"

stripe.api_key = STRIPE_SECRET_KEY

if not GROQ_API_KEY or not DISCORD_TOKEN:
    raise ValueError("Les variables d'environnement GROQ_API_KEY et DISCORD_TOKEN sont requises.")

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
            created_at TEXT
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

def set_premium(discord_id: str, customer_id: str, subscription_id: str, status: str):
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
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

def get_all_premium():
    conn = sqlite3.connect("premium.db")
    c = conn.cursor()
    c.execute("SELECT discord_id, stripe_customer_id, stripe_subscription_id, status, created_at FROM premium_users")
    rows = c.fetchall()
    conn.close()
    return rows

init_db()

# ========================
# CONFIG BOT
# ========================

groq_client = AsyncGroq(api_key=GROQ_API_KEY)

personalities = {
    "LoL Arrogant": """
Tu es un bot avec une personnalité de nerd arrogant et joueur de League of Legends.
Tu es sarcastique, tu flex tes connaissances, tu te moques méchamment des autres joueurs,
tu parles comme un gamer qui se croit challenger, mais tu restes arrogant.
Tu utilises un humour toxique mais léger, style LoL, sans insulter et tu
abreges tes phrases pas plus de 50 lignes.
""",
    "Assistant Sympa": """
Tu es un assistant Discord sympa, serviable et bienveillant.
Tu réponds clairement et simplement, tu aides les gens avec plaisir.
Tu es positif et encourageant.
""",
    "Philosophe": """
Tu es un philosophe mystérieux qui répond à tout avec des métaphores profondes.
Tu cites des philosophes, tu poses des questions existentielles,
tu vois le sens caché derrière chaque question.
""",
    "Pirate": """
Tu es un pirate des mers, tu parles comme un vieux loup de mer.
Tu utilises des expressions pirates, tu parles de trésors et d'aventures.
Tu es charismatique et imprévisible.
"""
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

async def ask_groq(channel_id, username, question, discord_id):
    premium = is_premium(str(discord_id))
    max_history = MAX_HISTORY_PREMIUM if premium else MAX_HISTORY_FREE
    model = "llama-3.3-70b-versatile" if premium else "llama-3.1-8b-instant"

    if channel_id not in conversation_history:
        conversation_history[channel_id] = []

    conversation_history[channel_id].append({"role": "user", "content": f"{username}: {question}"})

    if len(conversation_history[channel_id]) > max_history:
        conversation_history[channel_id] = conversation_history[channel_id][-max_history:]

    response = await groq_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": personalities[current_personality]},
            *conversation_history[channel_id]
        ]
    )
    text = response.choices[0].message.content
    conversation_history[channel_id].append({"role": "assistant", "content": text})
    return text, premium

async def assign_premium_role(discord_id: str):
    try:
        guild = client_discord.get_guild(GUILD_ID)
        if not guild:
            return
        member = guild.get_member(int(discord_id))
        if not member:
            return
        role = discord.utils.get(guild.roles, name=PREMIUM_ROLE_NAME)
        if not role:
            role = await guild.create_role(name=PREMIUM_ROLE_NAME, color=discord.Color.gold())
        await member.add_roles(role)
    except Exception as e:
        print(f"Erreur rôle premium : {e}")

async def remove_premium_role(discord_id: str):
    try:
        guild = client_discord.get_guild(GUILD_ID)
        if not guild:
            return
        member = guild.get_member(int(discord_id))
        if not member:
            return
        role = discord.utils.get(guild.roles, name=PREMIUM_ROLE_NAME)
        if role and role in member.roles:
            await member.remove_roles(role)
    except Exception as e:
        print(f"Erreur suppression rôle : {e}")

# ========================
# PAGE PREMIUM
# ========================

PREMIUM_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Premium - Mec_IA</title>
<script src="https://js.stripe.com/v3/"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
  .container { max-width: 480px; width: 100%; padding: 40px 20px; }
  h1 { text-align: center; font-size: 28px; margin-bottom: 8px; }
  .subtitle { text-align: center; color: #8b949e; margin-bottom: 30px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 16px; padding: 30px; margin-bottom: 20px; }
  .price { text-align: center; font-size: 48px; font-weight: bold; color: #FFD700; margin: 20px 0 5px; }
  .price span { font-size: 18px; color: #8b949e; }
  .features { list-style: none; margin: 20px 0; }
  .features li { padding: 8px 0; border-bottom: 1px solid #21262d; display: flex; align-items: center; gap: 10px; }
  .features li:last-child { border: none; }
  .check { color: #3fb950; font-size: 18px; }
  input { width: 100%; background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 12px; border-radius: 8px; margin-bottom: 12px; font-size: 14px; }
  #card-element { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
  button { width: 100%; background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; border: none; padding: 14px; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: bold; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .error { color: #f85149; font-size: 13px; margin-bottom: 10px; display: none; }
  .success { background: #1a3a2a; border: 1px solid #238636; border-radius: 8px; padding: 20px; text-align: center; display: none; }
  .badge { background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; display: inline-block; margin-bottom: 15px; }
</style>
</head>
<body>
<div class="container">
  <div style="text-align:center; margin-bottom:20px;">
    <span class="badge">👑 PREMIUM</span>
    <h1>Mec_IA Premium</h1>
    <p class="subtitle">Débloque toutes les fonctionnalités</p>
  </div>
  <div class="card">
    <div class="price">2,50€ <span>/ mois</span></div>
    <ul class="features">
      <li><span class="check">✓</span> Mémoire de 100 messages (au lieu de 20)</li>
      <li><span class="check">✓</span> Modèle IA plus puissant (Llama 70B)</li>
      <li><span class="check">✓</span> Accès à toutes les personnalités</li>
      <li><span class="check">✓</span> Rôle Premium 👑 sur le serveur</li>
      <li><span class="check">✓</span> Sans limite de messages</li>
    </ul>
    <div id="success-msg" class="success">
      <div style="font-size:40px; margin-bottom:10px;">🎉</div>
      <h3 style="color:#3fb950;">Paiement réussi !</h3>
      <p style="color:#8b949e; margin-top:8px;">Ton accès premium est activé. Retourne sur Discord !</p>
    </div>
    <div id="payment-form">
      <input type="text" id="discord-id" placeholder="Ton ID Discord (ex: 123456789012345678)">
      <div id="card-element"></div>
      <div class="error" id="error-msg"></div>
      <button id="pay-btn" onclick="handlePayment()">💳 S'abonner pour 2,50€/mois</button>
    </div>
  </div>
  <p style="text-align:center; color:#484f58; font-size:12px;">Paiement sécurisé par Stripe • Annulable à tout moment</p>
</div>
<script>
const stripe = Stripe('STRIPE_PUBLIC_KEY_PLACEHOLDER');
const elements = stripe.elements();
const cardElement = elements.create('card', {
  style: { base: { color: '#e6edf3', fontFamily: 'Segoe UI, sans-serif', fontSize: '14px', '::placeholder': { color: '#484f58' } } }
});
cardElement.mount('#card-element');

async function handlePayment() {
  const discordId = document.getElementById('discord-id').value.trim();
  const btn = document.getElementById('pay-btn');
  const errorEl = document.getElementById('error-msg');
  if (!discordId || !/^\\d{17,19}$/.test(discordId)) {
    errorEl.textContent = "Entre un ID Discord valide (17-19 chiffres)";
    errorEl.style.display = 'block';
    return;
  }
  btn.disabled = true;
  btn.textContent = 'Traitement...';
  errorEl.style.display = 'none';
  try {
    const r = await fetch('/api/create-subscription', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ discord_id: discordId })
    });
    const data = await r.json();
    if (!data.client_secret) throw new Error(data.error || 'Erreur serveur');
    const result = await stripe.confirmCardPayment(data.client_secret, { payment_method: { card: cardElement } });
    if (result.error) {
      errorEl.textContent = result.error.message;
      errorEl.style.display = 'block';
      btn.disabled = false;
      btn.textContent = "💳 S'abonner pour 2,50€/mois";
    } else {
      await fetch('/api/confirm-premium', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ discord_id: discordId, subscription_id: data.subscription_id, customer_id: data.customer_id })
      });
      document.getElementById('payment-form').style.display = 'none';
      document.getElementById('success-msg').style.display = 'block';
    }
  } catch(e) {
    errorEl.textContent = e.message;
    errorEl.style.display = 'block';
    btn.disabled = false;
    btn.textContent = "💳 S'abonner pour 2,50€/mois";
  }
}
</script>
</body>
</html>"""

# ========================
# PANEL ADMIN
# ========================

HTML_PANEL = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Panel Admin - Mec_IA</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', sans-serif; }
  .sidebar { width: 220px; background: #161b22; height: 100vh; position: fixed; padding: 20px; border-right: 1px solid #30363d; }
  .sidebar h2 { color: #5865F2; font-size: 18px; margin-bottom: 30px; }
  .sidebar a { display: block; color: #8b949e; padding: 10px; border-radius: 8px; text-decoration: none; margin-bottom: 5px; cursor: pointer; }
  .sidebar a:hover, .sidebar a.active { background: #21262d; color: #e6edf3; }
  .main { margin-left: 220px; padding: 30px; }
  h1 { font-size: 24px; margin-bottom: 20px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
  .card h3 { color: #8b949e; font-size: 13px; text-transform: uppercase; margin-bottom: 10px; }
  .card .value { font-size: 28px; font-weight: bold; color: #5865F2; }
  .section { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
  .section h2 { margin-bottom: 15px; font-size: 16px; }
  input, select, textarea { width: 100%; background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 10px; border-radius: 8px; margin-bottom: 10px; font-size: 14px; }
  button { background: #5865F2; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 14px; }
  button.red { background: #da3633; }
  button.green { background: #238636; }
  button.gold { background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; font-weight: bold; }
  .msg-feed { height: 400px; overflow-y: auto; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 15px; font-size: 13px; }
  .msg { padding: 6px 0; border-bottom: 1px solid #21262d; }
  .msg .time { color: #484f58; font-size: 11px; }
  .msg .server { color: #5865F2; font-weight: bold; }
  .msg .author { color: #3fb950; }
  .tab { display: none; }
  .tab.active { display: block; }
  .alert { padding: 10px 15px; border-radius: 8px; margin-bottom: 15px; display: none; }
  .alert.success { background: #1a3a2a; border: 1px solid #238636; color: #3fb950; }
  .alert.error { background: #3a1a1a; border: 1px solid #da3633; color: #f85149; }
  .premium-badge { background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 10px; border-bottom: 1px solid #30363d; color: #8b949e; }
  td { padding: 10px; border-bottom: 1px solid #21262d; }
  .blacklist-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  .blacklist-item { background: #21262d; padding: 5px 12px; border-radius: 20px; font-size: 13px; display: flex; align-items: center; gap: 8px; }
  .memory-item { background: #0d1117; padding: 10px; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
</style>
</head>
<body>
<div class="sidebar">
  <h2>🎮 Mec_IA Admin</h2>
  <a class="active" onclick="showTab('dashboard')">📊 Dashboard</a>
  <a onclick="showTab('messages')">💬 Messages live</a>
  <a onclick="showTab('moderation')">🔨 Modération</a>
  <a onclick="showTab('broadcast')">📢 Broadcast</a>
  <a onclick="showTab('memory')">🧠 Mémoire</a>
  <a onclick="showTab('premium')">👑 Premium</a>
  <a onclick="showTab('settings')">⚙️ Personnalités</a>
</div>

<div class="main">
  <div id="alert" class="alert"></div>

  <div id="tab-dashboard" class="tab active">
    <h1>📊 Dashboard</h1>
    <div class="grid">
      <div class="card"><h3>Serveurs</h3><div class="value" id="stat-guilds">...</div></div>
      <div class="card"><h3>Utilisateurs</h3><div class="value" id="stat-users">...</div></div>
      <div class="card"><h3>Mémoire</h3><div class="value" id="stat-memory">...</div></div>
      <div class="card"><h3>Premium 👑</h3><div class="value" id="stat-premium" style="color:#FFD700;">...</div></div>
    </div>
    <div class="section"><h2>Serveurs</h2><div id="guilds-list"></div></div>
  </div>

  <div id="tab-messages" class="tab">
    <h1>💬 Messages live</h1>
    <div class="section">
      <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
        <span style="color:#8b949e;font-size:13px;">Auto-refresh 3s</span>
        <button onclick="clearFeed()" class="red" style="padding:5px 12px;font-size:12px;">Vider</button>
      </div>
      <div class="msg-feed" id="msg-feed"></div>
    </div>
  </div>

  <div id="tab-moderation" class="tab">
    <h1>🔨 Modération</h1>
    <div class="grid">
      <div class="section"><h2>👢 Kick</h2>
        <input id="kick-guild" placeholder="ID serveur"><input id="kick-user" placeholder="ID utilisateur"><input id="kick-reason" placeholder="Raison">
        <button onclick="doAction('kick')">Kick</button></div>
      <div class="section"><h2>🔨 Ban</h2>
        <input id="ban-guild" placeholder="ID serveur"><input id="ban-user" placeholder="ID utilisateur"><input id="ban-reason" placeholder="Raison">
        <button class="red" onclick="doAction('ban')">Ban</button></div>
      <div class="section"><h2>🔇 Mute</h2>
        <input id="mute-guild" placeholder="ID serveur"><input id="mute-user" placeholder="ID utilisateur"><input id="mute-duration" type="number" placeholder="Minutes">
        <button onclick="doAction('mute')">Mute</button></div>
    </div>
    <div class="section"><h2>🚫 Blacklist bot</h2>
      <div style="display:flex;gap:10px;"><input id="blacklist-user" placeholder="ID utilisateur" style="margin:0;"><button onclick="addBlacklist()" style="white-space:nowrap;">Ajouter</button></div>
      <div class="blacklist-list" id="blacklist-list"></div>
    </div>
  </div>

  <div id="tab-broadcast" class="tab">
    <h1>📢 Broadcast</h1>
    <div class="section"><h2>Envoyer un message</h2>
      <input id="bc-channel" placeholder="ID du channel">
      <textarea id="bc-message" rows="4" placeholder="Ton message..."></textarea>
      <button class="green" onclick="sendBroadcast()">Envoyer</button>
    </div>
    <div class="section"><h2>⚙️ Status du bot</h2>
      <select id="status-type">
        <option value="playing">🎮 Playing</option><option value="watching">👀 Watching</option>
        <option value="listening">🎵 Listening</option><option value="competing">🏆 Competing</option>
      </select>
      <input id="status-text" placeholder="Texte du status">
      <button onclick="changeStatus()">Changer</button>
    </div>
  </div>

  <div id="tab-memory" class="tab">
    <h1>🧠 Mémoire</h1>
    <div class="section">
      <div style="display:flex;justify-content:space-between;margin-bottom:15px;">
        <span style="color:#8b949e;">Par channel</span>
        <button class="red" onclick="resetAllMemory()">Tout effacer</button>
      </div>
      <div id="memory-list"></div>
    </div>
  </div>

  <div id="tab-premium" class="tab">
    <h1>👑 Premium</h1>
    <div class="grid">
      <div class="card"><h3>Abonnés actifs</h3><div class="value" id="premium-count" style="color:#FFD700;">...</div></div>
      <div class="card"><h3>Revenus/mois</h3><div class="value" id="premium-revenue" style="color:#3fb950;">...</div></div>
    </div>
    <div class="section">
      <div style="display:flex;justify-content:space-between;margin-bottom:15px;">
        <h2>Abonnés</h2>
        <a href="/premium" target="_blank"><button class="gold">🔗 Page paiement</button></a>
      </div>
      <table><thead><tr><th>Discord ID</th><th>Status</th><th>Depuis</th><th>Action</th></tr></thead>
      <tbody id="premium-table-body"></tbody></table>
    </div>
    <div class="section"><h2>➕ Ajouter manuellement</h2>
      <input id="manual-premium-id" placeholder="ID Discord">
      <button class="gold" onclick="addManualPremium()">👑 Activer Premium</button>
    </div>
  </div>

  <div id="tab-settings" class="tab">
    <h1>⚙️ Personnalités</h1>
    <div class="section"><h2>🎭 Personnalité active</h2>
      <div id="personality-switcher" style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:15px;"></div>
      <p style="color:#8b949e;font-size:13px;">Active : <span id="current-personality" style="color:#5865F2;font-weight:bold;"></span></p>
    </div>
    <div class="section"><h2>✏️ Créer / Modifier</h2>
      <input id="personality-name" placeholder="Nom">
      <textarea id="personality-text" rows="8" placeholder="Contenu..."></textarea>
      <div style="display:flex;gap:10px;">
        <button onclick="savePersonality()" class="green">Sauvegarder</button>
        <button onclick="deletePersonality()" class="red">Supprimer</button>
      </div>
    </div>
  </div>
</div>

<script>
let currentTab = 'dashboard';
let feedMessages = [];

function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.sidebar a').forEach(a => a.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
  currentTab = name;
  if (name === 'dashboard') loadDashboard();
  if (name === 'memory') loadMemory();
  if (name === 'moderation') loadBlacklist();
  if (name === 'settings') loadPersonality();
  if (name === 'premium') loadPremium();
}

function showAlert(msg, type) {
  const el = document.getElementById('alert');
  el.textContent = msg; el.className = 'alert ' + type; el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 3000);
}

async function loadDashboard() {
  const d = await fetch('/api/stats').then(r => r.json());
  document.getElementById('stat-guilds').textContent = d.guilds;
  document.getElementById('stat-users').textContent = d.users;
  document.getElementById('stat-memory').textContent = d.memory_channels;
  document.getElementById('stat-premium').textContent = d.premium_count;
  document.getElementById('guilds-list').innerHTML = d.guild_list.map(g =>
    `<div style="display:flex;justify-content:space-between;padding:10px;background:#0d1117;border-radius:8px;margin-bottom:8px;">
      <span>${g.name}</span><span style="color:#8b949e;">${g.members} membres</span></div>`
  ).join('');
}

async function loadPremium() {
  const d = await fetch('/api/premium').then(r => r.json());
  document.getElementById('premium-count').textContent = d.active_count;
  document.getElementById('premium-revenue').textContent = (d.active_count * 2.5).toFixed(2) + '€';
  document.getElementById('premium-table-body').innerHTML = d.users.map(u =>
    `<tr><td>${u.discord_id}</td>
    <td><span class="${u.status === 'active' ? 'premium-badge' : ''}">${u.status === 'active' ? '👑 Actif' : '❌ Inactif'}</span></td>
    <td style="color:#8b949e;">${u.created_at ? u.created_at.split('T')[0] : '-'}</td>
    <td>${u.status === 'active'
      ? `<button class="red" onclick="revokePremium('${u.discord_id}')" style="padding:4px 10px;font-size:12px;">Révoquer</button>`
      : `<button class="gold" onclick="grantPremium('${u.discord_id}')" style="padding:4px 10px;font-size:12px;">Activer</button>`
    }</td></tr>`
  ).join('');
}

async function addManualPremium() {
  const id = document.getElementById('manual-premium-id').value;
  await grantPremium(id);
  document.getElementById('manual-premium-id').value = '';
}

async function grantPremium(discord_id) {
  const d = await fetch('/api/premium/grant', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({discord_id}) }).then(r=>r.json());
  showAlert(d.message, d.success ? 'success' : 'error'); loadPremium();
}

async function revokePremium(discord_id) {
  const d = await fetch('/api/premium/revoke', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({discord_id}) }).then(r=>r.json());
  showAlert(d.message, d.success ? 'success' : 'error'); loadPremium();
}

async function loadMemory() {
  const d = await fetch('/api/memory').then(r=>r.json());
  const el = document.getElementById('memory-list');
  if (!Object.keys(d).length) { el.innerHTML = '<p style="color:#8b949e;">Aucune mémoire</p>'; return; }
  el.innerHTML = Object.entries(d).map(([cid, msgs]) =>
    `<div class="memory-item"><span>Channel ${cid} — ${msgs} msgs</span>
    <button class="red" onclick="resetMemory('${cid}')" style="padding:5px 10px;font-size:12px;">Effacer</button></div>`
  ).join('');
}

async function loadBlacklist() {
  const d = await fetch('/api/blacklist').then(r=>r.json());
  document.getElementById('blacklist-list').innerHTML = d.map(uid =>
    `<div class="blacklist-item"><span>${uid}</span><button onclick="removeBlacklist('${uid}')">✕</button></div>`
  ).join('');
}

async function doAction(action) {
  const guild = document.getElementById(action+'-guild').value;
  const user = document.getElementById(action+'-user').value;
  const extra = action === 'mute' ? document.getElementById('mute-duration').value : document.getElementById(action+'-reason').value;
  const d = await fetch('/api/moderation', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action, guild_id:guild, user_id:user, extra}) }).then(r=>r.json());
  showAlert(d.message, d.success ? 'success' : 'error');
}

async function addBlacklist() {
  const uid = document.getElementById('blacklist-user').value;
  await fetch('/api/blacklist/add', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid}) });
  document.getElementById('blacklist-user').value = ''; loadBlacklist(); showAlert('Blacklisté', 'success');
}

async function removeBlacklist(uid) {
  await fetch('/api/blacklist/remove', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid}) });
  loadBlacklist();
}

async function sendBroadcast() {
  const d = await fetch('/api/broadcast', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({channel_id:document.getElementById('bc-channel').value, message:document.getElementById('bc-message').value}) }).then(r=>r.json());
  showAlert(d.message, d.success ? 'success' : 'error');
}

async function changeStatus() {
  const d = await fetch('/api/status', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({type:document.getElementById('status-type').value, text:document.getElementById('status-text').value}) }).then(r=>r.json());
  showAlert(d.message, d.success ? 'success' : 'error');
}

async function resetMemory(channel_id) {
  await fetch('/api/memory/reset', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({channel_id}) });
  loadMemory(); showAlert('Mémoire effacée', 'success');
}

async function resetAllMemory() {
  await fetch('/api/memory/reset-all', { method:'POST' }); loadMemory(); showAlert('Tout effacé', 'success');
}

async function loadPersonality() {
  const d = await fetch('/api/personality').then(r=>r.json());
  document.getElementById('current-personality').textContent = d.current;
  document.getElementById('personality-switcher').innerHTML = Object.keys(d.personalities).map(name =>
    `<button onclick="switchPersonality('${name}')" style="${name===d.current?'background:#238636;':''}"
     onmouseover="previewPersonality('${name}', this.dataset.text)"
     data-text="${d.personalities[name].replace(/"/g,'&quot;')}">${name}</button>`
  ).join('');
}

async function switchPersonality(name) {
  const d = await fetch('/api/personality', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({switch:name}) }).then(r=>r.json());
  showAlert(d.message, d.success ? 'success' : 'error'); loadPersonality();
}

function previewPersonality(name, text) {
  document.getElementById('personality-name').value = name;
  document.getElementById('personality-text').value = text;
}

async function savePersonality() {
  const name = document.getElementById('personality-name').value;
  const text = document.getElementById('personality-text').value;
  if (!name || !text) { showAlert('Remplis le nom et le contenu', 'error'); return; }
  const d = await fetch('/api/personality', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, text}) }).then(r=>r.json());
  showAlert(d.message, d.success ? 'success' : 'error'); loadPersonality();
}

async function deletePersonality() {
  const name = document.getElementById('personality-name').value;
  if (!name) { showAlert('Sélectionne une personnalité', 'error'); return; }
  const d = await fetch('/api/personality', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({delete:name}) }).then(r=>r.json());
  showAlert(d.message, d.success ? 'success' : 'error'); loadPersonality();
}

function clearFeed() { feedMessages = []; renderFeed(); }

function renderFeed() {
  document.getElementById('msg-feed').innerHTML = feedMessages.slice(-100).reverse().map(m =>
    `<div class="msg">
      <span class="time">${m.time}</span>
      <span class="server"> [${m.server}]</span>
      <span style="color:#8b949e;"> #${m.channel}</span>
      <span class="author"> ${m.author}${m.premium?' 👑':''}:</span>
      <div style="color:#e6edf3;margin-top:2px;">${m.content}</div>
    </div>`
  ).join('');
}

async function pollMessages() {
  try { feedMessages = await fetch('/api/live-messages').then(r=>r.json()); if (currentTab==='messages') renderFeed(); } catch(e) {}
  setTimeout(pollMessages, 3000);
}

loadDashboard(); loadPersonality(); pollMessages();
</script>
</body>
</html>"""

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

async def handle_stats(request):
    guilds = client_discord.guilds
    active_premium = sum(1 for u in get_all_premium() if u[3] == 'active')
    return web.json_response({
        "guilds": len(guilds),
        "users": sum(g.member_count for g in guilds),
        "memory_channels": len(conversation_history),
        "blacklist": len(blacklist),
        "premium_count": active_premium,
        "guild_list": [{"id": str(g.id), "name": g.name, "members": g.member_count} for g in guilds]
    })

async def handle_premium_list(request):
    users = get_all_premium()
    return web.json_response({
        "active_count": sum(1 for u in users if u[3] == 'active'),
        "users": [{"discord_id": u[0], "stripe_customer_id": u[1], "stripe_subscription_id": u[2], "status": u[3], "created_at": u[4]} for u in users]
    })

async def handle_premium_grant(request):
    data = await request.json()
    set_premium(str(data["discord_id"]), "manual", "manual", "active")
    await assign_premium_role(str(data["discord_id"]))
    return web.json_response({"success": True, "message": f"Premium activé ✅"})

async def handle_premium_revoke(request):
    data = await request.json()
    set_premium(str(data["discord_id"]), "", "", "inactive")
    await remove_premium_role(str(data["discord_id"]))
    return web.json_response({"success": True, "message": f"Premium révoqué ✅"})

async def handle_create_subscription(request):
    data = await request.json()
    try:
        customer = stripe.Customer.create(metadata={"discord_id": str(data["discord_id"])})
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": STRIPE_PRICE_ID}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )
        return web.json_response({
            "client_secret": subscription.latest_invoice.payment_intent.client_secret,
            "subscription_id": subscription.id,
            "customer_id": customer.id
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def handle_confirm_premium(request):
    data = await request.json()
    set_premium(str(data["discord_id"]), data.get("customer_id", ""), data.get("subscription_id", ""), "active")
    await assign_premium_role(str(data["discord_id"]))
    return web.json_response({"success": True})

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
        return web.json_response({"success": True, "message": "Message envoyé ✅"})
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
            await member.kick(reason=data.get("extra", "Panel admin"))
            return web.json_response({"success": True, "message": f"{member.name} kick ✅"})
        elif data["action"] == "ban":
            await member.ban(reason=data.get("extra", "Panel admin"))
            return web.json_response({"success": True, "message": f"{member.name} banni ✅"})
        elif data["action"] == "mute":
            until = discord.utils.utcnow() + timedelta(minutes=int(data.get("extra", 10)))
            await member.timeout(until)
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
    app.router.add_get('/api/stats', handle_stats)
    app.router.add_get('/api/live-messages', handle_live_messages)
    app.router.add_get('/api/memory', handle_memory)
    app.router.add_post('/api/memory/reset', handle_memory_reset)
    app.router.add_post('/api/memory/reset-all', handle_memory_reset_all)
    app.router.add_get('/api/blacklist', handle_blacklist)
    app.router.add_post('/api/blacklist/add', handle_blacklist_add)
    app.router.add_post('/api/blacklist/remove', handle_blacklist_remove)
    app.router.add_post('/api/broadcast', handle_broadcast)
    app.router.add_post('/api/moderation', handle_moderation)
    app.router.add_post('/api/status', handle_status)
    app.router.add_get('/api/personality', handle_personality_get)
    app.router.add_post('/api/personality', handle_personality_post)
    app.router.add_get('/api/premium', handle_premium_list)
    app.router.add_post('/api/premium/grant', handle_premium_grant)
    app.router.add_post('/api/premium/revoke', handle_premium_revoke)
    app.router.add_post('/api/create-subscription', handle_create_subscription)
    app.router.add_post('/api/confirm-premium', handle_confirm_premium)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()
    print("Panel : http://localhost:8080 | Premium : http://localhost:8080/premium")

# ========================
# EVENTS DISCORD
# ========================

@client_discord.event
async def on_ready():
    await client_discord.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name="League of Legends | Challenger 🏆"),
        status=discord.Status.online
    )
    print(f"Bot connecté en tant que {client_discord.user}")

@client_discord.event
async def on_message(message):
    if message.author == client_discord.user:
        return
    live_messages.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "server": message.guild.name if message.guild else "DM",
        "channel": message.channel.name if hasattr(message.channel, 'name') else "DM",
        "author": message.author.display_name,
        "content": message.content[:200],
        "premium": is_premium(str(message.author.id))
    })
    if len(live_messages) > MAX_LIVE:
        live_messages.pop(0)
    if str(message.author.id) in blacklist:
        return
    if client_discord.user.mentioned_in(message):
        question = message.content.replace(f"<@{client_discord.user.id}>", "").replace(f"<@!{client_discord.user.id}>", "").strip()
        if not question:
            await message.channel.send("Tu m'as ping, mais t'as rien dit… typique d'un joueur Bronze 😅")
            return
        async with message.channel.typing():
            try:
                text, premium = await ask_groq(message.channel.id, message.author.display_name, question, message.author.id)
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
        text, premium = await ask_groq(interaction.channel_id, interaction.user.display_name, question, interaction.user.id)
        embed = discord.Embed(description=text, color=0xFFD700 if premium else 0x5865F2)
        embed.set_footer(text=f"{'👑 Premium' if premium else '🆓 Gratuit'} • {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send("⚠️ Erreur. Réessaie.")

@client_discord.tree.command(name="premium", description="S'abonner au premium")
async def premium_cmd(interaction: discord.Interaction):
    if is_premium(str(interaction.user.id)):
        embed = discord.Embed(title="👑 Tu es déjà Premium !", color=0xFFD700)
        embed.description = "Tu profites déjà de tous les avantages !"
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    embed = discord.Embed(title="👑 Passe Premium !", color=0xFFD700)
    embed.description = "**2,50€/mois** pour débloquer :\n✓ Mémoire 100 messages\n✓ IA Llama 70B\n✓ Toutes les personnalités\n✓ Rôle Premium 👑"
    embed.add_field(name="Lien de paiement", value="https://panel-admin.up.railway.app/premium")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client_discord.tree.command(name="reset", description="Efface la mémoire du bot")
async def reset(interaction: discord.Interaction):
    conversation_history[interaction.channel_id] = []
    await interaction.response.send_message("Mémoire effacée 🧹")

@client_discord.tree.command(name="status", description="Statut du bot")
async def bot_status(interaction: discord.Interaction):
    premium = is_premium(str(interaction.user.id))
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
    await interaction.response.send_message("🔐 Panel admin : https://panel-admin.up.railway.app", ephemeral=True)

# ========================
# LANCEMENT
# ========================

async def main():
    await start_web_server()
    await client_discord.start(DISCORD_TOKEN)

asyncio.run(main())
