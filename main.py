import discord
from discord.ext import commands
import json
import datetime
import os
import asyncio
from typing import List, Dict, Optional

# 봇 클래스 정의
class TicketBot(commands.Bot):
    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.ticket_settings = {}
        self.active_tickets = {} 
        # 개발자 ID 목록 (여기에 개발자 ID를 추가하세요)
        self.developer_ids = []
        
    async def setup_hook(self):
        # 봇이 시작될 때 설정 로드
        self.load_settings()
        
        # 슬래시 명령어 동기화
        await self.sync_commands()
        print(f"슬래시 명령어 동기화 완료!")
    
    def load_settings(self):
        """설정 파일에서 티켓 설정을 로드합니다."""
        try:
            if os.path.exists('ticket_settings.json'):
                with open('ticket_settings.json', 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content:
                        self.ticket_settings = json.loads(content)
            else:
                with open('ticket_settings.json', 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"설정 로드 중 오류 발생: {e}")
            self.ticket_settings = {}
    
    def save_settings(self):
        """티켓 설정을 파일에 저장합니다."""
        try:
            with open('ticket_settings.json', 'w', encoding='utf-8') as f:
                json.dump(self.ticket_settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"설정 저장 중 오류 발생: {e}")
    
    def is_authorized(self, user: discord.User, guild: discord.Guild) -> bool:
        """사용자가 개발자이거나 서버 소유자인지 확인합니다."""
        return user.id in self.developer_ids or user.id == guild.owner_id

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# 봇 생성
bot = TicketBot(command_prefix="!", intents=intents)

# 권한 확인 함수
async def check_permission(interaction: discord.Interaction) -> bool:
    """사용자가 명령어를 사용할 권한이 있는지 확인합니다."""
    if not bot.is_authorized(interaction.user, interaction.guild):
        await interaction.response.send_message("이 명령어는 서버 소유자나 개발자만 사용할 수 있습니다.", ephemeral=True)
        return False
    return True

# 티켓 설정 명령어
@bot.slash_command(name="설정", description="티켓 시스템을 설정합니다")
@discord.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    """티켓 시스템 설정 명령어"""
    if not await check_permission(interaction):
        return
    await interaction.response.send_modal(TicketSetupModal(bot))

# 티켓 패널 생성 명령어
@bot.slash_command(name="티켓패널", description="티켓 생성 패널을 설정합니다")
@discord.default_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    """티켓 패널 생성 명령어"""
    if not await check_permission(interaction):
        return
    
    # 설정 확인
    guild_id = str(interaction.guild_id)
    if guild_id not in bot.ticket_settings:
        await interaction.response.send_message("먼저 `/설정` 명령어로 티켓 시스템을 설정해주세요.", ephemeral=True)
        return
    
    settings = bot.ticket_settings[guild_id]
    
    # 티켓 유형 확인
    ticket_types = settings.get("ticket_types", [])
    if not ticket_types:
        await interaction.response.send_message("티켓 유형이 설정되지 않았습니다.", ephemeral=True)
        return
    
    # 임베드 설정
    embed_settings = settings.get("ticket_panel_embed", {
        "title": "🎫 티켓 시스템",
        "description": "아래 버튼을 클릭하여 새로운 티켓을 생성하세요.",
        "color": 0x3498db,
        "footer": "문의사항이 있으시면 티켓을 생성해주세요."
    })
    
    embed = discord.Embed(
        title=embed_settings.get("title"),
        description=embed_settings.get("description"),
        color=embed_settings.get("color")
    )
    
    if embed_settings.get("footer"):
        embed.set_footer(text=embed_settings.get("footer"))
    
    # 티켓 패널 전송
    try:
        await interaction.channel.send(
            embed=embed,
            view=TicketPanelView(bot, ticket_types)
        )
        await interaction.response.send_message("티켓 패널이 생성되었습니다.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"패널 생성 중 오류가 발생했습니다: {e}", ephemeral=True)

# 임베드 설정 명령어
@bot.slash_command(name="임베드설정", description="티켓 시스템의 임베드를 커스텀마이징합니다")
@discord.default_permissions(administrator=True)
async def setup_embed(
    interaction: discord.Interaction, 
    embed_type: str = discord.Option("임베드 유형을 선택하세요", choices=["티켓 패널", "티켓 생성", "티켓 닫힘"])
):
    if not await check_permission(interaction):
        return
    
    await interaction.response.send_modal(EmbedCustomizationModal(bot, embed_type))

# 통계 명령어
@bot.slash_command(name="통계", description="티켓 시스템 통계를 확인합니다")
async def statistics(interaction: discord.Interaction):
    """티켓 통계 명령어"""
    if not await check_permission(interaction):
        return
        
    guild_id = str(interaction.guild_id)
    
    if guild_id not in bot.ticket_settings:
        await interaction.response.send_message("티켓 시스템이 설정되지 않았습니다.", ephemeral=True)
        return
    
    settings = bot.ticket_settings[guild_id]
    
    # 카테고리 확인
    if "category_id" not in settings:
        await interaction.response.send_message("티켓 카테고리가 설정되지 않았습니다.", ephemeral=True)
        return
    
    category = interaction.guild.get_channel(settings["category_id"])
    if not category:
        await interaction.response.send_message("설정된 티켓 카테고리를 찾을 수 없습니다.", ephemeral=True)
        return
    
    # 티켓 통계 계산
    total_tickets = 0
    tickets_by_type = {}
    
    for channel in category.channels:
        if channel.name.startswith("ticket-"):
            total_tickets += 1
            parts = channel.name.split("-")
            if len(parts) > 1:
                ticket_type = parts[1]
                tickets_by_type[ticket_type] = tickets_by_type.get(ticket_type, 0) + 1
    
    # 통계 임베드 생성
    embed = discord.Embed(
        title="📊 티켓 시스템 통계",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="총 활성 티켓", value=str(total_tickets), inline=False)
    
    for ticket_type, count in tickets_by_type.items():
        embed.add_field(name=f"{ticket_type} 티켓", value=str(count), inline=True)
    
    await interaction.response.send_message(embed=embed)

# 티켓 설정 모달
class TicketSetupModal(discord.ui.Modal):
    def __init__(self, bot: TicketBot):
        super().__init__(title="티켓 설정")
        self.bot = bot
        
        self.category = discord.ui.TextInput(
            label="티켓 카테고리 ID",
            placeholder="티켓이 생성될 카테고리의 ID를 입력하세요",
            required=True
        )
        
        self.support_roles = discord.ui.TextInput(
            label="지원팀 역할 ID들",
            placeholder="티켓에 접근할 수 있는 역할 ID들을 쉼표로 구분하여 입력하세요",
            required=True
        )
        
        self.ticket_types = discord.ui.TextInput(
            label="티켓 종류",
            placeholder="티켓 종류를 쉼표로 구분하여 입력하세요 (예: 구매문의,판매문의,기술지원)",
            required=True,
            style=discord.TextStyle.paragraph
        )
        
        self.log_channel = discord.ui.TextInput(
            label="로그 채널 ID",
            placeholder="티켓 로그가 기록될 채널의 ID를 입력하세요",
            required=True
        )
        
        self.max_tickets = discord.ui.TextInput(
            label="사용자당 최대 티켓 수",
            placeholder="한 사용자가 동시에 생성할 수 있는 최대 티켓 수를 입력하세요 (기본: 3)",
            required=False
        )
        
        self.add_item(self.category)
        self.add_item(self.support_roles)
        self.add_item(self.ticket_types)
        self.add_item(self.log_channel)
        self.add_item(self.max_tickets)
    
    async def callback(self, interaction: discord.Interaction):
        try:
            guild_id = str(interaction.guild_id)
            
            # 설정 저장
            self.bot.ticket_settings[guild_id] = {
                "category_id": int(self.category.value),
                "support_role_ids": [int(role.strip()) for role in self.support_roles.value.split(",")],
                "ticket_types": [type.strip() for type in self.ticket_types.value.split(",")],
                "log_channel_id": int(self.log_channel.value),
                "max_tickets_per_user": int(self.max_tickets.value) if self.max_tickets.value else 3
            }
            
            # 설정 저장
            self.bot.save_settings()
            
            embed = discord.Embed(
                title="✅ 티켓 설정 완료",
                description="티켓 시스템이 성공적으로 설정되었습니다.",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError as e:
            await interaction.response.send_message(f"설정 중 오류 발생: {str(e)}", ephemeral=True)

# 임베드 커스텀 모달
class EmbedCustomizationModal(discord.ui.Modal):
    def __init__(self, bot: TicketBot, embed_type: str):
        super().__init__(title="임베드 커스텀마이징")
        self.bot = bot
        self.embed_type = embed_type
        
        self.title_input = discord.ui.TextInput(
            label="제목",
            placeholder="임베드의 제목을 입력하세요",
            required=True,
            max_length=256
        )
        
        self.description_input = discord.ui.TextInput(
            label="설명",
            placeholder="임베드의 설명을 입력하세요",
            required=True,
            style=discord.TextStyle.paragraph
        )
        
        self.color_input = discord.ui.TextInput(
            label="색상 (HEX)",
            placeholder="예: #FF0000 (기본: #3498db)",
            required=False,
            max_length=7
        )
        
        self.footer_input = discord.ui.TextInput(
            label="푸터",
            placeholder="임베드의 푸터를 입력하세요",
            required=False
        )
        
        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.color_input)
        self.add_item(self.footer_input)
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # 색상 변환
            color_value = int(self.color_input.value.strip('#'), 16) if self.color_input.value else 0x3498db
        except ValueError:
            color_value = 0x3498db
        
        guild_id = str(interaction.guild_id)
        
        # 설정 저장
        if guild_id not in self.bot.ticket_settings:
            self.bot.ticket_settings[guild_id] = {}
        
        self.bot.ticket_settings[guild_id][f"{self.embed_type}_embed"] = {
            "title": self.title_input.value,
            "description": self.description_input.value,
            "color": color_value,
            "footer": self.footer_input.value if self.footer_input.value else None
        }
        
        self.bot.save_settings()
        
        embed = discord.Embed(
            title="✅ 임베드 설정 완료",
            description=f"{self.embed_type} 임베드가 성공적으로 커스텀되었습니다.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# 참여자 추가 모달
class AddParticipantModal(discord.ui.Modal):
    def __init__(self, ticket_channel):
        super().__init__(title="참여자 추가")
        self.ticket_channel = ticket_channel
        
        self.user_id = discord.ui.TextInput(
            label="사용자 ID",
            placeholder="추가할 사용자의 ID를 입력하세요",
            required=True
        )
        
        self.add_item(self.user_id)
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # 사용자 찾기
            user = await interaction.guild.fetch_member(int(self.user_id.value))
            
            # 티켓 채널에 권한 추가
            await self.ticket_channel.set_permissions(user, read_messages=True, send_messages=True)
            
            await interaction.response.send_message(f"{user.mention}님이 티켓에 추가되었습니다.", ephemeral=True)
        except Exception as e:
            print(f"참여자 추가 중 오류: {e}")
            await interaction.response.send_message("사용자를 찾을 수 없습니다.", ephemeral=True)

# 티켓 타이머 클래스
class TicketTimer:
    def __init__(self):
        self.start_time = datetime.datetime.now()
        self.end_time = None
    
    def close(self):
        self.end_time = datetime.datetime.now()
    
    def get_duration(self):
        if not self.end_time:
            return datetime.datetime.now() - self.start_time
        return self.end_time - self.start_time

# 티켓 패널 뷰
class TicketPanelView(discord.ui.View):
    def __init__(self, bot: TicketBot, ticket_types: List[str]):
        super().__init__(timeout=None)
        self.bot = bot
        
        # 티켓 유형별 버튼 생성
        for i, ticket_type in enumerate(ticket_types):
            # 최대 5개 버튼만 추가 (Discord UI 제한)
            if i >= 5:
                break
                
            button = TicketButton(ticket_type, i)
            self.add_item(button)

# 티켓 버튼 클래스
class TicketButton(discord.ui.Button):
    def __init__(self, ticket_type: str, position: int):
        # 버튼 스타일 결정 (순서에 따라 다른 색상)
        styles = [
            discord.ButtonStyle.primary,
            discord.ButtonStyle.success,
            discord.ButtonStyle.secondary,
            discord.ButtonStyle.danger,
            discord.ButtonStyle.primary
        ]
        
        super().__init__(
            style=styles[position % len(styles)],
            label=ticket_type,
            custom_id=f"ticket_{ticket_type}"
        )
        
        self.ticket_type = ticket_type
    
    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        guild_id = str(interaction.guild_id)
        
        # 설정 확인
        if guild_id not in bot.ticket_settings:
            await interaction.response.send_message("티켓 시스템이 설정되지 않았습니다.", ephemeral=True)
            return
        
        settings = bot.ticket_settings[guild_id]
        
        # 카테고리 확인
        category = interaction.guild.get_channel(settings.get("category_id"))
        if not category:
            await interaction.response.send_message("티켓 카테고리를 찾을 수 없습니다.", ephemeral=True)
            return
        
        # 사용자 티켓 수 확인
        user_tickets = sum(1 for channel in category.channels 
                          if channel.name.startswith("ticket-") and channel.name.endswith(str(interaction.user.name)))
        
        max_tickets = settings.get("max_tickets_per_user", 3)
        
        if user_tickets >= max_tickets:
            await interaction.response.send_message(
                "최대 티켓 수에 도달했습니다. 기존 티켓을 닫고 새로 만들어주세요.",
                ephemeral=True
            )
            return
        
        # 티켓 채널 생성 권한 설정
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # 지원팀 역할 권한 추가
        for role_id in settings.get("support_role_ids", []):
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        # 티켓 채널 생성
        ticket_channel = await category.create_text_channel(
            f"ticket-{self.ticket_type}-{interaction.user.name}",
            overwrites=overwrites
        )
        
        # 티켓 타이머 시작
        bot.active_tickets[ticket_channel.id] = TicketTimer()
        
        # 임베드 설정
        embed_settings = settings.get("ticket_created_embed", {
            "title": "🎫 새로운 티켓",
            "description": "티켓이 생성되었습니다.\n담당자가 곧 응답할 것입니다.",
            "color": 0x3498db
        })
        
        embed = discord.Embed(
            title=embed_settings.get("title", "🎫 새로운 티켓"),
            description=embed_settings.get("description", "티켓이 생성되었습니다.\n담당자가 곧 응답할 것입니다."),
            color=embed_settings.get("color", 0x3498db)
        )
        
        if embed_settings.get("footer"):
            embed.set_footer(text=embed_settings.get("footer"))
        
        # 티켓 관리 뷰 생성
        manage_view = TicketManageView(bot, ticket_channel)
        
        # 티켓 채널에 메시지 전송
        support_mentions = ", ".join(f"<@&{role_id}>" for role_id in settings.get("support_role_ids", []))
        
        await ticket_channel.send(
            content=f"{interaction.user.mention} {support_mentions}",
            embed=embed,
            view=manage_view
        )
        
        # 사용자에게 응답
        await interaction.response.send_message(
            f"티켓이 생성되었습니다: {ticket_channel.mention}",
            ephemeral=True
        )
        
        # 로그 채널에 기록
        log_channel_id = settings.get("log_channel_id")
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title="🎫 새 티켓 생성됨",
                    description=f"**채널:** {ticket_channel.mention}\n**생성자:** {interaction.user.mention}\n**종류:** {self.ticket_type}",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now()
                )
                await log_channel.send(embed=log_embed)

# 티켓 관리 뷰
class TicketManageView(discord.ui.View):
    def __init__(self, bot: TicketBot, ticket_channel):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_channel = ticket_channel
    
    @discord.ui.button(label="티켓 닫기", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild_id)
        settings = self.bot.ticket_settings.get(guild_id)
        
        if not settings:
            await interaction.response.send_message("티켓 시스템이 설정되지 않았습니다.", ephemeral=True)
            return
        
        # 타이머 종료
        timer = self.bot.active_tickets.get(self.ticket_channel.id)
        if timer:
            timer.close()
            duration = timer.get_duration()
        else:
            duration = None
        
        # 메시지 기록 저장
        messages = []
        async for message in self.ticket_channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = message.content if message.content else "[임베드 또는 첨부 파일]"
            messages.append(f"[{timestamp}] {message.author.name}: {content}")
        
        # 트랜스크립트 저장
        os.makedirs('transcripts', exist_ok=True)
        transcript_path = f'transcripts/ticket-{self.ticket_channel.name}.txt'
        
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(messages))
        
        # 로그 채널에 기록
        log_channel_id = settings.get("log_channel_id")
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                close_embed = discord.Embed(
                    title="🔒 티켓 닫힘",
                    description=f"**티켓:** {self.ticket_channel.name}\n**닫은 사람:** {interaction.user.mention}",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now()
                )
                
                if duration:
                    close_embed.add_field(
                        name="처리 시간",
                        value=str(duration).split('.')[0]
                    )
                
                await log_channel.send(
                    embed=close_embed,
                    file=discord.File(transcript_path, filename=f'transcript-{self.ticket_channel.name}.txt')
                )
        
        # 티켓 삭제 알림
        await interaction.response.send_message("티켓이 닫히고 5초 후 삭제됩니다.", ephemeral=True)
        
        # 5초 후 티켓 채널 삭제
        await asyncio.sleep(5)
        await self.ticket_channel.delete()
    
    @discord.ui.button(label="참여자 추가", style=discord.ButtonStyle.success, emoji="👥", custom_id="add_participant")
    async def add_participant(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddParticipantModal(self.ticket_channel)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="우선순위 설정", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="set_priority")
    async def set_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "티켓 우선순위를 선택하세요:",
            view=TicketPriorityView(self.ticket_channel),
            ephemeral=True
        )

# 티켓 우선순위 뷰
class TicketPriorityView(discord.ui.View):
    def __init__(self, ticket_channel):
        super().__init__(timeout=60)  # 60초 타임아웃
        self.ticket_channel = ticket_channel
    
    @discord.ui.button(label="긴급", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="priority_urgent")
    async def priority_urgent(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_priority(interaction, "URGENT")
    
    @discord.ui.button(label="높음", style=discord.ButtonStyle.primary, emoji="🟡", custom_id="priority_high")
    async def priority_high(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_priority(interaction, "HIGH")
    
    @discord.ui.button(label="보통", style=discord.ButtonStyle.success, emoji="🟢", custom_id="priority_medium")
    async def priority_medium(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_priority(interaction, "MEDIUM")
    
    @discord.ui.button(label="낮음", style=discord.ButtonStyle.secondary, emoji="⚪", custom_id="priority_low")
    async def priority_low(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_priority(interaction, "LOW")
    
    async def set_priority(self, interaction: discord.Interaction, priority: str):
        # 채널 이름에서 우선순위 부분 제거
        channel_name = self.ticket_channel.name
        if any(p in channel_name for p in ["URGENT", "HIGH", "MEDIUM", "LOW"]):
            parts = channel_name.split("-")
            channel_name = "-".join([p for p in parts if p not in ["URGENT", "HIGH", "MEDIUM", "LOW"]])
        
        # 새 우선순위로 채널 이름 변경
        new_name = f"{channel_name}-{priority}"
        await self.ticket_channel.edit(name=new_name)
        
        # 응답
        await interaction.response.send_message(f"티켓 우선순위가 {priority}로 설정되었습니다.", ephemeral=True)
        
def main():
    # 봇 실행
    bot.run("")  

if __name__ == "__main__":
    main()
