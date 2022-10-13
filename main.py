#!/bin/python3

from http.client import ResponseNotReady
import discord
from discord.ext import tasks, commands

import openai
import os
import jsons
import traceback
import gtts

# Local modules
import brain.memory as ai_memory


class AISettings:
    before: str = "Respond to"
    after: str = ""
    model: str = "text-davinci-002"
    max_tokens: int = 256
    temp: float = 1.0
    channel_id: int = -1
    announcement: str = "Hello! @everyone"


# Globals
intents = discord.Intents().all()
bot: commands.Bot = commands.Bot(command_prefix='?', intents=intents)
talk_to_self = False

config_folder = "config"
config_path = "config/config.json"

memory_folder = "memories"
local_mem_path = f"{memory_folder}/local.json"
convo_mem_path = f"{memory_folder}/convo.json"

#
# Inputs
#
voice_channel: discord.VoiceChannel = None
voice_client: discord.VoiceClient = None
tts_lang = "en"


#
# Helpers
#
def validate_path(path):
    if not os.path.exists(path):
        os.mkdir(path)


#
# Brain
#
brain_path = f"{config_folder}/brain.json"


class Brain:
    user_memory: dict[int, ai_memory.Memory] = {}
    guild_memory: dict[int, dict[int, ai_memory.Memory]] = {}

    user_settings: dict[int, AISettings] = {}
    guild_settings: dict[int, AISettings] = {}

    def write(self):
        json = jsons.dumps(self, jdkwargs={"indent": 4})
        validate_path(config_folder)
        with open(brain_path, "w") as f:
            f.write(json)

    def remember_user(self, user: int, what: str):
        if user not in self.user_memory:
            self.user_memory[user] = ai_memory.Memory()

        self.user_memory[user].what = what
        print(f"USER MEMORY: {user} = {what}")

    def remember_guild(self, guild: int, user: int, what: str):
        if guild not in self.guild_memory:
            self.guild_memory[guild] = {}

        if user not in brain.guild_memory[guild]:
            self.guild_memory[guild][user] = ai_memory.Memory()

        self.guild_memory[guild][user].what = what
        print(f"GUILD MEMORY: {guild} -> {user} = {what}")

    def remember(self, guild: int | None, user: int, what: str):
        if guild is None:
            self.remember_user(user, what)
        else:
            self.remember_guild(guild, user, what)

    def recall(self, guild: int | None, user: int) -> ai_memory.Memory | None:
        if guild is None:
            if user in self.user_memory:
                return self.user_memory[user]
        else:
            if guild in self.guild_memory:
                if user in self.guild_memory[guild]:
                    return self.guild_memory[guild][user]

        return None

    def get_settings(self, lookup: int, is_guild: bool) -> AISettings:
        if not is_guild:
            if lookup not in self.user_settings:
                self.user_settings[lookup] = AISettings()

            return self.user_settings[lookup]
        else:
            if lookup not in self.guild_settings:
                self.guild_settings[lookup] = AISettings()

            return self.guild_settings[lookup]

    def set_settings(self, lookup: int, is_guild: bool, settings: AISettings):
        if not is_guild:
            self.user_settings[lookup] = settings
        else:
            self.guild_settings[lookup] = settings

    def ask_openai_raw(self, prompt : str, model : str, max_tokens : int, temp : float):
        return openai.Completion.create(
            engine=model,
            max_tokens=max_tokens,
            temperature=temp,

            prompt=prompt,
        ).to_dict()

    def ask_openai(self, lookup: int, is_guild: bool, prompt: str) -> str:
        settings = self.get_settings(lookup, is_guild)

        completion = self.ask_openai_raw(prompt, settings.model, settings.max_tokens, settings.temp)

        responses = ""
        for choice in completion["choices"]:
            responses += choice.text

        return responses


    async def send_ann(self, content : str, embed : discord.Embed):
        global bot

        for guild in bot.guilds:
            if guild.id in self.guild_settings:
                settings = self.guild_settings[guild.id]
    
                if settings.channel_id != -1:
                    ann = guild.get_channel(settings.channel_id)
    
                    if ann is not None:
                        await ann.send(content, embed=embed)


# More globals
brain: Brain = Brain()
testing_mode = "TESTING_MODE" in os.environ



@bot.event
async def on_ready():
    global bot
    global brain

    print('CLIENT: Logged in as bot user %s' % bot.user.name)

    for guild in bot.guilds:
        print(f"CLIENT: In server '{guild.name}'")

    validate_path(config_folder)

    if os.path.exists(brain_path):
        with open(brain_path, "r") as f:
            raw = f.read()
            brain = jsons.loads(raw, Brain)

    action = "the world burn"

    if testing_mode:
        action = "TESTING MODE!"

    embed = discord.Embed(title="Online", description="")
    embed.color = discord.Color.from_rgb(67, 160, 71)

    #await brain.send_ann("", embed)

    completion = brain.ask_openai_raw("Complete the phrase 'Watching'", "text-davinci-002", 128, 1.0)
    responses = ""
    for choice in completion["choices"]:
        responses += choice.text

    responses = responses.strip()
    responses = responses.replace('"', '')
    responses = responses.replace("'", '')
    responses = responses.removeprefix("Watching")
    responses = responses.removeprefix("Watcing")
    responses = responses.removeprefix("watching")
    responses = responses.removeprefix("watcing")

    print(f"CLIENT: Status = {responses}")

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=responses), status=discord.Status.online)


@bot.event
async def on_message(message: discord.Message):
    global brain

    await bot.process_commands(message)

    if message.content.startswith("?"):
        return

    try:
        is_dm = (message.channel.type is discord.ChannelType.private and message.author.id != bot.user.id)
        is_reply = False
        is_self = False
        is_guild = message.guild is not None

        guild_id = None
        lookup = message.author.id

        if message.guild is not None:
            guild_id = message.guild.id
            lookup = guild_id

        predicate = ""
        if message.reference is not None:
            msg = message.reference.resolved
            is_reply = message.reference.resolved.author.id == bot.user.id

            if is_reply:
                predicate = f"Remember, you last said '{msg.content}'\n"
        else:
            mem = brain.recall(guild_id, message.author.id)

            if mem is not None:
                predicate = mem.get_memory()

        if talk_to_self:
            is_self = True

        if f"{bot.user.id}" in message.content or is_dm or is_reply or is_self:
            # We need to sanitize the mention of the bot
            mention_self = f"<@{bot.user.id}>"
            sanitized_message = message.content.replace(mention_self, "")
            sanitized_message = sanitized_message.strip()

            settings = brain.get_settings(lookup, is_guild)
            prompt = f"{predicate}{settings.before} '{sanitized_message}' {settings.after}"

            print(f"SELF: {mention_self}")

            if message.guild is not None:
                print(f"GUILD: {message.guild} ({message.guild.id})")
            else:
                print("IS A DM!")

            print(f"ASKER: {message.author.name}")
            print(f"OPENAI: Responding to {message.content}")
            print(f"SANITIZED: {sanitized_message}")
            print(f"PROMPT: {prompt}")

            # We find every mention in the message beforehand
            # TODO

            raw_response = brain.ask_openai(lookup, is_guild, prompt)
            response = raw_response.strip()

            print(f"RESPONSE: {response}")
            await message.reply(response, mention_author=True)

            if voice_channel is not None and voice_client is not None:
                if os.path.exists("temp.mp3"):
                    os.remove("temp.mp3")

                if voice_client.is_playing():
                    voice_client.stop()

                tts_reply = f"Hey {message.author.name}, {response}"
                tts = gtts.gTTS(text=tts_reply, lang=tts_lang, slow=False)
                tts.save("temp.mp3")

                voice_client.play(discord.FFmpegPCMAudio("temp.mp3"))

            brain.remember(guild_id, message.author.id, response)
            print("\n")

            if testing_mode:
                embed = discord.Embed(title="Context", description="")
                embed.color = discord.Color.from_rgb(255, 138, 101)

                embed.add_field(name="Self", value=mention_self, inline=False)
                embed.add_field(name="Guild", value=message.guild, inline=False)
                embed.add_field(name="Asker", value=message.author, inline=False)

                await message.reply(embed=embed)

                embed = discord.Embed(title="AI IO", description="")
                embed.color = discord.Color.from_rgb(255, 138, 101)

                embed.add_field(name="Input", value=prompt, inline=False)
                embed.add_field(name="Output", value=response, inline=False)

                await message.channel.send(embed=embed)

                embed = discord.Embed(title="Prompt Composure", description="")
                embed.color = discord.Color.from_rgb(255, 138, 101)

                if predicate:
                    embed.add_field(name="Predicate", value=predicate, inline=False)

                if settings.before:
                    embed.add_field(name="Before", value=settings.before, inline=False)

                embed.add_field(name="Content", value=message.content, inline=False)

                if settings.after:
                    embed.add_field(name="After", value=settings.after, inline=False)

                await message.channel.send(embed=embed)

                embed = discord.Embed(title="Raw Info", description="")
                embed.color = discord.Color.from_rgb(255, 138, 101)

                embed.add_field(name="AI Settings", value=jsons.dumps(settings, jdkwargs={"indent": 4}), inline=False)
                embed.add_field(name="Is DM?", value=is_dm)
                embed.add_field(name="Is Reply", value=is_reply)
                embed.add_field(name="Is Self?", value=is_self)

                await message.channel.send(embed=embed)
    except Exception as e:
        tb = traceback.format_exc()
        await message.channel.send(f"ERROR!\n\n{tb}")

    # We update configs per message
    brain.write()


@bot.event
async def on_member_join(member):
    pass


@bot.event
async def on_member_remove(member):
    pass


@bot.event
async def on_member_ban(guild, user):
    pass


@bot.event
async def on_member_unban(guild, user):
    pass


@bot.event
async def on_reaction_remove(reaction, user):
    pass


# @bot.command()
async def harass(ctx, member: discord.Member):
    await ctx.send(f"Harassing {member.name}!")

    await member.send("你是一个白痴")
    await member.send("我想杀你!")
    await member.send("-1000 社会信用 😐👎")


def get_lookup(ctx: commands.Context) -> int:
    if ctx.guild is None:
        return ctx.author.id
    else:
        return ctx.guild.id


@bot.command()
@commands.has_permissions(administrator=True)
async def set_model(ctx, mdl):
    lookup = get_lookup(ctx)
    settings = brain.get_settings(lookup, ctx.guild is not None)
    settings.model = mdl
    brain.set_settings(lookup, ctx.guild is not None, settings)

    await ctx.send(f"Set OpenAI model to {settings.model}")


@bot.command()
async def set_temp(ctx, tmp):
    lookup = get_lookup(ctx)
    settings = brain.get_settings(lookup, ctx.guild is not None)
    settings.temp = max(0.0, min(float(tmp), 1.0))
    brain.set_settings(lookup, ctx.guild is not None, settings)

    await ctx.send(f"Set OpenAI temp to {settings.temp}")


@bot.command()
async def set_before(ctx, b4):
    lookup = get_lookup(ctx)
    settings = brain.get_settings(lookup, ctx.guild is not None)
    settings.before = b4
    brain.set_settings(lookup, ctx.guild is not None, settings)

    await ctx.send(f"Set OpenAI prompt 'before' to {settings.before}")


@bot.command()
async def set_after(ctx, aft):
    lookup = get_lookup(ctx)
    settings = brain.get_settings(lookup, ctx.guild is not None)
    settings.after = aft
    brain.set_settings(lookup, ctx.guild is not None, settings)

    await ctx.send(f"Set OpenAI prompt 'after' to {settings.after}")


@bot.command()
@commands.has_permissions(administrator=True)
async def set_ann(ctx, channel: int):
    lookup = get_lookup(ctx)

    if ctx.guild is None:
        await ctx.send("Announcements don't work in DMs!")
        return

    settings = brain.get_settings(lookup, ctx.guild is not None)
    settings.channel_id = channel

    brain.set_settings(lookup, ctx.guild is not None, settings)

    await ctx.send(f"Set 'ann' channel to <#{channel}>")


@bot.command()
@commands.has_permissions(administrator=True)
async def reset(ctx):
    lookup = get_lookup(ctx)
    brain.set_settings(lookup, ctx.guild is not None, AISettings())
    await ctx.send(f"Reset settings...")

    if ctx.guild is not None:
        brain.guild_memory[ctx.guild.id] = {}
    else:
        brain.remember(None, ctx.message.author.id, "")


@bot.command()
@commands.has_permissions(administrator=True)
async def debug_reload(ctx):
    await ctx.send("Reloading bot module...")
    await bot.close()


@bot.command()
async def set_t2s(ctx, t: bool):
    global talk_to_self
    talk_to_self = t
    await ctx.send(f"Set T2S to {talk_to_self}")


@bot.command()
async def skip(ctx):
    if voice_channel is not None:
        if voice_client.is_playing():
            voice_client.stop()


@bot.command()
async def set_lang(ctx, lang):
    global tts_lang
    tts_lang = lang
    await ctx.send(f"Set OpenAI TTS lang to {lang}")


@bot.command()
async def join_vc(ctx: commands.Context, id: int):
    global voice_channel
    global voice_client

    voice_channel = ctx.guild.get_channel(id)
    voice_client = await voice_channel.connect()


@bot.command()
async def list_oai_engines(ctx: commands.Context):
    engines = openai.Engine.list()

    embed = discord.Embed(title="OpenAI Info", description="")
    embed.color = discord.Color.from_rgb(255, 138, 101)

    engine_str = ""
    for engine in engines.data:
        engine_str += f"{engine.id}\n"

    embed.add_field(name="Models", value=engine_str, inline=False)
    await ctx.message.reply(embed=embed, mention_author=True)


@bot.command()
async def forget(ctx: commands.Context):
    guild_id = None

    if ctx.guild is not None:
        guild_id = ctx.guild.id

    brain.remember(guild_id, ctx.author.id, "")
    await ctx.send("Cleared memory...")


@bot.command()
@commands.has_permissions(administrator=True)
async def dump_brain(ctx: commands.Context):
    await ctx.message.reply(file=discord.File(brain_path))


def run_bot():
    try:
        key = open("openai_key.txt", "r").readline()
        openai.api_key = key

    except Exception as e:
        print(e)

    try:
        token = open("token.txt", "r").readline()
        bot.run(token)
    except Exception as e:
        print(e)


run_bot()