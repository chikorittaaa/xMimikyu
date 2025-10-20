import discord
from discord.ext import commands
import re

class ChannelLock(commands.Cog):
    """Cog for automatically locking channels when specific Pokémon spawn"""

    def __init__(self, bot):
        self.bot = bot
        self.monitor_bot_ids = [854233015475109888, 1131217949672353832]  # Bots to monitor for spawn messages
        self.target_bot_id = 716390085896962058       # Bot to lock out

        # Hardcoded list of Pokémon that trigger channel lock
        # Simply add names separated by commas (case-insensitive matching)
        locked_pokemon_list = """
            Umbrella Farfetch'd, Raincoat Grafaiai, Muddy Goomy, Foombrella, Cloubat
        """

        # Convert to lowercase set for case-insensitive matching
        self.locked_pokemon = {name.strip().lower() for name in locked_pokemon_list.split(',') if name.strip()}

        # Special Pokémon with custom images
        self.pokemon_images = {
            'muddy goomy': 'https://cdn.poketwo.net/images/50246.png',
            'foombrella': 'https://cdn.poketwo.net/images/50245.png'
        }

    @commands.Cog.listener()
    async def on_message(self, message):
        """Monitor messages for spawn patterns"""
        # Ignore bot's own messages
        if message.author.id == self.bot.user.id:
            return

        # Only process messages from the monitor bots
        if message.author.id not in self.monitor_bot_ids:
            return

        # Check if message matches the spawn pattern
        # Pattern: "Name: percentage%"
        pattern = r'^(.+?):\s*(\d+\.?\d*)%'
        match = re.search(pattern, message.content, re.MULTILINE)

        if match:
            pokemon_name = match.group(1).strip()
            percentage = match.group(2)

            # Check if this Pokémon is in the locked list (case-insensitive)
            if pokemon_name.lower() in self.locked_pokemon:
                try:
                    # Try to get the target bot member object (the one to lock out)
                    target_bot = message.guild.get_member(self.target_bot_id)

                    # If not in cache, try to fetch it
                    if not target_bot:
                        try:
                            target_bot = await message.guild.fetch_member(self.target_bot_id)
                        except discord.NotFound:
                            print(f'Target bot {self.target_bot_id} not found in guild {message.guild.name}')
                            return
                        except discord.HTTPException as e:
                            print(f'Error fetching target bot: {e}')
                            return

                    # Remove send messages and view channel permissions from target bot
                    await message.channel.set_permissions(
                        target_bot,
                        send_messages=False,
                        view_channel=False,
                        reason=f'Auto-lock triggered by spawn: {pokemon_name}'
                    )

                    # Send confirmation message
                    lock_embed = discord.Embed(
                        title='🔒 Channel Locked',
                        description=f'Channel locked due to **{pokemon_name}** spawn ({percentage}%)',
                        color=discord.Color.red()
                    )
                    lock_embed.set_footer(text='Use unlock command to restore permissions')

                    # Add thumbnail image if this Pokémon has a special image
                    pokemon_lower = pokemon_name.lower()
                    if pokemon_lower in self.pokemon_images:
                        lock_embed.set_thumbnail(url=self.pokemon_images[pokemon_lower])

                    await message.channel.send(embed=lock_embed)
                    print(f'Locked channel {message.channel.name} for {pokemon_name}')

                except discord.Forbidden:
                    print(f'Missing permissions to lock channel {message.channel.name}')
                except Exception as e:
                    print(f'Error locking channel: {e}')

    @commands.hybrid_command(name='unlock', description='Restore permissions for the target bot in this channel')
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx):
        """Manually unlock a channel by restoring bot permissions"""
        try:
            target_bot = ctx.guild.get_member(self.target_bot_id)

            # If not in cache, try to fetch it
            if not target_bot:
                try:
                    target_bot = await ctx.guild.fetch_member(self.target_bot_id)
                except discord.NotFound:
                    await ctx.reply(f'❌ Target bot not found in this server.', mention_author=False)
                    return

            # Restore permissions
            await ctx.channel.set_permissions(
                target_bot,
                send_messages=None,  # Reset to default/role permissions
                view_channel=None,
                reason=f'Manual unlock by {ctx.author}'
            )

            unlock_embed = discord.Embed(
                title='🔓 Channel Unlocked',
                description='Bot permissions have been restored in this channel.',
                color=discord.Color.green()
            )

            await ctx.reply(embed=unlock_embed, mention_author=False)
            print(f'Unlocked channel {ctx.channel.name} by {ctx.author}')

        except discord.Forbidden:
            await ctx.reply('❌ Missing permissions to unlock this channel.', mention_author=False)
        except Exception as e:
            await ctx.reply(f'❌ Error unlocking channel: {e}', mention_author=False)

    @unlock.error
    async def unlock_error(self, ctx, error):
        """Handle permission errors for unlock command"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply('❌ You need **Manage Channels** permission to use this command.', mention_author=False)

async def setup(bot):
    await bot.add_cog(ChannelLock(bot))
