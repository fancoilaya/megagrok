# bot/commands/growmygrok.py

from discord.ext import commands
import db
import evolutions

async def grow_command_logic(ctx, base_xp: int = 10):
    # THE LOGIC GOES HERE
    # I will paste the full growmygrok implementation after this step. 
    pass


def setup(bot):
    @bot.command(name="growmygrok")
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def growmygrok(ctx, base_xp: int = 10):
        await grow_command_logic(ctx, base_xp)
