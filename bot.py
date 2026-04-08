import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import pytz

from time_parser import find_times, to_unix_timestamp
from timezone_store import get_user_tz, get_user_tz_str, set_user_tz, init_db

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

COMMON_TIMEZONES = [
    ("US/Pacific",     "Pacific (PT)"),
    ("US/Mountain",    "Mountain (MT)"),
    ("US/Central",     "Central (CT)"),
    ("US/Eastern",     "Eastern (ET)"),
    ("America/Halifax","Atlantic (AT)"),
    ("America/Anchorage", "Alaska (AKT)"),
    ("Pacific/Honolulu",  "Hawaii (HT)"),
    ("Europe/London",  "London (GMT/BST)"),
    ("Europe/Paris",   "Paris (CET/CEST)"),
    ("Europe/Berlin",  "Berlin (CET/CEST)"),
    ("Asia/Dubai",     "Dubai (GST)"),
    ("Asia/Kolkata",   "India (IST)"),
    ("Asia/Tokyo",     "Tokyo (JST)"),
    ("Australia/Sydney", "Sydney (AEST/AEDT)"),
]


class TimezoneSelect(discord.ui.Select):
    def __init__(self, original_message: discord.Message, times: list[tuple[int, int]]):
        self.original_message = original_message
        self.times = times
        options = [
            discord.SelectOption(label=label, value=tz_str)
            for tz_str, label in COMMON_TIMEZONES
        ]
        super().__init__(
            placeholder="Select your timezone...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        tz_str = self.values[0]
        set_user_tz(interaction.user.id, tz_str)
        tz = pytz.timezone(tz_str)

        timestamps = [to_unix_timestamp(h, m, inline_tz or tz) for h, m, inline_tz in self.times]
        reply = _format_reply(timestamps)

        await interaction.response.edit_message(
            content=f"Timezone saved as **{tz_str}**!", view=None
        )
        await self.original_message.reply(reply)


class TimezoneView(discord.ui.View):
    def __init__(self, original_message: discord.Message, times: list[tuple[int, int]]):
        super().__init__(timeout=120)
        self.add_item(TimezoneSelect(original_message, times))


def _format_reply(timestamps: list[int]) -> str:
    if len(timestamps) == 1:
        ts = timestamps[0]
        return f"🕐 <t:{ts}:t> — <t:{ts}:F> (<t:{ts}:R>)"
    lines = [f"🕐 Times mentioned:"]
    for ts in timestamps:
        lines.append(f"• <t:{ts}:t> — <t:{ts}:F> (<t:{ts}:R>)")
    return "\n".join(lines)


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


@bot.event
async def on_ready():
    init_db()
    await tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    times = find_times(message.content)
    if not times:
        await bot.process_commands(message)
        return

    tz = get_user_tz(message.author.id)

    if tz is None:
        view = TimezoneView(message, times)
        await message.reply(
            "What's your timezone? I'll remember it so you only need to do this once.",
            view=view,
            ephemeral=False,
        )
        return

    timestamps = [to_unix_timestamp(h, m, inline_tz or tz) for h, m, inline_tz in times]
    await message.reply(_format_reply(timestamps))

    await bot.process_commands(message)


@tree.command(name="settimezone", description="Set your timezone")
@app_commands.describe(timezone="e.g. US/Central, Europe/London, America/New_York")
async def settimezone(interaction: discord.Interaction, timezone: str):
    try:
        set_user_tz(interaction.user.id, timezone)
        await interaction.response.send_message(
            f"Your timezone has been set to **{timezone}**.", ephemeral=True
        )
    except pytz.exceptions.UnknownTimeZoneError:
        await interaction.response.send_message(
            f"Unknown timezone: `{timezone}`. Use a standard tz name like `US/Central` or `Europe/London`.",
            ephemeral=True,
        )


@tree.command(name="mytimezone", description="Show your currently stored timezone")
async def mytimezone(interaction: discord.Interaction):
    tz_str = get_user_tz_str(interaction.user.id)
    if tz_str:
        await interaction.response.send_message(
            f"Your timezone is set to **{tz_str}**.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "You don't have a timezone set yet. Send a message with a time and I'll ask you!",
            ephemeral=True,
        )


bot.run(TOKEN)
