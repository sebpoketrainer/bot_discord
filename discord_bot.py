import discord
import os
import string
from discord.ext import commands
import asyncio
from supabase import create_client
from dotenv import load_dotenv
import random
import asyncpg
import logging
from collections import defaultdict
from keep_alive import keep_alive
from datetime import datetime
import pytz

# Cargar las variables de entorno
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ID_CANAL_COMANDOS_RANKED = int(os.getenv("ID_CANAL_COMANDOS_RANKED", "0"))
ID_CANAL_TORNEOS = int(os.getenv("ID_CANAL_TORNEOS", "0"))

# Verificar que las variables de entorno fueron cargadas correctamente
if not all([TOKEN, SUPABASE_URL, SUPABASE_KEY]):
    print("ERROR: Las variables de entorno no están correctamente configuradas.")
    exit()

# Conectar a Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configurar los intents
intents = discord.Intents.default()
intents.message_content = True  # Permite leer el contenido de los mensajes
intents.guilds = True
intents.members = True
intents.messages = True
intents.reactions = True        # Permite manejar reacciones en los mensajes

# Crear una instancia del bot
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None) 
keep_alive()

# Evento para manejar comandos no reconocidos
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Comando desconocido. Usa `!ayuda` para ver la lista de comandos disponibles.")

def verificar_canal(ctx, canal_permitido_id: str):
    """Verifica si el comando se ejecuta en el canal permitido."""
    
    return ctx.channel.id == int(canal_permitido_id)

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

@bot.command()
async def ping(ctx):
    """Comando de prueba para verificar que el bot está funcionando."""
    print(f"Canal donde se ejecutó el comando: {ctx.channel.id} ({type(ctx.channel.id)})")
    print(f"ID_CANAL_COMANDOS_RANKED: {ID_CANAL_COMANDOS_RANKED} ({type(ID_CANAL_COMANDOS_RANKED)})")
    print(f"ID_CANAL_TORNEOS: {ID_CANAL_TORNEOS} ({type(ID_CANAL_TORNEOS)})")

    # Llamar a la función para verificar el canal
    if not (verificar_canal(ctx, ID_CANAL_COMANDOS_RANKED) or verificar_canal(ctx, ID_CANAL_TORNEOS)):
        await ctx.send("❌ Este comando solo puede ejecutarse en los canales permitidos.")
        return
    await ctx.send("Pong!")


@bot.command()
async def ayuda(ctx):
    # Llamar a la función para verificar el canal
    if not verificar_canal(ctx, ID_CANAL_COMANDOS_RANKED):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal comandos-ranked.")
        return
    help_message = """
¡Estoy aquí para ayudarte! Aquí tienes una lista de los comandos que puedo ejecutar:

**Comandos disponibles:**
1. !agregame: Te agrega a la base de datos.
2. !miperfil: Mostrar estadísticas de usuario.
3. !eliminar @usuario: Eliminar un usuario (solo admin).
4. !ranking: Mostrar el ranking de jugadores.
5. !partida @usuario: Crea una partida con el usuario etiquetado. Ambos jugadores deben confirmar la creación de la partida y tienen que reportar resutlados coherentes.

**Comandos para Admin:**
1. !eliminar @usuario: Eliminar un usuario
2. !reiniciar_ranking: Reinicia el ranking de todos los jugadores en la base de datos

**Reglas de asignación de puntos para las partidas:**
- El ganador recibe 3 puntos, el perdedor 0 puntos. En caso de empate, ambos jugadores reciben 1 punto.

Si necesitas más ayuda, ¡no dudes en preguntar!
"""

    await ctx.send(help_message)

# Comando para agregar un usuario
@bot.command()
async def agregame(ctx):
    # Llamar a la función para verificar el canal
    if not verificar_canal(ctx, ID_CANAL_COMANDOS_RANKED):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal comandos-ranked.")
        return
    try:
        discord_id = ctx.author.id  # ID único del usuario en Discord
        username = ctx.author.display_name  # Nombre visible en Discord

        # Verificar si el usuario ya existe
        existing_user_response = supabase.table("players").select("discord_id").eq("discord_id", discord_id).execute()

        if existing_user_response.data:
            await ctx.send(f"❌ El usuario '{username}' ya está registrado.")
            return

        # Agregar el nuevo usuario a la tabla "players" usando su Discord ID como clave primaria
        data = {"discord_id": discord_id, "username": username}
        response = supabase.table("players").insert(data).execute()

        if response.data:
            # Agregar los datos predeterminados a la tabla "scores"
            scores_data = {
                "player_id": discord_id,  # Ahora el Discord ID es la clave primaria
                "total_points": 0,
                "victories": 0,
                "draws": 0,
                "losses": 0
            }
            scores_response = supabase.table("scores").insert(scores_data).execute()

            if scores_response.data:
                await ctx.send(f"✅ Usuario {username} agregado con éxito y se le han asignado sus estadísticas iniciales.")
            else:
                await ctx.send("❌ Error al agregar estadísticas para el usuario.")
        else:
            await ctx.send("❌ Error al agregar usuario.")

    except Exception as e:
        await ctx.send(f"❌ Error, contáctate con el admin")

# Comando para obtener los datos de un usuario
@bot.command()
async def miperfil(ctx):
    # Llamar a la función para verificar el canal
    if not verificar_canal(ctx, ID_CANAL_COMANDOS_RANKED):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal comandos-ranked.")
        return
    try:
        discord_id = ctx.author.id  # Obtener el ID único de Discord del usuario

        # Buscar la información del usuario en la tabla "players"
        user_response = supabase.table("players").select("username").eq("discord_id", discord_id).execute()

        if not user_response.data:
            await ctx.send("❌ No estás registrado en la base de datos. Usa `!agregame` para registrarte.")
            return

        username = user_response.data[0]["username"]

        # Obtener los datos de la tabla "scores" utilizando `discord_id`
        scores_response = supabase.table("scores").select("total_points", "victories", "draws", "losses").eq("player_id", discord_id).execute()

        if scores_response.data:
            stats = scores_response.data[0]
            await ctx.send(f"👤 {username} tiene:\n\n🏆 {stats['victories']} victorias\n⚔️ {stats['draws']} empates\n💀 {stats['losses']} derrotas\n⭐ {stats['total_points']} puntos")
        else:
            await ctx.send("❌ No hay registros de puntuación para este usuario.")
    except Exception as e:
        await ctx.send(f"❌ Error, contáctate con el admin")


# Comando para eliminar un usuario
@bot.command()
async def eliminar(ctx, miembro: discord.Member):
    # Llamar a la función para verificar el canal
    if not verificar_canal(ctx, ID_CANAL_COMANDOS_RANKED):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal comandos-ranked.")
        return
    
    # Verificar si el autor del comando tiene el rol "Maestro Pokemon" o es administrador
    if not (any(role.name == "Maestro Pokemon" for role in ctx.author.roles) or ctx.author.guild_permissions.administrator):
        await ctx.send("❌ No tienes permiso para usar este comando.")
        return
    
    try:
        # Depuración: Mostrar los roles del autor
        roles_usuario = [role.name for role in ctx.author.roles]
        print(f"Roles del usuario: {roles_usuario}")

        discord_id = miembro.id  # Obtener el ID de Discord del usuario mencionado

        # Buscar el usuario en la tabla "players"
        user_response = supabase.table("players").select("username").eq("discord_id", discord_id).execute()

        if not user_response.data:
            await ctx.send("❌ No se encontró el usuario en la base de datos.")
            return

        username = user_response.data[0]["username"]

        # Eliminar el usuario de la tabla players
        delete_response = supabase.table("players").delete().eq("discord_id", discord_id).execute()

        if delete_response.data:
            await ctx.send(f"🗑️ Usuario {miembro.mention} ({username}) eliminado de la base de datos.")
        else:
            await ctx.send("❌ Error al eliminar usuario.")
    except Exception as e:
        await ctx.send(f"❌ Error, contáctate con el admin")


# Comando para retornar la lista de usuarios inscritos
@bot.command()
async def usuarios(ctx):
    # Llamar a la función para verificar el canal
    if not verificar_canal(ctx, ID_CANAL_COMANDOS_RANKED):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal comandos-ranked.")
        return
    try:
        # Obtener todos los usuarios de la tabla "players"
        response = supabase.table("players").select("discord_id", "username").execute()

        if response.data:
            # Si hay usuarios, enviamos el listado con un número correlativo empezando desde 1
            usuarios = [f"{i + 1} .- {player['username']}" for i, player in enumerate(response.data)]
            await ctx.send(f"📜 Lista de usuarios inscritos:\n" + "\n".join(usuarios))
        else:
            await ctx.send("❌ No hay usuarios inscritos.")
    
    except Exception as e:
        await ctx.send(f"❌ Error, contáctate con el admin")

# Comando para retornar el ranking de los jugadores
@bot.command()
async def ranking(ctx):
    # Llamar a la función para verificar el canal
    if not verificar_canal(ctx, ID_CANAL_COMANDOS_RANKED):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal comandos-ranked.")
        return
    try:
        # Obtener la tabla de scores ordenada por total_points de mayor a menor
        scores_response = supabase.table("scores").select("player_id", "total_points").order("total_points", desc=True).execute()

        if not scores_response.data:
            await ctx.send("❌ No hay datos en la tabla de rankings.")
            return

        # Obtener los discord_ids de los jugadores en el ranking
        player_ids = [score["player_id"] for score in scores_response.data]

        # Obtener los discord_ids de los jugadores
        players_response = supabase.table("players").select("discord_id", "username").in_("discord_id", player_ids).execute()

        if not players_response.data:
            await ctx.send("❌ No se encontraron jugadores en la tabla de players.")
            return

        # Crear un diccionario para mapear player_id a username
        players_dict = {player["discord_id"]: player["username"] for player in players_response.data}

        # Construir el ranking con formato "posición.- username: puntos" con separación de miles
        ranking_list = [
            f"{i + 1}.- {players_dict[score['player_id']]}: {score['total_points']:,} puntos"
            for i, score in enumerate(scores_response.data) if score["player_id"] in players_dict
        ]

        # Reemplazar comas con puntos para el formato de separación de miles
        ranking_list = [entry.replace(",", ".") for entry in ranking_list]

        # Enviar el mensaje con el ranking
        await ctx.send("🏆 **Ranking de jugadores:**\n" + "\n".join(ranking_list))

    except Exception as e:
        await ctx.send(f"❌ Error, contáctate con el admin")


@bot.command()
async def reiniciar_ranking(ctx):
    # Llamar a la función para verificar el canal
    if not verificar_canal(ctx, ID_CANAL_COMANDOS_RANKED):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal comandos-ranked.")
        return
    
    # Verificar si el autor del comando tiene el rol "Maestro Pokemon" o es administrador
    if not (any(role.name == "Maestro Pokemon" for role in ctx.author.roles) or ctx.author.guild_permissions.administrator):
        await ctx.send("❌ No tienes permiso para usar este comando.")
        return
    
    try:
        # Obtener la tabla de scores para obtener todos los player_id
        scores_response = supabase.table("scores").select("player_id").execute()

        if not scores_response.data:
            await ctx.send("❌ No hay jugadores en la tabla de scores.")
            return

        # Recorrer los jugadores y reiniciar los puntajes
        for score in scores_response.data:
            player_id = score["player_id"]
            
            # Actualizar el puntaje a cero (también podrías agregar otras variables a reiniciar)
            supabase.table("scores").update({
                "total_points": 0,  # Reiniciar puntos
                "victories": 0,     # Reiniciar victorias
                "losses": 0,          # Reiniciar derrotas
                "draws": 0           # Reiniciar empates
            }).eq("player_id", player_id).execute()

        await ctx.send("✅ El ranking ha sido reiniciado para todos los jugadores.")
    
    except Exception as e:
        await ctx.send(f"❌ Error al reiniciar el ranking: {e}")

### PARA EL REGISTRO DE PARTIDAS Y RANKING ###

# Función para generar un ID de partida aleatorio
async def generate_match_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

# Comando para generar un codigo de partida
@bot.command()
async def codigo(ctx):
    # Llamar a la función para verificar el canal
    if not verificar_canal(ctx, ID_CANAL_TORNEOS):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal torneos.")
        return
    
    match_id = await generate_match_id()  # Genera el código de partida
    await ctx.send("🔢 **El código de la sala es:**")
    await ctx.send(f"`{match_id}`") 

# Función para verificar si un jugador está en la base de datos
async def verificar_registro(discord_id):
    try:
        response = supabase.table("players").select("discord_id").eq("discord_id", discord_id).execute()
        return bool(response.data)  # Devuelve True si el jugador está registrado, False si no lo está
    except Exception as e:
        print(f"Error verificando registro: {e}")
        return False

@bot.command()
async def partida(ctx, rival: discord.User):
    # Llamar a la función para verificar el canal
    if not verificar_canal(ctx, ID_CANAL_COMANDOS_RANKED):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal comandos-ranked.")
        return
    
    jugador1_id = str(ctx.author.id)  # ID del jugador que ejecuta el comando
    jugador2_id = str(rival.id)    # ID del jugador mencionado
    
    # Validar si ambos jugadores están registrados
    if not await verificar_registro(jugador1_id) or not await verificar_registro(jugador2_id):
        await ctx.send("❌ Ambos jugadores deben estar registrados en la base de datos antes de crear una partida.")
        return
    
    try:
        # Verificar si el jugador ya tiene una partida abierta
        existing_match_response = supabase.table("matches").select("id").eq("status", "open").in_("player_id", [ctx.author.id, rival.id]).execute()
        if existing_match_response.data:
            await ctx.send("⚠️ Ya tienes una partida abierta con otro jugador.")
            return

        # Enviar mensaje de confirmación
        confirm_msg = await ctx.send(
            f"🔨 **¿Estás seguro de crear la partida entre {ctx.author.mention} y {rival.mention}?**\n"
            "Reaccionen con ✅ para confirmar o ❌ para cancelar.\n"
            "Tienen 3 minutos para reaccionar."
        )

        # Agregar reacciones al mensaje de confirmación
        for emoji in ["✅", "❌"]:
            await confirm_msg.add_reaction(emoji)

        # Diccionario para almacenar las reacciones de los jugadores
        reactions = {ctx.author.id: None, rival.id: None}

        # Definir la función de verificación de reacciones
        def check_confirm(reaction, user):
            return (
                reaction.message.id == confirm_msg.id  # Asegurarnos de que es el mensaje correcto
                and user.id in [ctx.author.id, rival.id]  # Solo permitir reacciones de los jugadores
                and str(reaction.emoji) in ["✅", "❌"]  # Solo reacciones válidas
            )

        # Esperar a que ambos jugadores reaccionen (tiempo máximo 3 minutos)
        try:
            while reactions[ctx.author.id] is None or reactions[rival.id] is None:
                reaction, user = await bot.wait_for("reaction_add", check=check_confirm, timeout=180)  # 180 segundos = 3 minutos
                reactions[user.id] = str(reaction.emoji)  # Almacenar la reacción del jugador

            # Si alguno de los jugadores cancela
            if reactions[ctx.author.id] == "❌" or reactions[rival.id] == "❌":
                await ctx.send("❌ La partida ha sido cancelada por uno de los jugadores.")
                return

            # Si ambos jugadores confirmaron
            if not (reactions[ctx.author.id] == "✅" and reactions[rival.id] == "✅"):
                return

        except asyncio.TimeoutError:
            await ctx.send("⏳ El tiempo de espera ha expirado. No se creó la partida.")
            return

        # Si uno de los jugadores cancela
        if reactions.get(ctx.author.id) == "❌" or reactions.get(rival.id) == "❌":
            return

        # Obtener el último ID utilizado en la tabla de partidas
        last_match_response = supabase.table("matches").select("id").order("id", desc=True).limit(1).execute()
        last_match_data = last_match_response.data

        # Determinar el nuevo ID de partida
        new_match_id = last_match_data[0]['id'] + 1 if last_match_data else 1

        # Generar un código de sala único
        match_id = await generate_match_id()

        # Insertar datos en la tabla de partidas
        data = [
            {
                "id": new_match_id,
                "player_id": ctx.author.id,
                "rival_id": rival.id,
                "status": "open",
                "win": False,
                "lose": False,
                "draw": False,
            },
        ]
        supabase.table("matches").insert(data).execute()

        # Para hacer que el bot espere 1 segundo
        await asyncio.sleep(1)

        # Mensaje con el código de la sala (separado)
        await ctx.send("🔢 **El código de la sala es:**")
        await ctx.send(f"`{match_id}`")  

        # Para hacer que el bot espere 1 segundo
        await asyncio.sleep(1) 

        # Mensaje con la información de la partida
        partida_msg = await ctx.send(
            f"🎮 **Partida creada entre {ctx.author.mention} y {rival.mention}!**\n"
            "Reacciona con:\n👍 para ganar\n\n👎 para perder\n\n🤝 para empate.\n"
            "Tienen 30 min. para reportar sus resultados"
        )

        # Agregar reacciones al mensaje
        for emoji in ["👍", "👎", "🤝"]:
            await partida_msg.add_reaction(emoji)

            # Función check para filtrar las reacciones
        def check_partida(reaction, user):
            return (
                reaction.message.id == partida_msg.id  # Asegurarnos de que es el mensaje correcto
                and user.id in [ctx.author.id, rival.id]  # Solo permitir reacciones de los jugadores
                and str(reaction.emoji) in ["👍", "👎", "🤝"]  # Solo reacciones válidas
        )

        # Esperar a que ambos jugadores reaccionen (tiempo máximo 30 minutos)
        try:
            await bot.wait_for("reaction_add", check=check_partida, timeout=1800)  # 1800 segundos = 30 minutos
        except asyncio.TimeoutError:
            await ctx.send("⏳ El tiempo de espera ha expirado. Se cerrará la partida sin ganadores.")
            supabase.table("matches").update({"status": "canceled"}).eq("id", new_match_id).execute()
            return


    except Exception as e:
        print(f"Error al crear la partida: {e}")
        await ctx.send("⚠️ Error al crear la partida. Inténtalo de nuevo más tarde.")

        
# Escuchar las reacciones al mensaje de la partida
match_reactions = {}

@bot.event
async def on_reaction_add(reaction, user):
    try:
        # Asegurarse de que la reacción no proviene de un bot
        if user.bot:
            return

        # Verificar si el mensaje de confirmación es el correcto
        if reaction.message.content and reaction.message.content.startswith("🔨 **¿Estás seguro de crear la partida"):
            # Asegurarse de que ambas personas reaccionen
            if reaction.emoji == "✅":
                await reaction.message.channel.send(f"✅ {user.mention} ha confirmado la partida.")
            elif reaction.emoji == "❌":
                await reaction.message.channel.send(f"❌ {user.mention} ha cancelado la partida.")
            return  # Si no es una partida abierta, no continuar


        elif reaction.message.content and reaction.message.content.startswith("🎮 **Partida creada entre"):

            # Buscar si ya existe una partida abierta entre el jugador y su rival
            match_response = supabase.table("matches").select("id", "player_id", "rival_id", "status", "win", "lose", "draw").eq("status", "open").eq("player_id", user.id).execute()

            if not match_response.data:
                match_response = supabase.table("matches").select("id", "player_id", "rival_id", "status", "win", "lose", "draw").eq("status", "open").eq("rival_id", user.id).execute()

            if not match_response.data:
                return

            # Si ya hay una partida abierta, se extraen los datos
            match_data = match_response.data[0]
            match_id = match_data["id"]
            player_id = match_data["player_id"]
            rival_id = match_data["rival_id"]

            # Si el usuario no es ni el jugador ni el rival, eliminar su reacción
            if user.id not in [player_id, rival_id]:
                await reaction.remove(user)
                return

            # Inicializar el diccionario de reacciones para la partida si no existe
            match_key = f"match_{player_id}_{rival_id}"
            if match_key not in match_reactions:
                match_reactions[match_key] = {}

            # Guardar la reacción del usuario en el diccionario
            match_reactions[match_key][user.id] = reaction.emoji

            print(f"DEBUG: Reacciones guardadas en match {match_key}: {match_reactions[match_key]}")

            # Esperar a que ambos jugadores reaccionen, sin importar el orden
            if len(match_reactions[match_key]) < 2:
                return  # No continuar si aún falta una reacción

            # Obtener las reacciones de ambos jugadores (sin importar el orden de las reacciones)
            player_reaction = match_reactions[match_key].get(player_id)
            rival_reaction = match_reactions[match_key].get(rival_id)

            # Validar reacciones coherentes
            print(f"DEBUG: Evaluando reacciones {player_reaction} vs {rival_reaction}")
            valid_results = [
                (player_reaction == "👍" and rival_reaction == "👎"),
                (player_reaction == "👎" and rival_reaction == "👍"),
                (player_reaction == "🤝" and rival_reaction == "🤝")
            ]

            if any(valid_results):
                # Actualizar resultados en la base de datos
                result = "win" if player_reaction == "👍" else "lose" if player_reaction == "👎" else "draw"
                print(f"DEBUG: Actualizando puntaje - {player_id} ({result}) vs {rival_id}")
                await actualizar_puntaje(player_id, rival_id, result, match_id)
                await reaction.message.channel.send(f"✅ Partida entre <@{player_id}> y <@{rival_id}> cerrada con éxito.")
                match_reactions[match_key].clear()

            else:
                await reaction.message.channel.send("⚠️ Los resultados no coinciden. Intenten nuevamente.")

    except Exception as e:
        print(f"Error al procesar la reacción: {e}")


async def actualizar_puntaje(player_id, rival_id, result, match_id):
    try:
        if result == "win":
            # Si el jugador ganó, incrementamos las victorias del jugador y las derrotas del rival
            player_response = supabase.table("scores").select("victories, total_points").eq("player_id", player_id).execute()
            if player_response.data:
                player_data = player_response.data[0]
                new_wins = int(player_data["victories"] + 1)
                new_points_player = int(player_data["total_points"] + 3)
            else:
                print(f"No se encontró datos para el jugador con ID: {player_id}")
                return

            rival_response = supabase.table("scores").select("losses").eq("player_id", rival_id).execute()
            if rival_response.data:
                rival_data = rival_response.data[0]
                new_losses = int(rival_data["losses"] + 1)
            else:
                print(f"No se encontró datos para el rival con ID: {rival_id}")
                return

            # Actualizar victorias del jugador
            supabase.table("scores").update({"victories": new_wins, "total_points": new_points_player}).eq("player_id", player_id).execute()
            # Actualizar derrotas del rival
            supabase.table("scores").update({"losses": new_losses}).eq("player_id", rival_id).execute()

            # Actualizar el resultado en la tabla de matches
            supabase.table("matches").update({"win": True}).eq("id", match_id).execute()

        elif result == "lose":
            # Si el jugador perdió, incrementamos las derrotas del jugador y las victorias del rival
            player_response = supabase.table("scores").select("losses").eq("player_id", player_id).execute()
            if player_response.data:
                player_data = player_response.data[0]
                new_losses = int(player_data["losses"] + 1)
            else:
                print(f"No se encontró datos para el jugador con ID: {player_id}")
                return

            rival_response = supabase.table("scores").select("victories, total_points").eq("player_id", rival_id).execute()
            if rival_response.data:
                rival_data = rival_response.data[0]
                new_wins = int(rival_data["victories"] + 1)
                new_points_rival = int(rival_data["total_points"] + 3)
            else:
                print(f"No se encontró datos para el rival con ID: {rival_id}")
                return

            # Actualizar derrotas del jugador
            supabase.table("scores").update({"losses": new_losses}).eq("player_id", player_id).execute()
            # Actualizar victorias del rival
            supabase.table("scores").update({"victories": new_wins, "total_points": new_points_rival}).eq("player_id", rival_id).execute()

            # Actualizar el resultado en la tabla de matches
            supabase.table("matches").update({"lose": True}).eq("id", match_id).execute()

        elif result == "draw":
            # Si es empate, ambos jugadores incrementan el empate
            player_response = supabase.table("scores").select("draws, total_points").eq("player_id", player_id).execute()
            if player_response.data:
                player_data = player_response.data[0]
                new_draws_player = int(player_data["draws"] + 1)
                new_points_player = int(player_data["total_points"] + 1)
            else:
                print(f"No se encontró datos para el jugador con ID: {player_id}")
                return

            rival_response = supabase.table("scores").select("draws, total_points").eq("player_id", rival_id).execute()
            if rival_response.data:
                rival_data = rival_response.data[0]
                new_draws_rival = int(rival_data["draws"] + 1)
                new_points_rival = int(rival_data["total_points"] + 1)
            else:
                print(f"No se encontró datos para el rival con ID: {rival_id}")
                return

            # Actualizar empates de ambos jugadores
            supabase.table("scores").update({"draws": new_draws_player, "total_points" : new_points_player}).eq("player_id", player_id).execute()
            supabase.table("scores").update({"draws": new_draws_rival, "total_points" : new_points_rival}).eq("player_id", rival_id).execute()

            # Actualizar el resultado en la tabla de matches
            supabase.table("matches").update({"draw": True}).eq("id", match_id).execute()

        print(f"DEBUG: Puntaje actualizado para {player_id} y {rival_id}.")
        # Cerrar la partida
        supabase.table("matches").update({"status": "closed"}).eq("id", match_id).execute()

    except Exception as e:
        print(f"Error al actualizar puntaje: {e}")


### PARA TORNEOS ###git remote add origin https://github.com/sebpoketrainer/bot_discord.git

# Diccionario para almacenar los jugadores registrados
tournament_players = []

def closest_power_of_2(n):
    """Encuentra la potencia de 2 más cercana que sea mayor o igual a n."""
    power = 1
    while power < n:
        power *= 2
    return power

@bot.command()
async def registrarse(ctx):
    """Registra a un jugador en el torneo, indicando su número en la lista."""
    if not verificar_canal(ctx, ID_CANAL_TORNEOS):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal torneos.")
        return
    
    if ctx.author.id not in tournament_players:
        tournament_players.append(ctx.author.id)
        position = len(tournament_players)  # Obtener el número en la lista
        await ctx.send(f"✅ {ctx.author.mention} ha sido registrado en el torneo como jugador #{position}.")
    else:
        await ctx.send(f"⚠️ {ctx.author.mention}, ya estás registrado en el torneo.")

@bot.command()
async def eliminar_participantes(ctx):
    """Elimina todos los jugadores registrados en el torneo."""
    if not verificar_canal(ctx, ID_CANAL_TORNEOS):
        await ctx.send("❌ Este comando solo puede ejecutarse en el canal torneos.")
        return
    
    # Verificar si el autor del comando tiene el rol "Maestro Pokemon" o es administrador
    if not (any(role.name == "Maestro Pokemon" for role in ctx.author.roles) or ctx.author.guild_permissions.administrator):
        await ctx.send("❌ No tienes permiso para usar este comando.")
        return

    global tournament_players
    
    # Limpiar la lista de jugadores registrados
    tournament_players.clear()
    
    await ctx.send("❌ Todos los jugadores han sido eliminados del torneo.")

@bot.command()
async def iniciar_torneo(ctx):
    """Inicia el torneo si hay suficientes jugadores registrados."""

    if not verificar_canal(ctx, ID_CANAL_TORNEOS):
       await ctx.send("❌ Este comando solo puede ejecutarse en el canal torneos.")
       return
    
    # Verificar si el autor del comando tiene el rol "Maestro Pokemon" o es administrador
    if not (any(role.name == "Maestro Pokemon" for role in ctx.author.roles) or ctx.author.guild_permissions.administrator):
        await ctx.send("❌ No tienes permiso para usar este comando.")
        return
    
    global tournament_players
    
    if len(tournament_players) < 4:
        await ctx.send("⚠️ Se necesitan al menos 4 jugadores para iniciar un torneo.")
        return
    
    # Determinar el tamaño del torneo
    total_players = len(tournament_players)
    tournament_size = closest_power_of_2(total_players)
    
    # Ordenar aleatoriamente los jugadores
    random.shuffle(tournament_players)
    
    # Si hay menos jugadores que el tamaño del torneo, algunos obtienen un BYE
    byes = tournament_size - total_players
    current_round = []
    
    for i in range(0, len(tournament_players), 2):
        if i + 1 < len(tournament_players):
            current_round.append((tournament_players[i], tournament_players[i+1]))
        else:
            current_round.append((tournament_players[i], None))  # BYE para este jugador
    
    await ctx.send(f"🎮 ¡El torneo ha comenzado con {len(tournament_players)} jugadores!")
    await play_round(ctx, current_round)

    # Después de terminar el torneo, reiniciar las colecciones
    tournament_players.clear()  # Limpiar la lista de jugadores registrados

def get_member(ctx, player):
    """Obtiene un objeto Member desde un ID o deja el objeto si ya lo es."""
    return ctx.guild.get_member(player) if isinstance(player, int) else player

async def play_round(ctx, matches):
    """Ejecuta una ronda del torneo con validación de ganador y perdedor en paralelo."""
    winners = []
    tasks = [asyncio.create_task(process_match(ctx, match, winners)) for match in matches]
    await asyncio.gather(*tasks)

    if len(winners) == 1:
        await ctx.send(f"🏆 ¡{winners[0].mention} es el campeón del torneo!")
    else:
        await ctx.send(f"⚡ Avanzan a la siguiente ronda: {', '.join([w.mention for w in winners])}")
        next_matches = [(winners[i], winners[i+1]) if i+1 < len(winners) else (winners[i], None) for i in range(0, len(winners), 2)]
        await play_round(ctx, next_matches)

async def process_match(ctx, match, winners):
    """Procesa un enfrentamiento individual."""
    player1, player2 = match
    player1 = get_member(ctx, player1)
    player2 = get_member(ctx, player2) if player2 else None
    
    if player2 is None:
        winners.append(player1)  # Gana automáticamente
        return

    match_msg = await ctx.send(f"⚔️ **{player1.mention} vs {player2.mention}** \n"
                               "Reacciona ✅ si ganas, y tu oponente debe confirmar con ❌.")

    await match_msg.add_reaction("✅")
    await match_msg.add_reaction("❌")

    reactions = {player1.id: None, player2.id: None}

    def check(reaction, user):
        return (
            reaction.message.id == match_msg.id and
            user.id in [player1.id, player2.id] and
            str(reaction.emoji) in ["✅", "❌"]
        )

    try:
        while None in reactions.values():
            reaction, user = await bot.wait_for("reaction_add", check=check, timeout=300)

            if user.id == player1.id and str(reaction.emoji) == "✅":
                reactions[player1.id] = "win"
            elif user.id == player2.id and str(reaction.emoji) == "❌":
                reactions[player2.id] = "lose"
            elif user.id == player2.id and str(reaction.emoji) == "✅":
                reactions[player2.id] = "win"
            elif user.id == player1.id and str(reaction.emoji) == "❌":
                reactions[player1.id] = "lose"

            if reactions[player1.id] == "win" and reactions[player2.id] == "lose":
                winners.append(player1)
                await ctx.send(f"✅ {player1.mention} gana contra {player2.mention}!")
                return
            elif reactions[player2.id] == "win" and reactions[player1.id] == "lose":
                winners.append(player2)
                await ctx.send(f"✅ {player2.mention} gana contra {player1.mention}!")
                return
            elif reactions[player1.id] == "win" and reactions[player2.id] == "win":
                await ctx.send("⚠️ Ambos jugadores dijeron que ganaron. Se necesita resolver el conflicto manualmente.")
                return
            elif reactions[player1.id] == "lose" and reactions[player2.id] == "lose":
                await ctx.send("⚠️ Ambos jugadores dijeron que perdieron. Se necesita resolver el conflicto manualmente.")
                return

    except asyncio.TimeoutError:
        await ctx.send(f"⏳ Nadie confirmó el resultado entre {player1.mention} y {player2.mention}. La partida queda sin resolución.")


# Iniciar el bot
bot.run(TOKEN)
