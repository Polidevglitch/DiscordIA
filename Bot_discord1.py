import discord
from discord import app_commands
from groq import AsyncGroq
import os
from dotenv import load_dotenv
from aiohttp import web
import asyncio
import json
from datetime import datetime

load_dotenv(r"C:/Users/benoi/Documents/.env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ID = 1314677631609733131
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "admin")

if not GROQ_API_KEY or not DISCORD_TOKEN:
    raise ValueError("Les variables d'environnement GROQ_API_KEY et DISCORD_TOKEN sont requises.")

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

current_personality = "LoL Arrogant"  # personnalité active par défaut

conversation_history = {}
blacklist = set()
MAX_HISTORY = 20
live_messages = []  # messages en temps réel
MAX_LIVE = 200      # garder les 200 derniers

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
            {"role": "system", "content": personalities[current_personality]},
            *conversation_history[channel_id]
        ]
    )
    text = response.choices[0].message.content

    conversation_history[channel_id].append({
        "role": "assistant",
        "content": text
    })

    return text
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

# ========================
# PANEL WEB ADMIN
# ========================

HTML_PANEL = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Panel Admin - Mec_IA</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', sans-serif; }
  .sidebar { width: 220px; background: #161b22; height: 100vh; position: fixed; padding: 20px; border-right: 1px solid #30363d; }
  .sidebar h2 { color: #5865F2; font-size: 18px; margin-bottom: 30px; }
  .sidebar a { display: block; color: #8b949e; padding: 10px; border-radius: 8px; text-decoration: none; margin-bottom: 5px; }
  .sidebar a:hover, .sidebar a.active { background: #21262d; color: #e6edf3; }
  .main { margin-left: 220px; padding: 30px; }
  h1 { font-size: 24px; margin-bottom: 20px; color: #e6edf3; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
  .card h3 { color: #8b949e; font-size: 13px; text-transform: uppercase; margin-bottom: 10px; }
  .card .value { font-size: 28px; font-weight: bold; color: #5865F2; }
  .section { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
  .section h2 { margin-bottom: 15px; font-size: 16px; }
  input, select, textarea { width: 100%; background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 10px; border-radius: 8px; margin-bottom: 10px; font-size: 14px; }
  button { background: #5865F2; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 14px; }
  button:hover { background: #4752c4; }
  button.red { background: #da3633; }
  button.red:hover { background: #b91c1c; }
  button.green { background: #238636; }
  button.green:hover { background: #1a6828; }
  .msg-feed { height: 400px; overflow-y: auto; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 15px; font-size: 13px; }
  .msg { padding: 6px 0; border-bottom: 1px solid #21262d; }
  .msg .time { color: #484f58; font-size: 11px; }
  .msg .server { color: #5865F2; font-weight: bold; }
  .msg .channel { color: #8b949e; }
  .msg .author { color: #3fb950; }
  .msg .content { color: #e6edf3; margin-top: 2px; }
  .blacklist-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  .blacklist-item { background: #21262d; padding: 5px 12px; border-radius: 20px; font-size: 13px; display: flex; align-items: center; gap: 8px; }
  .blacklist-item button { background: #da3633; padding: 2px 8px; font-size: 11px; }
  .memory-list { max-height: 300px; overflow-y: auto; }
  .memory-item { background: #0d1117; padding: 10px; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
  .tab { display: none; }
  .tab.active { display: block; }
  .nav-tabs { display: flex; gap: 10px; margin-bottom: 20px; }
  .nav-tab { background: #21262d; border: 1px solid #30363d; color: #8b949e; padding: 8px 16px; border-radius: 8px; cursor: pointer; }
  .nav-tab.active { background: #5865F2; color: white; border-color: #5865F2; }
  .alert { padding: 10px 15px; border-radius: 8px; margin-bottom: 15px; display: none; }
  .alert.success { background: #1a3a2a; border: 1px solid #238636; color: #3fb950; }
  .alert.error { background: #3a1a1a; border: 1px solid #da3633; color: #f85149; }
</style>
</head>
<body>

<div class="sidebar">
  <h2>🎮 Mec_IA Admin</h2>
  <a href="#" class="active" onclick="showTab('dashboard')">📊 Dashboard</a>
  <a href="#" onclick="showTab('messages')">💬 Messages live</a>
  <a href="#" onclick="showTab('moderation')">🔨 Modération</a>
  <a href="#" onclick="showTab('broadcast')">📢 Broadcast</a>
  <a href="#" onclick="showTab('memory')">🧠 Mémoire</a>
  <a href="#" onclick="showTab('settings')">⚙️ Paramètres</a>
</div>

<div class="main">
  <div id="alert" class="alert"></div>

  <!-- DASHBOARD -->
  <div id="tab-dashboard" class="tab active">
    <h1>📊 Dashboard</h1>
    <div class="grid">
      <div class="card"><h3>Serveurs</h3><div class="value" id="stat-guilds">...</div></div>
      <div class="card"><h3>Utilisateurs</h3><div class="value" id="stat-users">...</div></div>
      <div class="card"><h3>Channels en mémoire</h3><div class="value" id="stat-memory">...</div></div>
      <div class="card"><h3>Blacklistés</h3><div class="value" id="stat-blacklist">...</div></div>
    </div>
    <div class="section">
      <h2>🖥️ Serveurs connectés</h2>
      <div id="guilds-list"></div>
    </div>
  </div>

  <!-- MESSAGES LIVE -->
  <div id="tab-messages" class="tab">
    <h1>💬 Messages en temps réel</h1>
    <div class="section">
      <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
        <span style="color:#8b949e; font-size:13px;">Tous les serveurs • Auto-refresh 3s</span>
        <button onclick="clearFeed()" class="red" style="padding:5px 12px; font-size:12px;">Vider</button>
      </div>
      <div class="msg-feed" id="msg-feed"></div>
    </div>
  </div>

  <!-- MODERATION -->
  <div id="tab-moderation" class="tab">
    <h1>🔨 Modération</h1>
    <div class="grid">
      <div class="section">
        <h2>👢 Kick</h2>
        <input type="text" id="kick-guild" placeholder="ID du serveur">
        <input type="text" id="kick-user" placeholder="ID de l'utilisateur">
        <input type="text" id="kick-reason" placeholder="Raison (optionnel)">
        <button onclick="doAction('kick')">Kick</button>
      </div>
      <div class="section">
        <h2>🔨 Ban</h2>
        <input type="text" id="ban-guild" placeholder="ID du serveur">
        <input type="text" id="ban-user" placeholder="ID de l'utilisateur">
        <input type="text" id="ban-reason" placeholder="Raison (optionnel)">
        <button class="red" onclick="doAction('ban')">Ban</button>
      </div>
      <div class="section">
        <h2>🔇 Mute (timeout)</h2>
        <input type="text" id="mute-guild" placeholder="ID du serveur">
        <input type="text" id="mute-user" placeholder="ID de l'utilisateur">
        <input type="number" id="mute-duration" placeholder="Durée en minutes">
        <button onclick="doAction('mute')">Mute</button>
      </div>
    </div>
    <div class="section">
      <h2>🚫 Blacklist bot</h2>
      <p style="color:#8b949e; font-size:13px; margin-bottom:10px;">Empêche un utilisateur d'utiliser le bot</p>
      <div style="display:flex; gap:10px;">
        <input type="text" id="blacklist-user" placeholder="ID de l'utilisateur" style="margin:0;">
        <button onclick="addBlacklist()" style="white-space:nowrap;">Ajouter</button>
      </div>
      <div class="blacklist-list" id="blacklist-list"></div>
    </div>
  </div>

  <!-- BROADCAST -->
  <div id="tab-broadcast" class="tab">
    <h1>📢 Broadcast</h1>
    <div class="section">
      <h2>Envoyer un message dans un channel</h2>
      <input type="text" id="bc-channel" placeholder="ID du channel">
      <textarea id="bc-message" rows="4" placeholder="Ton message..."></textarea>
      <button class="green" onclick="sendBroadcast()">Envoyer</button>
    </div>
    <div class="section">
      <h2>⚙️ Changer le status du bot</h2>
      <select id="status-type">
        <option value="playing">🎮 Playing</option>
        <option value="watching">👀 Watching</option>
        <option value="listening">🎵 Listening</option>
        <option value="competing">🏆 Competing</option>
      </select>
      <input type="text" id="status-text" placeholder="Texte du status">
      <button onclick="changeStatus()">Changer</button>
    </div>
  </div>

  <!-- MEMORY -->
  <div id="tab-memory" class="tab">
    <h1>🧠 Mémoire des conversations</h1>
    <div class="section">
      <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
        <span style="color:#8b949e;">Historique par channel</span>
        <button class="red" onclick="resetAllMemory()">Tout effacer</button>
      </div>
      <div class="memory-list" id="memory-list"></div>
    </div>
  </div>

  <!-- SETTINGS -->
  <div id="tab-settings" class="tab">
    <h1>⚙️ Personnalités</h1>

    <div class="section">
      <h2>🎭 Personnalité active</h2>
      <div id="personality-switcher" style="display:flex; flex-wrap:wrap; gap:10px; margin-bottom:15px;"></div>
      <p style="color:#8b949e; font-size:13px;">Personnalité active : <span id="current-personality" style="color:#5865F2; font-weight:bold;"></span></p>
    </div>

    <div class="section">
      <h2>✏️ Créer / Modifier une personnalité</h2>
      <input type="text" id="personality-name" placeholder="Nom de la personnalité">
      <textarea id="personality-text" rows="8" placeholder="Contenu de la personnalité..."></textarea>
      <div style="display:flex; gap:10px;">
        <button onclick="savePersonality()" class="green">Sauvegarder</button>
        <button onclick="deletePersonality()" class="red">Supprimer</button>
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
}

function showAlert(msg, type) {
  const el = document.getElementById('alert');
  el.textContent = msg;
  el.className = 'alert ' + type;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 3000);
}

async function loadDashboard() {
  const r = await fetch('/api/stats');
  const d = await r.json();
  document.getElementById('stat-guilds').textContent = d.guilds;
  document.getElementById('stat-users').textContent = d.users;
  document.getElementById('stat-memory').textContent = d.memory_channels;
  document.getElementById('stat-blacklist').textContent = d.blacklist;
  const gl = document.getElementById('guilds-list');
  gl.innerHTML = d.guild_list.map(g => `
    <div style="display:flex; justify-content:space-between; padding:10px; background:#0d1117; border-radius:8px; margin-bottom:8px;">
      <span>${g.name}</span>
      <span style="color:#8b949e;">${g.members} membres • ID: ${g.id}</span>
    </div>
  `).join('');
}

async function loadMemory() {
  const r = await fetch('/api/memory');
  const d = await r.json();
  const el = document.getElementById('memory-list');
  if (Object.keys(d).length === 0) {
    el.innerHTML = '<p style="color:#8b949e;">Aucune mémoire active</p>';
    return;
  }
  el.innerHTML = Object.entries(d).map(([cid, msgs]) => `
    <div class="memory-item">
      <span>Channel <code>${cid}</code> — ${msgs} messages</span>
      <button class="red" onclick="resetMemory('${cid}')" style="padding:5px 10px; font-size:12px;">Effacer</button>
    </div>
  `).join('');
}

async function loadBlacklist() {
  const r = await fetch('/api/blacklist');
  const d = await r.json();
  const el = document.getElementById('blacklist-list');
  el.innerHTML = d.map(uid => `
    <div class="blacklist-item">
      <span>${uid}</span>
      <button onclick="removeBlacklist('${uid}')">✕</button>
    </div>
  `).join('');
}

async function doAction(action) {
  const guild = document.getElementById(action + '-guild').value;
  const user = document.getElementById(action + '-user').value;
  const extra = action === 'mute'
    ? document.getElementById('mute-duration').value
    : document.getElementById(action + '-reason').value;
  const r = await fetch('/api/moderation', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ action, guild_id: guild, user_id: user, extra })
  });
  const d = await r.json();
  showAlert(d.message, d.success ? 'success' : 'error');
}

async function addBlacklist() {
  const uid = document.getElementById('blacklist-user').value;
  await fetch('/api/blacklist/add', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ user_id: uid })
  });
  document.getElementById('blacklist-user').value = '';
  loadBlacklist();
  showAlert('Utilisateur blacklisté', 'success');
}

async function removeBlacklist(uid) {
  await fetch('/api/blacklist/remove', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ user_id: uid })
  });
  loadBlacklist();
}

async function sendBroadcast() {
  const channel = document.getElementById('bc-channel').value;
  const message = document.getElementById('bc-message').value;
  const r = await fetch('/api/broadcast', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ channel_id: channel, message })
  });
  const d = await r.json();
  showAlert(d.message, d.success ? 'success' : 'error');
}

async function changeStatus() {
  const type = document.getElementById('status-type').value;
  const text = document.getElementById('status-text').value;
  const r = await fetch('/api/status', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ type, text })
  });
  const d = await r.json();
  showAlert(d.message, d.success ? 'success' : 'error');
}

async function resetMemory(channel_id) {
  await fetch('/api/memory/reset', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ channel_id })
  });
  loadMemory();
  showAlert('Mémoire effacée', 'success');
}

async function resetAllMemory() {
  await fetch('/api/memory/reset-all', { method: 'POST' });
  loadMemory();
  showAlert('Toute la mémoire effacée', 'success');
}

async function loadPersonality() {
  const r = await fetch('/api/personality');
  const d = await r.json();
  document.getElementById('current-personality').textContent = d.current;

  const switcher = document.getElementById('personality-switcher');
  switcher.innerHTML = Object.keys(d.personalities).map(name => `
    <button onclick="switchPersonality('${name}')"
      style="${name === d.current ? 'background:#238636;' : ''}"
      onmouseover="previewPersonality('${name}', this.dataset.text)"
      data-text="${d.personalities[name].replace(/"/g, '&quot;')}"
    >${name}</button>
  `).join('');
}

async function switchPersonality(name) {
  const r = await fetch('/api/personality', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ switch: name })
  });
  const d = await r.json();
  showAlert(d.message, d.success ? 'success' : 'error');
  loadPersonality();
}

function previewPersonality(name, text) {
  document.getElementById('personality-name').value = name;
  document.getElementById('personality-text').value = text;
}

async function savePersonality() {
  const name = document.getElementById('personality-name').value;
  const text = document.getElementById('personality-text').value;
  if (!name || !text) { showAlert('Remplis le nom et le contenu', 'error'); return; }
  const r = await fetch('/api/personality', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ name, text })
  });
  const d = await r.json();
  showAlert(d.message, d.success ? 'success' : 'error');
  loadPersonality();
}

async function deletePersonality() {
  const name = document.getElementById('personality-name').value;
  if (!name) { showAlert('Sélectionne une personnalité', 'error'); return; }
  const r = await fetch('/api/personality', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ delete: name })
  });
  const d = await r.json();
  showAlert(d.message, d.success ? 'success' : 'error');
  loadPersonality();
}
function clearFeed() { feedMessages = []; renderFeed(); }

function renderFeed() {
  const el = document.getElementById('msg-feed');
  const wasAtBottom = el.scrollHeight - el.clientHeight <= el.scrollTop + 50;
  el.innerHTML = feedMessages.slice(-100).reverse().map(m => `
    <div class="msg">
      <span class="time">${m.time}</span>
      <span class="server"> [${m.server}]</span>
      <span class="channel"> #${m.channel}</span>
      <span class="author"> ${m.author}:</span>
      <div class="content">${m.content}</div>
    </div>
  `).join('');
  if (wasAtBottom) el.scrollTop = 0;
}

async function pollMessages() {
  try {
    const r = await fetch('/api/live-messages');
    const d = await r.json();
    feedMessages = d;
    if (currentTab === 'messages') renderFeed();
  } catch(e) {}
  setTimeout(pollMessages, 3000);
}

// Init
loadDashboard();
loadPersonality();
pollMessages();
</script>
</body>
</html>
"""

# ========================
# ROUTES API
# ========================

async def handle_panel(request):
    import base64
    auth = request.headers.get('Authorization', '')
    expected = base64.b64encode(f"admin:{PANEL_PASSWORD}".encode()).decode()
    if auth != f'Basic {expected}':
        return web.Response(
            status=401,
            headers={'WWW-Authenticate': 'Basic realm="Admin Panel"'},
            text='Accès refusé'
        )
    return web.Response(text=HTML_PANEL, content_type='text/html')

async def handle_stats(request):
    guilds = client_discord.guilds
    total_users = sum(g.member_count for g in guilds)
    return web.json_response({
        "guilds": len(guilds),
        "users": total_users,
        "memory_channels": len(conversation_history),
        "blacklist": len(blacklist),
        "guild_list": [{"id": str(g.id), "name": g.name, "members": g.member_count} for g in guilds]
    })

async def handle_live_messages(request):
    return web.json_response(live_messages[-100:])

async def handle_memory(request):
    return web.json_response({str(k): len(v) for k, v in conversation_history.items()})

async def handle_memory_reset(request):
    data = await request.json()
    cid = int(data["channel_id"])
    conversation_history.pop(cid, None)
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
            return web.json_response({"success": True, "message": f"{member.name} a été kick ✅"})
        elif data["action"] == "ban":
            await member.ban(reason=data.get("extra", "Panel admin"))
            return web.json_response({"success": True, "message": f"{member.name} a été banni ✅"})
        elif data["action"] == "mute":
            duration = int(data.get("extra", 10))
            until = discord.utils.utcnow() + discord.utils.datetime.timedelta(minutes=duration)
            await member.timeout(until, reason="Panel admin")
            return web.json_response({"success": True, "message": f"{member.name} muté {duration} min ✅"})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})

async def handle_status(request):
    data = await request.json()
    types = {
        "playing": discord.ActivityType.playing,
        "watching": discord.ActivityType.watching,
        "listening": discord.ActivityType.listening,
        "competing": discord.ActivityType.competing,
    }
    try:
        await client_discord.change_presence(
            activity=discord.Activity(type=types[data["type"]], name=data["text"])
        )
        return web.json_response({"success": True, "message": "Status changé ✅"})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})
async def handle_personality_get(request):
    return web.json_response({
        "current": current_personality,
        "personalities": {k: v for k, v in personalities.items()}
    })

async def handle_personality_post(request):
    global current_personality, personalities
    data = await request.json()
    if "switch" in data:
        if data["switch"] in personalities:
            current_personality = data["switch"]
            return web.json_response({"success": True, "message": f"Personnalité changée : {current_personality} ✅"})
    if "name" in data and "text" in data:
        personalities[data["name"]] = data["text"]
        return web.json_response({"success": True, "message": f"Personnalité '{data['name']}' sauvegardée ✅"})
    if "delete" in data:
        if data["delete"] in personalities and data["delete"] != current_personality:
            del personalities[data["delete"]]
            return web.json_response({"success": True, "message": "Personnalité supprimée ✅"})
        return web.json_response({"success": False, "message": "Impossible de supprimer la personnalité active"})
    return web.json_response({"success": False, "message": "Requête invalide"})
#les routes API de personnalité
async def handle_personality_post(request):
    global personality
    data = await request.json()
    personality = data["personality"]
    return web.json_response({"success": True, "message": "Personnalité mise à jour ✅"})

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_panel)
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

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("Panel admin disponible sur http://localhost:8080")

# ========================
# EVENTS DISCORD
# ========================

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

@client_discord.event
async def on_message(message):
    if message.author == client_discord.user:
        return

    # Log tous les messages pour le panel live
    live_messages.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "server": message.guild.name if message.guild else "DM",
        "channel": message.channel.name if hasattr(message.channel, 'name') else "DM",
        "author": message.author.display_name,
        "content": message.content[:200]
    })
    if len(live_messages) > MAX_LIVE:
        live_messages.pop(0)

    # Blacklist check
    if str(message.author.id) in blacklist:
        return

    if client_discord.user.mentioned_in(message):
        question = message.content
        question = question.replace(f"<@{client_discord.user.id}>", "").replace(f"<@!{client_discord.user.id}>", "").strip()

        if not question:
            await message.channel.send("Tu m'as ping, mais t'as rien dit… typique d'un joueur Bronze 🤓")
            return

        async with message.channel.typing():
            try:
                text = await ask_groq(message.channel.id, message.author.display_name, question)
                for part in split_message(text):
                    await message.channel.send(part)
            except Exception as e:
                print("Erreur Groq :", e)
                await message.channel.send("⚠️ L'IA est en cooldown. Réessaie dans quelques secondes.")

# ========================
# COMMANDES SLASH
# ========================

@client_discord.tree.command(name="ask", description="Pose une question au bot LoL")
@app_commands.describe(question="Ta question")
async def ask(interaction: discord.Interaction, question: str):
    if str(interaction.user.id) in blacklist:
        await interaction.response.send_message("❌ Tu es blacklisté.", ephemeral=True)
        return
    await interaction.response.defer()
    try:
        text = await ask_groq(interaction.channel_id, interaction.user.display_name, question)
        embed = discord.Embed(description=text, color=0x5865F2)
        embed.set_footer(text=f"Demandé par {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send("⚠️ Erreur. Réessaie.")

@client_discord.tree.command(name="reset", description="Efface la mémoire du bot dans ce channel")
async def reset(interaction: discord.Interaction):
    conversation_history[interaction.channel_id] = []
    await interaction.response.send_message("Mémoire effacée 🧹")

@client_discord.tree.command(name="status", description="Statut du bot")
async def status(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Statut du bot", color=0x5865F2)
    embed.add_field(name="Modèle IA", value="Llama 3.3 70B (Groq)", inline=True)
    embed.add_field(name="Messages en mémoire", value=f"{len(conversation_history.get(interaction.channel_id, []))}/{MAX_HISTORY}", inline=True)
    embed.add_field(name="Ping", value=f"{round(client_discord.latency * 1000)}ms", inline=True)
    await interaction.response.send_message(embed=embed)

@client_discord.tree.command(name="admin", description="Lien vers le panel admin")
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
