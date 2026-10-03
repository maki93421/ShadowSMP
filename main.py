import discord
from discord import app_commands
from discord.ext import commands
import asyncio

# In-memory storage for the support role ID per guild (server)
# Note: For production use, this should be saved to a database so it persists after reboots.
support_role_storage = {}

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Keeps the button persistent across bot restarts

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.green, emoji="📩", custom_id="open_ticket_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        
        # Fetch the support role configured for this guild
        support_role_id = support_role_storage.get(guild.id)
        support_role = guild.get_role(support_role_id) if support_role_id else None

        # Define channel access restrictions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False), # Hide channel from everyone
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True), # Ticket creator can read/write
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True) # The bot can read/write
        }

        # Grant access to the support rank if it has been configured
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # Create the isolated text channel
        channel_name = f"ticket-{member.name}"
        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)

        # Immediate micro-feedback to the clicking user
        await interaction.response.send_message(f"Your ticket has been created here: {ticket_channel.mention}", ephemeral=True)

        # Welcome panel message layout (Fixed the quote closure issue here)
        embed = discord.Embed(
            title="Ticket Opened!",
            description=f"Hello {member.mention}, the support team will be with you shortly.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Type /close to delete this ticket channel")

        # Mention the user and the support group if available
        ping_msg = f"{member.mention}"
        if support_role:
            ping_msg += f" {support_role.mention}"

        await ticket_channel.send(content=ping_msg, embed=embed)

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Register the visual components view profile into the global cycle
        self.add_view(TicketView())
        await self.tree.sync()

bot = Bot()

@bot.event
async def on_ready():
    print(f"Bot application is online as {bot.user}")

# COMMAND 1: /setup_discord
@bot.tree.command(name="setup_discord", description="Deploys the ticket creation interface and sets the staff role.")
@app_commands.describe(support_role="The rank allowed to view and reply inside created ticket channels")
@app_commands.checks.has_permissions(administrator=True)
async def setup_discord(interaction: discord.Interaction, support_role: discord.Role):
    # Save the selected support role ID for this guild
    support_role_storage[interaction.guild_id] = support_role.id

    embed = discord.Embed(
        title="Support & Help Desk",
        description="Need assistance or want to contact staff? Click the button below to open a private ticket.",
        color=discord.Color.green()
    )
    
    view = TicketView()
    await interaction.response.send_message("Ticket panel configuration successfully deployed!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=view)

# Error handling mapping for the setup execution rule
@setup_discord.error
async def setup_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You lack the required Administrator permissions to use this command.", ephemeral=True)

# COMMAND 2: /close
@bot.tree.command(name="close", description="Closes and deletes the current active ticket channel.")
async def close(interaction: discord.Interaction):
    # Check if the execution context is happening in a ticket channel boundary
    if not interaction.channel.name.startswith("ticket-"):
        await interaction.response.send_message("This command can only be executed within a valid ticket channel context!", ephemeral=True)
        return

    guild = interaction.guild
    support_role_id = support_role_storage.get(guild.id)
    
    # Access control evaluation parameters
    is_admin = interaction.user.guild_permissions.administrator
    has_support_role = any(role.id == support_role_id for role in interaction.user.roles) if support_role_id else False
    is_ticket_owner = interaction.channel.name == f"ticket-{interaction.user.name.lower()}"

    if is_admin or has_support_role or is_ticket_owner:
        await interaction.response.send_message("This ticket channel will be deleted in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("You do not have the required access permissions to close this ticket.", ephemeral=True)

# Replace this placeholder string value with your actual bot token
bot.run("token")


