import discord
from discord.ext import tasks, commands

import openai
import os
import subprocess
import jsons

# Globals
intents = discord.Intents().default()
intents.members = True
intents.message_content = True

bot: commands.Bot = commands.Bot(command_prefix='?', intents=intents)


class OAI_Input:
    before: str = "Respond to"
    after: str = ""
    model: str = "text-davinci-002"
    max_tokens: int = 256
    temp: float = 1.0


oai_input: OAI_Input = OAI_Input()

testing_mode = "TESTING_MODE" in os.environ

if testing_mode:
    print("TESTING MODE ACTIVE!")

contact_openai = not testing_mode


def ask_openai(prompt):
    global oai_input

    completion = openai.Completion.create(
        engine=oai_input.model,
        max_tokens=oai_input.max_tokens,
        temperature=oai_input.temp,

        prompt=prompt,
    ).to_dict()

    responses = ""
    for choice in completion["choices"]:
        responses += choice.text

    return responses


@bot.event
async def on_ready():
    global bot
    print('CLIENT: Logged in as bot user %s' % bot.user.name)

    for guild in bot.guilds:
        print(f"CLIENT: In server '{guild.name}'")


@bot.event
async def on_message(message: discord.Message):
    global oai_input

    try:
        is_dm = (message.channel.type is discord.ChannelType.private and message.author.id != bot.user.id)
        is_reply = False

        predicate = ""
        if message.reference is not None:
            msg = message.reference.resolved
            is_reply = message.reference.resolved.author.id == bot.user.id

            if is_reply:
                predicate = f"Remember, you last said \"{msg.content}\"\n\n"

        if f"{bot.user.id}" in message.content or is_dm or is_reply:
            # We need to sanitize the mention of the bot
            mention_self = f"<@{bot.user.id}>"
            sanitized_message = message.content.replace(mention_self, "")
            sanitized_message = sanitized_message.strip()

            prompt = f"{predicate}{oai_input.before} '{sanitized_message}' {oai_input.after}"

            print(f"SELF: {mention_self}")
            print(f"GUILD: {message.guild} ({message.guild.id})")
            print(f"ASKER: {message.author.name}")
            print(f"OPENAI: Responding to {message.content}")
            print(f"SANITIZED: {sanitized_message}")
            print(f"PROMPT: {prompt}")

            # We find every mention in the message beforehand
            # TODO

            if contact_openai:
                raw_response = ask_openai(prompt)
                response = raw_response.strip()

                print(f"RESPONSE: {response}")
                await message.reply(response, mention_author=True)

                print("\n")
            else:
                embed = discord.Embed(title="Debug Info", description="")
                embed.color = discord.Color.from_rgb(255, 138, 101)

                embed.add_field(name="Self", value=mention_self, inline=False)
                embed.add_field(name="Guild", value=message.guild, inline=False)
                embed.add_field(name="Asker", value=message.author, inline=False)
                embed.add_field(name="Sanitized Input", value=sanitized_message, inline=False)
                embed.add_field(name="Prompt", value=prompt, inline=False)
                embed.add_field(name="OpenAI Input", value=jsons.dumps(oai_input, jdkwargs={"indent": 4}), inline=False)

                await message.channel.send(embed=embed)
    except Exception as e:
        await message.channel.send(f"ERROR!\n\n{e}")


    await bot.process_commands(message)


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
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    if reaction.emoji == "👍" and reaction.message.author == bot.user:
        try:
            response = ask_openai(f"Succinctly thank {user.name}")
            response.strip()

            await reaction.message.channel.send(response)
        except Exception as e:
            print(f"ERROR: {e}")


@bot.event
async def on_reaction_remove(reaction, user):
    pass


# @bot.command()
async def harass(ctx, member: discord.Member):
    await ctx.send(f"Harassing {member.name}!")

    await member.send("你是一个白痴")
    await member.send("我想杀你!")
    await member.send("-1000 社会信用 😐👎")


@bot.command()
async def set_model(ctx, mdl):
    global model
    model = mdl
    await ctx.send(f"Set OpenAI model to {model}")


@bot.command()
async def set_temp(ctx, tmp):
    global oai_input
    oai_input.temp = max(0.0, min(float(tmp), 1.0))
    await ctx.send(f"Set OpenAI temp to {oai_input.temp}")


@bot.command()
async def set_before(ctx, b4):
    global oai_input
    oai_input.before = b4
    await ctx.send(f"Set OpenAI prompt 'before' to {oai_input.before}")


@bot.command()
async def set_after(ctx, aft):
    global oai_input
    oai_input.after = aft
    await ctx.send(f"Set OpenAI prompt 'after' to {oai_input.after}")


@bot.command()
async def reload(ctx):
    await ctx.send("Reloading bot module...")
    await bot.close()


def run_bot():
    try:
        key = open("openai_key.txt", "r").readline()
        openai.api_key = key

        engines = openai.Engine.list()

        print("OPENAI: Listing available OpenAI engines")
        for engine in engines.data:
            print(engine.id)
        print("OPENAI: End of listing")

    except Exception as e:
        print(e)


    try:
        token = open("token.txt", "r").readline()
        bot.run(token)
    except Exception as e:
        print(e)