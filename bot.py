# ============================================================
#  BOT DISCORD IA — GÉNÉRATEUR DE SERVEUR PAR PROMPT
#  Modèle IA : Groq (100% gratuit)
#  Commande  : !creer <description de ton serveur>
#  Exemple   : !creer Un serveur gaming Valorant et CS2
# ============================================================

import discord
from discord.ext import commands
import os
import json
from groq import Groq
from dotenv import load_dotenv
from keep_alive import keep_alive

# ── Chargement des variables d'environnement ────────────────
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY  = os.getenv('GROQ_API_KEY')

# ── Client Groq ──────────────────────────────────────────────
groq_client = Groq(api_key=GROQ_API_KEY)

# ── Intents Discord ──────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ============================================================
#  PROMPT SYSTÈME ENVOYÉ À GROQ
# ============================================================
SYSTEM_PROMPT = """Tu es un architecte expert de serveurs Discord.
L'utilisateur décrit le type de serveur qu'il veut créer.
Tu dois générer UNIQUEMENT un objet JSON valide, sans markdown, sans explication, sans texte autour.

Le JSON doit respecter EXACTEMENT ce schéma :

{
  "roles": [
    {
      "name": "string",
      "color_rgb": [int, int, int],
      "hoist": true,
      "mentionable": true,
      "level": "admin" | "moderator" | "member"
    }
  ],
  "categories": [
    {
      "name": "string (avec emoji pertinent, ex: 🎮-GAMING)",
      "staff_only": false,
      "channels": [
        {
          "name": "string (minuscules, tirets, ex: gaming-general)",
          "type": "text" | "voice",
          "topic": "string (description courte du salon)",
          "readonly": false,
          "slowmode": 0,
          "user_limit": 0,
          "staff_only": false
        }
      ]
    }
  ]
}

Règles strictes :
- Crée entre 3 et 6 catégories adaptées au thème décrit
- Chaque catégorie contient entre 2 et 5 salons (mix texte + vocal pertinent)
- Toujours inclure exactement 1 rôle level "admin", 1 "moderator", 1 "member"
- Les noms de salons : minuscules, tirets uniquement, pas d'espaces ni emojis
- Les catégories STAFF doivent avoir staff_only: true
- readonly: true uniquement sur les salons d'annonces officielles
- slowmode en secondes (0 = désactivé, 3 = lent, 10 = très lent)
- user_limit pour les vocaux (0 = illimité)
- Réponds UNIQUEMENT avec le JSON brut, rien d'autre, absolument rien d'autre"""

# ============================================================
#  MAPPING : niveau du rôle → permissions Discord
# ============================================================
def get_permissions_for_level(level: str) -> discord.Permissions:
    if level == "admin":
        return discord.Permissions(administrator=True)
    elif level == "moderator":
        return discord.Permissions(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
            kick_members=True,
            ban_members=True,
            mute_members=True,
            deafen_members=True,
            move_members=True,
            embed_links=True,
            attach_files=True,
            add_reactions=True,
            manage_nicknames=True,
            connect=True,
            speak=True,
        )
    else:  # member
        return discord.Permissions(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            embed_links=True,
            attach_files=True,
            add_reactions=True,
            connect=True,
            speak=True,
            change_nickname=True,
        )

# ============================================================
#  CONSTRUCTION DES OVERWRITES DE PERMISSIONS
# ============================================================
def build_overwrites(staff_only: bool, readonly: bool,
                     everyone, role_member, role_mod, role_admin) -> dict:
    ow = {
        everyone: discord.PermissionOverwrite(
            view_channel=False, send_messages=False
        )
    }

    if role_admin:
        ow[role_admin] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True,
            connect=True, speak=True
        )

    if staff_only:
        if role_mod:
            ow[role_mod] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                connect=True, speak=True
            )
    else:
        if role_mod:
            ow[role_mod] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                connect=True, speak=True
            )
        if role_member:
            if readonly:
                ow[role_member] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=False,
                    connect=True, speak=False
                )
            else:
                ow[role_member] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    connect=True, speak=True
                )
    return ow

# ============================================================
#  ÉVÉNEMENT : BOT PRÊT
# ============================================================
@bot.event
async def on_ready():
    print(f'✅ Connecté : {bot.user}')
    print(f'📡 Sur {len(bot.guilds)} serveur(s)')
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name='!creer <description> pour générer un serveur'
        )
    )

# ============================================================
#  COMMANDE : !creer <prompt>
# ============================================================
@bot.command(name='creer')
@commands.has_permissions(administrator=True)
async def creer(ctx, *, prompt: str):

    guild = ctx.guild
    msg = await ctx.send(
        f"🤖 **L'IA analyse votre demande...**\n"
        f"```\n{prompt}\n```"
    )

    # ── Étape 1 : appel à Groq ───────────────────────────────
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.3,       # Peu de créativité pour rester précis
            max_tokens=2048,
        )
        raw_json = response.choices[0].message.content.strip()

        # Nettoyage au cas où Groq aurait ajouté des balises markdown
        if raw_json.startswith("```"):
            raw_json = raw_json.strip("`")
            if raw_json.lower().startswith("json"):
                raw_json = raw_json[4:]
            raw_json = raw_json.strip()

        server_data = json.loads(raw_json)

    except json.JSONDecodeError as e:
        await msg.edit(
            content=f"❌ L'IA a retourné un JSON invalide : `{e}`\n"
                    f"Réessaie avec une description différente."
        )
        return
    except Exception as e:
        await msg.edit(content=f"❌ Erreur API Groq : `{e}`")
        return

    await msg.edit(content="✅ Structure générée ! Nettoyage du serveur...")

    # ── Étape 2 : nettoyage du serveur ───────────────────────
    for channel in guild.channels:
        if channel.id != ctx.channel.id:
            try:
                await channel.delete(reason="Génération IA — nettoyage")
            except discord.Forbidden:
                pass

    for role in guild.roles:
        if not role.is_default() and not role.managed:
            try:
                await role.delete(reason="Génération IA — nettoyage")
            except discord.Forbidden:
                pass

    await guild.default_role.edit(permissions=discord.Permissions.none())

    # ── Étape 3 : création des rôles ─────────────────────────
    await msg.edit(content="🎭 Création des rôles...")

    created_roles = {}
    level_to_role = {}

    for role_data in server_data.get("roles", []):
        r, g, b = role_data.get("color_rgb", [88, 101, 242])
        level   = role_data.get("level", "member")

        new_role = await guild.create_role(
            name=role_data["name"],
            color=discord.Color.from_rgb(r, g, b),
            permissions=get_permissions_for_level(level),
            hoist=role_data.get("hoist", True),
            mentionable=role_data.get("mentionable", True),
            reason="Génération IA"
        )
        created_roles[role_data["name"]] = new_role
        level_to_role[level] = new_role

    # Attribution du rôle Admin à l'auteur de la commande
    if "admin" in level_to_role:
        await ctx.author.add_roles(
            level_to_role["admin"],
            reason="Génération IA — attribution Admin"
        )

    everyone    = guild.default_role
    role_admin  = level_to_role.get("admin")
    role_mod    = level_to_role.get("moderator")
    role_member = level_to_role.get("member")

    # ── Étape 4 : création des catégories et salons ──────────
    for i, cat_data in enumerate(server_data.get("categories", [])):
        cat_name  = cat_data.get("name", f"Catégorie {i+1}")
        cat_staff = cat_data.get("staff_only", False)

        await msg.edit(content=f"📂 Création de **{cat_name}**...")

        cat_ow = build_overwrites(
            cat_staff, False,
            everyone, role_member, role_mod, role_admin
        )
        category = await guild.create_category(
            name=cat_name,
            position=i,
            overwrites=cat_ow,
            reason="Génération IA"
        )

        for ch_data in cat_data.get("channels", []):
            ch_staff   = ch_data.get("staff_only", cat_staff)
            ch_readonly = ch_data.get("readonly", False)
            ch_type    = ch_data.get("type", "text")

            ch_ow = build_overwrites(
                ch_staff, ch_readonly,
                everyone, role_member, role_mod, role_admin
            )

            if ch_type == "voice":
                await guild.create_voice_channel(
                    name=ch_data["name"],
                    category=category,
                    overwrites=ch_ow,
                    user_limit=ch_data.get("user_limit", 0),
                    reason="Génération IA"
                )
            else:
                await guild.create_text_channel(
                    name=ch_data["name"],
                    category=category,
                    overwrites=ch_ow,
                    topic=ch_data.get("topic", ""),
                    slowmode_delay=ch_data.get("slowmode", 0),
                    reason="Génération IA"
                )

    # ── Étape 5 : confirmation finale ────────────────────────
    roles_str = "\n".join([f"• {name}" for name in created_roles.keys()])
    cats_str  = "\n".join([
        f"• {c.get('name', '?')} ({len(c.get('channels', []))} salons)"
        for c in server_data.get("categories", [])
    ])

    embed = discord.Embed(
        title="✅ Serveur généré par l'IA !",
        color=discord.Color.green(),
        description=f"Basé sur votre prompt :\n> *{prompt}*"
    )
    embed.add_field(name="🎭 Rôles créés",       value=roles_str, inline=True)
    embed.add_field(name="📂 Catégories créées",  value=cats_str,  inline=True)
    embed.set_footer(text="Généré par Groq (Llama 3.3) • !creer pour relancer")

    await msg.edit(content=None, embed=embed)


# ============================================================
#  GESTION DES ERREURS
# ============================================================
@creer.error
async def creer_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ **Usage :** `!creer <description>`\n"
            "**Exemple :** `!creer Un serveur gaming Valorant et CS2`"
        )
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu dois être **administrateur** pour utiliser cette commande.")
    else:
        await ctx.send(f"❌ Erreur : `{error}`")


# ============================================================
#  LANCEMENT
# ============================================================
keep_alive()
bot.run(DISCORD_TOKEN)
