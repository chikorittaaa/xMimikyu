import discord
from discord.ext import commands
from discord import app_commands
import csv
import re
from typing import List, Dict, Optional
from config import EMBED_COLOR

class DetailsView(discord.ui.View):
    """View with a Details button to show full quest breakdown"""

    def __init__(self, details_embed, timeout=180):
        super().__init__(timeout=timeout)
        self.details_embed = details_embed

    @discord.ui.button(label='Details', style=discord.ButtonStyle.primary, emoji='📖')
    async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=self.details_embed, ephemeral=True)

class PokemonQuestHelper(commands.Cog):
    """Cog for suggesting Pokémon based on event quests"""

    def __init__(self, bot):
        self.bot = bot
        self.pokemon_data = {}
        self.spawn_rates = {}
        self.gender_data = {'male': set(), 'female': set(), 'genderless': set()}
        self.load_data()

    def load_data(self):
        """Load Pokémon data and spawn rates from CSV files"""
        try:
            # Load pokemondata.csv (tab-separated)
            with open('pokemondata.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    dex = int(row['Dex'])
                    self.pokemon_data[dex] = {
                        'name': row['Name'],
                        'type1': row['Type 1'],
                        'type2': row['Type 2'].strip() if row['Type 2'].strip() else None,
                        'dex': dex,
                        'region': self.get_region(dex)
                    }

            # Load spawnrates.csv (comma-separated)
            with open('spawnrates.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dex = int(row['Dex'])
                    self.spawn_rates[dex] = row['Chance']

            # Load gender data
            for gender_type in ['male', 'female', 'genderless']:
                try:
                    with open(f'{gender_type}.csv', 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row:
                                self.gender_data[gender_type].add(row['name'].strip())
                except FileNotFoundError:
                    print(f'Warning: {gender_type}.csv not found')

            print(f'Loaded {len(self.pokemon_data)} Pokémon and {len(self.spawn_rates)} spawn rates')
            print(f'Loaded gender data: {len(self.gender_data["male"])} male, {len(self.gender_data["female"])} female, {len(self.gender_data["genderless"])} genderless')
        except Exception as e:
            print(f'Error loading Pokémon data: {e}')

    def get_region(self, dex: int) -> str:
        """Get region based on Dex number"""
        if 1 <= dex <= 151:
            return 'Kanto'
        elif 152 <= dex <= 251:
            return 'Johto'
        elif 252 <= dex <= 386:
            return 'Hoenn'
        elif 387 <= dex <= 493:
            return 'Sinnoh'
        elif 494 <= dex <= 649:
            return 'Unova'
        elif 650 <= dex <= 721:
            return 'Kalos'
        elif 722 <= dex <= 809:
            return 'Alola'
        elif 810 <= dex <= 905:
            return 'Galar'
        elif 906 <= dex <= 1025:
            return 'Paldea'
        return 'Unknown'

    def parse_quest(self, quest_text: str) -> Optional[Dict]:
        """Parse a quest line to extract requirements"""
        # Check for gender quests
        gender_quest = None
        if 'male' in quest_text.lower() and 'female' not in quest_text.lower():
            gender_quest = 'male'
        elif 'female' in quest_text.lower():
            gender_quest = 'female'
        elif 'unknown gender' in quest_text.lower() or 'genderless' in quest_text.lower():
            gender_quest = 'genderless'

        # Skip breeding quests
        if 'breed' in quest_text.lower():
            return None

        # Extract quest details using regex
        quest_info = {
            'text': quest_text,
            'region': None,
            'type': None,
            'count': 0,
            'gender': gender_quest
        }

        # Extract count
        count_match = re.search(r'Catch (\d+)', quest_text)
        if count_match:
            quest_info['count'] = int(count_match.group(1))

        # If it's a gender quest, return it
        if gender_quest:
            return quest_info

        # Extract region
        regions = ['Kanto', 'Johto', 'Hoenn', 'Sinnoh', 'Unova', 'Kalos', 'Alola', 'Galar', 'Paldea']
        for region in regions:
            if region in quest_text:
                quest_info['region'] = region
                break

        # Extract type (look for common type patterns)
        types = ['Normal', 'Fire', 'Water', 'Grass', 'Electric', 'Ice', 'Fighting', 'Poison', 
                'Ground', 'Flying', 'Psychic', 'Bug', 'Rock', 'Ghost', 'Dragon', 'Dark', 
                'Steel', 'Fairy']
        for ptype in types:
            if ptype.lower() in quest_text.lower() or f'{ptype}-type' in quest_text:
                quest_info['type'] = ptype
                break

        # Skip generic catch quests (no region or type specified)
        if not quest_info['region'] and not quest_info['type']:
            return None

        return quest_info

    def find_matching_pokemon(self, quest_info: Dict, limit: int = 2) -> List[Dict]:
        """Find Pokémon matching the quest criteria"""
        matches = []

        # Handle gender quests
        if quest_info.get('gender'):
            gender = quest_info['gender']
            gender_pokemon = self.gender_data.get(gender, set())

            # Priority order for spawn rates
            spawn_priorities = ['1/225', '1/337', '1/674']

            for priority in spawn_priorities:
                if len(matches) >= limit:
                    break

                for dex, data in self.pokemon_data.items():
                    if len(matches) >= limit:
                        break

                    # Skip if already in matches
                    if any(m['dex'] == dex for m in matches):
                        continue

                    # Check if Pokémon is in gender list and has spawn rate
                    if data['name'] in gender_pokemon and dex in self.spawn_rates and self.spawn_rates[dex] == priority:
                        matches.append({**data, 'spawn_rate': self.spawn_rates[dex]})

            return matches[:limit]

        # Priority order for spawn rates
        spawn_priorities = ['1/225', '1/337', '1/674']

        for priority in spawn_priorities:
            if len(matches) >= limit:
                break

            for dex, data in self.pokemon_data.items():
                if len(matches) >= limit:
                    break

                # Skip if already in matches
                if any(m['dex'] == dex for m in matches):
                    continue

                # Skip if no spawn rate data
                if dex not in self.spawn_rates or self.spawn_rates[dex] != priority:
                    continue

                # Check matching criteria
                region_match = not quest_info['region'] or data['region'] == quest_info['region']
                type_match = not quest_info['type'] or (
                    data['type1'] == quest_info['type'] or 
                    data['type2'] == quest_info['type']
                )

                # Priority: both match > type match > region match
                if quest_info['region'] and quest_info['type']:
                    if region_match and type_match:
                        matches.append({**data, 'spawn_rate': self.spawn_rates[dex]})
                elif quest_info['type']:
                    if type_match:
                        matches.append({**data, 'spawn_rate': self.spawn_rates[dex]})
                elif quest_info['region']:
                    if region_match:
                        matches.append({**data, 'spawn_rate': self.spawn_rates[dex]})

        return matches[:limit]

    def format_pokemon_info(self, pokemon: Dict) -> str:
        """Format Pokémon information for display"""
        types = pokemon['type1']
        if pokemon['type2']:
            types += f"/{pokemon['type2']}"

        return f"→ **{pokemon['name']}** (#{pokemon['dex']:03d}, {types}, {pokemon['region']}, {pokemon['spawn_rate']})"

    @commands.hybrid_command(name='suggest', aliases=['s'], description='Suggest Pokémon for event quests')
    @app_commands.describe(count='Number of Pokémon to suggest per quest (default: 2)')
    async def suggest(self, ctx, count: int = 2):
        """Suggest Pokémon for the latest event quest embed"""
        if count < 1 or count > 5:
            await ctx.reply('❌ Please provide a count between 1 and 5.', mention_author=False)
            return

        # Try to find the latest message with an embed containing quests
        async for message in ctx.channel.history(limit=50):
            if message.embeds:
                embed = message.embeds[0]
                # Check if this is an event embed with quests
                if embed.fields:
                    quest_field = None
                    for field in embed.fields:
                        if 'quest' in field.name.lower():
                            quest_field = field
                            break

                    if quest_field:
                        # Parse quests from the field value
                        quest_lines = quest_field.value.split('\n')

                        # Build summary embed (just the list)
                        summary_embed = discord.Embed(
                            title='🔍 Pokémon Quest Suggestions',
                            description=f'Suggesting **{count} Pokémon** per quest from the event: **{embed.title}**',
                            color=EMBED_COLOR
                        )

                        # Build detailed embed (with quest breakdown)
                        details_embed = discord.Embed(
                            title='🔍 Pokémon Quest Suggestions - Details',
                            description=f'Detailed breakdown for the event: **{embed.title}**',
                            color=EMBED_COLOR
                        )

                        suggestions = []
                        all_suggested_pokemon = set()
                        gender_suggestions = []

                        for line in quest_lines:
                            if not line.strip() or not re.search(r'^\d+\.', line.strip()):
                                continue

                            quest_info = self.parse_quest(line)
                            if not quest_info:
                                continue

                            matches = self.find_matching_pokemon(quest_info, limit=count)

                            if matches:
                                quest_text = re.sub(r'<:[^>]+>', '', quest_info['text'])
                                quest_text = re.sub(r'\d+/\d+$', '', quest_text).strip()

                                suggestion_text = f"**Quest:** {quest_text}\n"
                                for pokemon in matches:
                                    suggestion_text += self.format_pokemon_info(pokemon) + '\n'

                                    # Only add to main list if not a gender quest
                                    if not quest_info.get('gender'):
                                        all_suggested_pokemon.add(pokemon['name'])

                                # Separate gender quests from regular quests
                                if quest_info.get('gender'):
                                    gender_pokemon_names = ', '.join([p['name'] for p in matches])
                                    gender_type = 'Unknown gender' if quest_info['gender'] == 'genderless' else quest_info['gender'].capitalize() + ' gender'
                                    gender_suggestions.append({
                                        'text': f"**{quest_text}**\n{gender_pokemon_names}",
                                        'quest_text': quest_text,
                                        'pokemon': gender_pokemon_names
                                    })

                                suggestions.append(suggestion_text)

                        if suggestions:
                            # Add quest details to the details embed
                            for i, suggestion in enumerate(suggestions[:25]):
                                details_embed.add_field(
                                    name=f'Quest {i+1}',
                                    value=suggestion,
                                    inline=False
                                )

                            # Add main Pokémon list to summary embed (excluding gender quests)
                            if all_suggested_pokemon:
                                pokemon_list = ', '.join(sorted(all_suggested_pokemon))
                                summary_embed.add_field(
                                    name='📋 All Suggested Pokémon',
                                    value=pokemon_list,
                                    inline=False
                                )

                                # Also add to details embed
                                details_embed.add_field(
                                    name='📋 All Suggested Pokémon',
                                    value=pokemon_list,
                                    inline=False
                                )

                            # Add gender quest suggestions separately on summary embed
                            if gender_suggestions:
                                for gender_info in gender_suggestions:
                                    summary_embed.add_field(
                                        name='👥 Gender Quest Suggestions',
                                        value=gender_info['text'],
                                        inline=False
                                    )

                            if len(suggestions) > 25:
                                details_embed.set_footer(text=f'Showing 25 of {len(suggestions)} quests')

                            # Create view with Details button
                            view = DetailsView(details_embed)

                            await ctx.reply(embed=summary_embed, view=view, mention_author=False)
                            return

        await ctx.reply('❌ No event quest embed found in recent messages. Please run this command in a channel with an event embed.', mention_author=False)

async def setup(bot):
    await bot.add_cog(PokemonQuestHelper(bot))
