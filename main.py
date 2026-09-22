from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.constants import ParseMode
import psycopg2
from psycopg2 import extras
from datetime import datetime, timedelta
import os
import asyncio
import random
import csv
from io import BytesIO
import pytz
import html

# ============================================================
# CUSTOM EMOJI MAPPING (Telegram Premium)
# Tổng: 38 emoji động
# ============================================================
CUSTOM_EMOJI = {
    # ===== GAME =====
    "🎲": "5280816565657300091",
    "🎰": "6249213184167645257",
    "🃏": "5298499667569425533",
    "🎮": "5197288647275071607",
    "🎯": "5256131095094652290",
    # ===== TIỀN TỆ =====
    "💰": "5224257782013769471",
    "💵": "5409048419211682843",
    "💎": "6003595618100974363",
    "💳": "5445353829304387411",
    "💍": "5262922516426420894",
    "💠": "5461151367559141950",
    # ===== QUÀ TẶNG =====
    "🎁": "5203996991054432397",
    "🎉": "5192959294470895031",
    "🏆": "5226431245918942763",
    "👑": "5433758796289685818",
    "🌟": "5267500801240092311",
    "⭐": "5463092727136661235",
    # ===== TRẠNG THÁI =====
    "✅": "6003745186042089867",
    "❌": "5210952531676504517",
    "🔥": "5424972470023104089",
    "⚡": "5411590687663608498",
    "🚫": "5462882007451185227",
    "🔔": "5458603043203327669",
    # ===== NẠP / RÚT =====
    "📥": "5443127283898405358",
    "📤": "5445355530111437729",
    "🛒": "5400090058030075645",
    # ===== THỜI GIAN & CÀI ĐẶT =====
    "⏰": "5386415655253730366",
    "⌛": "5386367538735104399",
    "⚙️": "5341715473882955310",
    "🛠": "5462921117423384478",
    # ===== THÔNG TIN =====
    "👤": "5361741454685256344",
    "📞": "5237988788164107500",
    "📜": "6098288123580518916",
    "📊": "5203993413346680064",
    "📌": "5397782960512444700",
    "✍️": "5258500400918587241",
    "🆔": "5443038326535759644",
    "💬": "6003823762468770935",
    # ===== BẢO MẬT =====
    "🛡": "5400250414929041085",
    "🔒": "5372917041193828849",
    "🔓": "5291873529464122510",
    "🔮": "5278651867780377852",
    "👀": "5210956306952758910",
}

def ce(emoji: str) -> str:
    """Wrap emoji thành custom emoji HTML tag."""
    emoji_id = CUSTOM_EMOJI.get(emoji)
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>'
    return emoji

def ce_text(text: str) -> str:
    """Thay tất cả emoji trong text thành custom emoji."""
    for emoji, emoji_id in CUSTOM_EMOJI.items():
        text = text.replace(emoji, f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>')
    return text

def fmt_money(amount: int) -> str:
    """Format tiền: 50000 -> 50.000"""
    return f"{amount:,}".replace(",", ".")

# ============================================================
# TIMEZONE VIỆT NAM
# ============================================================
VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

def get_vietnam_time():
    return datetime.now(VIETNAM_TZ)

def get_vietnam_date():
    return get_vietnam_time().strftime("%d/%m/%Y")

def get_vietnam_datetime_db():
    return get_vietnam_time().strftime("%H:%M - %d/%m/%Y")

# ============================================================
# CẤU HÌNH
# ============================================================
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

ADMIN_IDS = [5633649201, 7857144049]
BOT_USERNAME = "zen88uytins1bot"
MIN_WITHDRAW = 50000
LOG_GROUP_ID = -1003663678808

BANK_ID = "MB"
ACCOUNT_NO = "0003456712345"
ACCOUNT_NAME = "LY THI CHAM"

_bot_instance = None
GROUP_IDS = [-1004322118515]

group_games = {}
room_betting_enabled = {}
game_history = {}
SESSION_COUNTER = {"value": 0}

# ============================================================
# DATABASE
# ============================================================
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

def query(q, args=()):
    conn = get_db_connection()
    cur = conn.cursor()
    res = None
    try:
        cur.execute(q, args)
        if cur.description:
            res = cur.fetchall()
        conn.commit()
    except Exception as e:
        print(f"Database Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return res

# ============================================================
# KHỞI TẠO BẢNG
# ============================================================
query("CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, reward INTEGER, uses INTEGER)")
query("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    balance BIGINT DEFAULT 0,
    refs INTEGER DEFAULT 0,
    refed INTEGER DEFAULT 0,
    bank TEXT DEFAULT NULL,
    stk TEXT DEFAULT NULL,
    name TEXT DEFAULT NULL,
    last_checkin TEXT,
    last_withdraw TEXT,
    total_bet BIGINT DEFAULT 0,
    rate_bonus INTEGER DEFAULT NULL,
    bank_linked INTEGER DEFAULT 0
)
""")
query("CREATE TABLE IF NOT EXISTS game_rates (id INTEGER PRIMARY KEY, name TEXT, rate INTEGER)")
query("CREATE TABLE IF NOT EXISTS banned_games (user_id BIGINT, game_id INTEGER, PRIMARY KEY (user_id, game_id))")
query("CREATE TABLE IF NOT EXISTS banned_features (user_id BIGINT, feature TEXT, PRIMARY KEY (user_id, feature))")
query("CREATE TABLE IF NOT EXISTS banned_admins (admin_id BIGINT PRIMARY KEY, banned_by BIGINT, reason TEXT, banned_at TEXT)")
query("""
CREATE TABLE IF NOT EXISTS user_bonus (
    user_id BIGINT PRIMARY KEY,
    bonus_amount BIGINT DEFAULT 0,
    required_bet BIGINT DEFAULT 0,
    current_bet BIGINT DEFAULT 0,
    created_at TEXT
)
""")
query("""
CREATE TABLE IF NOT EXISTS deposit_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    amount BIGINT,
    admin_id BIGINT,
    status TEXT DEFAULT 'pending',
    time TEXT
)
""")
query("""
CREATE TABLE IF NOT EXISTS withdraw_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    amount BIGINT,
    status TEXT DEFAULT 'pending',
    time TEXT,
    admin_id BIGINT,
    admin_note TEXT
)
""")
query("""
CREATE TABLE IF NOT EXISTS banned_admin_commands (
    admin_id BIGINT,
    command TEXT,
    banned_by BIGINT,
    reason TEXT,
    banned_at TEXT,
    PRIMARY KEY (admin_id, command)
)
""")
query("""
CREATE TABLE IF NOT EXISTS code_usage (
    user_id BIGINT,
    code TEXT,
    used_date TEXT,
    PRIMARY KEY (user_id, code, used_date)
)
""")
query("""
CREATE TABLE IF NOT EXISTS group_interactions (
    user_id BIGINT,
    group_id BIGINT,
    interaction_count INTEGER DEFAULT 0,
    last_interaction TEXT,
    PRIMARY KEY (user_id, group_id)
)
""")
query("""
CREATE TABLE IF NOT EXISTS daily_top_interactions (
    user_id BIGINT,
    group_id BIGINT,
    interaction_count INTEGER DEFAULT 0,
    date TEXT,
    rank INTEGER,
    reward_amount BIGINT DEFAULT 0,
    rewarded INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, group_id, date)
)
""")
query("""
CREATE TABLE IF NOT EXISTS tanthu_code (
    user_id BIGINT PRIMARY KEY,
    code TEXT,
    received_at TEXT,
    used INTEGER DEFAULT 0
)
""")

games_to_keep = [
    (1, "TÀI XỈU 6D"),
    (2, "XÓC ĐĨA"),
    (3, "BẦU CUA"),
    (4, "TÀI XỈU ROOM"),
]
for gid, name in games_to_keep:
    res = query("SELECT 1 FROM game_rates WHERE id=%s", (gid,))
    if not res:
        query("INSERT INTO game_rates VALUES(%s, %s, 10)", (gid, name))
    else:
        query("UPDATE game_rates SET name=%s WHERE id=%s", (name, gid))

query("DELETE FROM game_rates WHERE id > 4")

try: query("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_bet BIGINT DEFAULT 0")
except: pass
try: query("ALTER TABLE users ADD COLUMN IF NOT EXISTS rate_bonus INTEGER DEFAULT NULL")
except: pass
try: query("ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_linked INTEGER DEFAULT 0")
except: pass

query("CREATE TABLE IF NOT EXISTS history (user_id BIGINT, amount BIGINT, note TEXT, time TEXT)")
query("CREATE TABLE IF NOT EXISTS banned (user_id BIGINT PRIMARY KEY)")
query("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

maintenance_keys = ['mt_taixiu', 'mt_xocdia', 'mt_baucua', 'mt_taixiu_room', 'mt_nap', 'mt_rut']
for k in maintenance_keys:
    res = query("SELECT 1 FROM settings WHERE key=%s", (k,))
    if not res:
        query("INSERT INTO settings VALUES(%s, '0')", (k,))

query("DELETE FROM settings WHERE key IN ('mt_duaxe','mt_domin','mt_penalty','mt_gomo','mt_quayso','mt_xoso','mt_vongquay','mt_caothap','mt_rutgo','mt_tomau')")

res_name = query("SELECT 1 FROM settings WHERE key='bot_display_name'")
if not res_name:
    query("INSERT INTO settings(key, value) VALUES('bot_display_name', 'Hệ thống Game Uy Tín')")

res_system_mt = query("SELECT 1 FROM settings WHERE key='system_maintenance'")
if not res_system_mt:
    query("INSERT INTO settings VALUES('system_maintenance', '0')")

res_tongbao = query("SELECT 1 FROM settings WHERE key='mt_tongbao'")
if not res_tongbao:
    query("INSERT INTO settings VALUES('mt_tongbao', '0')")

res_jackpot = query("SELECT 1 FROM settings WHERE key='jackpot_amount'")
if not res_jackpot:
    query("INSERT INTO settings VALUES('jackpot_amount', '11000000000')")

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def is_system_maintenance():
    res = query("SELECT value FROM settings WHERE key='system_maintenance'")
    return res[0][0] == '1' if res else False

def is_total_maintenance():
    res = query("SELECT value FROM settings WHERE key='mt_tongbao'")
    return res[0][0] == '1' if res else False

def is_admin_banned(admin_id):
    res = query("SELECT 1 FROM banned_admins WHERE admin_id=%s", (admin_id,))
    return len(res) > 0 if res else False

def is_admin_command_banned(admin_id, command):
    res = query("SELECT 1 FROM banned_admin_commands WHERE admin_id=%s AND command=%s", (admin_id, command))
    return len(res) > 0 if res else False

def check_bank_linked(user_id):
    res = query("SELECT bank, stk, bank_linked FROM users WHERE user_id=%s", (user_id,))
    if res and res[0][0] and res[0][1] and res[0][2] == 1:
        return True
    return False

def admin_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if is_system_maintenance() and user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ</b>\n\nVui lòng quay lại sau ít phút!',
                parse_mode=ParseMode.HTML
            )
            return
        if user_id in ADMIN_IDS and is_admin_banned(user_id):
            await update.message.reply_text(
                f'{ce("🚫")} <b>Bạn đã bị cấm sử dụng các lệnh Admin!</b>',
                parse_mode=ParseMode.HTML
            )
            return
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(f'{ce("❌")} Bạn không có quyền sử dụng lệnh này!', parse_mode=ParseMode.HTML)
            return
        return await func(update, ctx, *args, **kwargs)
    return wrapper

def check_mt(key):
    res = query("SELECT value FROM settings WHERE key=%s", (key,))
    if res:
        return res[0][0] == '1'
    query("INSERT INTO settings (key, value) VALUES (%s, '0') ON CONFLICT (key) DO NOTHING", (key,))
    return False

def get_bot_name():
    res = query("SELECT value FROM settings WHERE key='bot_display_name'")
    return res[0][0] if res else "Hệ thống Game Uy Tín"

def get_rate_by_id(game_id, user_id=None):
    if user_id:
        res_user = query("SELECT rate_bonus FROM users WHERE user_id=%s", (user_id,))
        if res_user and res_user[0][0] is not None:
            return res_user[0][0]
    res = query("SELECT rate FROM game_rates WHERE id=%s", (game_id,))
    return res[0][0] if res else 10

def check_win_by_id(game_id, user_id=None):
    rate = get_rate_by_id(game_id, user_id)
    if rate >= 100: return True
    if rate <= 0: return False
    return random.randint(1, 100) <= rate

def is_game_banned(uid, gid):
    res = query("SELECT 1 FROM banned_games WHERE user_id=%s AND game_id=%s", (uid, gid))
    return len(res) > 0 if res else False

def is_feature_banned(uid, feature):
    res = query("SELECT 1 FROM banned_features WHERE user_id=%s AND feature=%s", (uid, feature))
    return len(res) > 0 if res else False

def get_vip_info(total_bet):
    if total_bet >= 50000000: return "VIP 5 (Kim Cương)", 5000
    if total_bet >= 20000000: return "VIP 4 (Vàng)", 3000
    if total_bet >= 10000000: return "VIP 3 (Bạc)", 1500
    if total_bet >= 5000000: return "VIP 2 (Đồng)", 800
    if total_bet >= 1000000: return "VIP 1", 500
    return "Thành viên", 300

def get_user(uid):
    res = query("SELECT 1 FROM users WHERE user_id=%s", (uid,))
    if not res:
        query("INSERT INTO users(user_id) VALUES(%s)", (uid,))

def get_balance(uid):
    get_user(uid)
    res = query("SELECT balance FROM users WHERE user_id=%s", (uid,))
    return res[0][0] if res else 0

def is_banned(uid):
    res = query("SELECT 1 FROM banned WHERE user_id=%s", (uid,))
    return len(res) > 0 if res else False

def add_money(uid, amt, note):
    get_user(uid)
    now_str = get_vietnam_datetime_db()
    query("UPDATE users SET balance=balance+%s WHERE user_id=%s", (amt, uid))
    query("INSERT INTO history VALUES(%s,%s,%s,%s)", (uid, amt, note, now_str))

def sub_money(uid, amt, note="withdraw"):
    get_user(uid)
    bal = get_balance(uid)
    if bal < amt:
        return False
    now_str = get_vietnam_datetime_db()
    query("UPDATE users SET balance=balance-%s WHERE user_id=%s", (amt, uid))
    query("INSERT INTO history VALUES(%s,%s,%s,%s)", (uid, -amt, note, now_str))
    if note != "Rút tiền" and note != "withdraw" and "Admin" not in note and "Chuyển tiền" not in note:
        query("UPDATE users SET total_bet=total_bet+%s WHERE user_id=%s", (amt, uid))
        update_bet_progress(uid, amt)
    return True

def add_bonus_with_requirement(user_id, bonus_amount, required_multiplier=3):
    required_bet = bonus_amount * required_multiplier
    now_str = get_vietnam_datetime_db()
    query("DELETE FROM user_bonus WHERE user_id=%s", (user_id,))
    query("INSERT INTO user_bonus (user_id, bonus_amount, required_bet, current_bet, created_at) VALUES (%s, %s, %s, %s, %s)",
          (user_id, bonus_amount, required_bet, 0, now_str))
    add_money(user_id, bonus_amount, f"Khuyến mãi nạp +{bonus_amount:,}đ (yêu cầu cược x{required_multiplier})")
    return required_bet

def get_remaining_bet_required(user_id):
    bonus_data = query("SELECT required_bet, current_bet FROM user_bonus WHERE user_id=%s", (user_id,))
    if not bonus_data or bonus_data[0][0] == 0:
        return 0
    required_bet, current_bet = bonus_data[0]
    return max(0, required_bet - current_bet)

async def check_and_notify_bet_completion(user_id: int, current_bet: int, required_bet: int):
    if current_bet >= required_bet:
        bonus_data = query("SELECT bonus_amount, required_bet, current_bet FROM user_bonus WHERE user_id=%s", (user_id,))
        if bonus_data:
            bonus_amount, req_bet, curr_bet = bonus_data[0]
            message = (
                f'{ce("🎉")} <b>CHÚC MỪNG! BẠN ĐÃ HOÀN THÀNH YÊU CẦU CƯỢC!</b> {ce("🎉")}\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'{ce("💰")} <b>Tiền khuyến mãi đã nhận:</b> <code>+{fmt_money(bonus_amount)}đ</code>\n'
                f'{ce("🎯")} <b>Yêu cầu cược:</b> <code>{fmt_money(req_bet)}đ</code> (x3 vòng)\n'
                f'{ce("✅")} <b>Tổng cược đã thực hiện:</b> <code>{fmt_money(curr_bet)}đ</code>\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'{ce("🔓")} <b>Bạn đã có thể rút tiền bình thường!</b>'
            )
            try:
                if _bot_instance:
                    await _bot_instance.send_message(user_id, message, parse_mode=ParseMode.HTML)
            except: pass
            query("DELETE FROM user_bonus WHERE user_id=%s", (user_id,))
            return True
    return False

def update_bet_progress(user_id: int, bet_amount: int):
    bonus_data = query("SELECT required_bet, current_bet FROM user_bonus WHERE user_id=%s", (user_id,))
    if not bonus_data or bonus_data[0][0] == 0:
        return False
    required_bet, current_bet = bonus_data[0]
    new_bet = current_bet + bet_amount
    query("UPDATE user_bonus SET current_bet=%s WHERE user_id=%s", (new_bet, user_id))
    if new_bet >= required_bet:
        asyncio.create_task(check_and_notify_bet_completion(user_id, new_bet, required_bet))
        return True
    return False

def get_bet_progress_status(user_id: int):
    bonus_data = query("SELECT bonus_amount, required_bet, current_bet FROM user_bonus WHERE user_id=%s", (user_id,))
    if not bonus_data or bonus_data[0][1] == 0:
        return None
    bonus_amount, required_bet, current_bet = bonus_data[0]
    percent = (current_bet / required_bet * 100) if required_bet > 0 else 0
    remaining = required_bet - current_bet
    return {
        'bonus_amount': bonus_amount,
        'required_bet': required_bet,
        'current_bet': current_bet,
        'percent': percent,
        'remaining': remaining,
        'is_completed': current_bet >= required_bet
    }

def gen_code():
    return ''.join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(8))

def get_deposit_info(user_id):
    qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-qr_only.png?amount=0&addInfo={user_id}&accountName={ACCOUNT_NAME}"
    caption = (
        f'{ce("💳")} <b>THÔNG TIN NẠP TIỀN</b>\n\n'
        f'{ce("💳")} Ngân hàng: <b>MBBANK</b>\n'
        f'{ce("👤")} CTK: <b>{ACCOUNT_NAME}</b>\n'
        f'{ce("💰")} STK: <code>{ACCOUNT_NO}</code>\n'
        f'{ce("✍️")} Nội dung: <code>{user_id}</code>\n\n'
        f'{ce("⚡")} <i>Lưu ý: Quét mã QR để tự động điền nội dung. Hệ thống cộng tiền sau 1-3 phút.</i>'
    )
    return qr_url, caption

def format_money(amount):
    return f"{amount:,}".replace(",", ".")

async def track_interaction(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return
    uid = update.effective_user.id
    gid = update.effective_chat.id
    today = get_vietnam_date()
    now_str = get_vietnam_datetime_db()
    query("""
        INSERT INTO group_interactions (user_id, group_id, interaction_count, last_interaction)
        VALUES (%s, %s, 1, %s)
        ON CONFLICT (user_id, group_id) DO UPDATE SET 
            interaction_count = group_interactions.interaction_count + 1,
            last_interaction = %s
    """, (uid, gid, now_str, now_str))
    query("""
        INSERT INTO daily_top_interactions (user_id, group_id, interaction_count, date)
        VALUES (%s, %s, 1, %s)
        ON CONFLICT (user_id, group_id, date) DO UPDATE SET 
            interaction_count = daily_top_interactions.interaction_count + 1
    """, (uid, gid, today))
    total = query("SELECT interaction_count FROM group_interactions WHERE user_id=%s AND group_id=%s", (uid, gid))
    if total and total[0][0] >= 200:
        rewarded = query("SELECT 1 FROM daily_top_interactions WHERE user_id=%s AND group_id=%s AND rewarded=1 AND interaction_count>=200", (uid, gid))
        if not rewarded:
            query("UPDATE group_interactions SET interaction_count = -200 WHERE user_id=%s AND group_id=%s", (uid, gid))
            await ctx.bot.send_message(uid,
                f'{ce("🎉")} <b>CHÚC MỪNG!</b> {ce("🎉")}\n{ce("🔥")} Bạn đã đạt <b>200 lượt tương tác</b>!',
                parse_mode=ParseMode.HTML)
            query("UPDATE daily_top_interactions SET rewarded=1 WHERE user_id=%s AND group_id=%s", (uid, gid))

# ============================================================
# JACKPOT
# ============================================================
def get_jackpot():
    res = query("SELECT value FROM settings WHERE key='jackpot_amount'")
    if res:
        return int(res[0][0])
    query("INSERT INTO settings (key, value) VALUES ('jackpot_amount', '11000000000') ON CONFLICT (key) DO NOTHING")
    return 11000000000

def update_jackpot(amount):
    query("UPDATE settings SET value=%s WHERE key='jackpot_amount'", (str(amount),))

# ============================================================
# TÀI XỈU ROOM
# ============================================================
def get_result_code(res_tx, res_cl):
    tx_code = "T" if res_tx == "tai" else "X"
    cl_code = "C" if res_cl == "chan" else "L"
    return f"{tx_code}{cl_code}"

def get_result_icons(res_tx, res_cl):
    tx_icon = "🔵" if res_tx == "tai" else "🔴"
    cl_icon = "⚪️" if res_cl == "chan" else "⚫️"
    return f"{tx_icon}{cl_icon}"

def get_full_result_text(res_tx, res_cl):
    tx_text = "TÀI" if res_tx == "tai" else "XỈU"
    cl_text = "CHẴN" if res_cl == "chan" else "LẺ"
    return f"{tx_text} {cl_text}"

async def run_dice_game_cycle(bot, group_id: int, chat_id: int):
    while True:
        try:
            if not room_betting_enabled.get(group_id, True):
                await asyncio.sleep(10)
                continue

            SESSION_COUNTER["value"] += 1
            session_id = SESSION_COUNTER["value"]

            game_state = {
                "status": "betting",
                "bets": {},
                "message_id": None,
                "session_id": session_id,
                "cycle_start": datetime.now()
            }
            group_games[group_id] = game_state

            jackpot_now = get_jackpot()

            start_text = (
                f'{ce("🎲")} <b>{get_bot_name()} - TÀI XỈU ROOM</b> {ce("🎲")}\n\n'
                f'{ce("✍️")} <b>Phiên #{session_id}</b>\n'
                f'{ce("⚡")} <b>ĐẶT CƯỢC NGAY!</b>\n'
                f'{ce("⏰")} Thời gian còn lại: <code>60s</code>\n\n'
                f'{ce("🎯")} <b>CÁCH CHƠI:</b>\n'
                f'• Tài (21-36): <code>t [số_tiền]</code> hoặc <code>t max</code>\n'
                f'• Xỉu (6-20): <code>x [số_tiền]</code> hoặc <code>x max</code>\n'
                f'• Chẵn: <code>c [số_tiền]</code> hoặc <code>c max</code>\n'
                f'• Lẻ: <code>l [số_tiền]</code> hoặc <code>l max</code>\n\n'
                f'{ce("🏆")} <b>Tỉ lệ thưởng: x1.95</b>\n'
                f'{ce("💰")} <b>Cược không giới hạn!</b>\n\n'
                f'{ce("📊")} <b>TỔNG CƯỢC:</b>\n'
                f'{ce("🎲")} TÀI: <code>0đ</code>\n'
                f'{ce("🎲")} XỈU: <code>0đ</code>\n'
                f'🔴 CHẴN: <code>0đ</code>\n'
                f'⚪ LẺ: <code>0đ</code>\n'
                f'{ce("👤")} Người chơi: <code>0</code>\n\n'
                f'{ce("🎁")} Hũ jackpot: <code>{fmt_money(jackpot_now)}đ</code>'
            )
            start_msg = await bot.send_message(chat_id, start_text, parse_mode=ParseMode.HTML)
            game_state["message_id"] = start_msg.message_id

            current_second = 60
            while current_second > 0:
                await asyncio.sleep(1)
                current_second -= 1

                if current_second % 10 == 0 or current_second in [5, 3, 2, 1]:
                    tai_count = sum(b["amount"] for b in game_state['bets'].values() if b["choice"] == "tai")
                    xiu_count = sum(b["amount"] for b in game_state['bets'].values() if b["choice"] == "xiu")
                    chan_count = sum(b["amount"] for b in game_state['bets'].values() if b["choice"] == "chan")
                    le_count = sum(b["amount"] for b in game_state['bets'].values() if b["choice"] == "le")
                    total_players = len(set(b["user_id"] for b in game_state['bets'].values()))
                    header = f'{ce("🚫")} <b>SẮP ĐÓNG CƯỢC!</b>' if current_second < 10 else f'{ce("⚡")} <b>ĐẶT CƯỢC NGAY!</b>'

                    edit_text = (
                        f'{ce("🎲")} <b>{get_bot_name()} - TÀI XỈU ROOM</b> {ce("🎲")}\n\n'
                        f'{ce("✍️")} <b>Phiên #{session_id}</b>\n'
                        f'{header}\n'
                        f'{ce("⏰")} Thời gian còn lại: <code>{current_second}s</code>\n\n'
                        f'{ce("💰")} <b>THỐNG KÊ TIỀN CƯỢC:</b>\n'
                        f'{ce("🎲")} TÀI: <code>{fmt_money(tai_count)}đ</code>\n'
                        f'{ce("🎲")} XỈU: <code>{fmt_money(xiu_count)}đ</code>\n'
                        f'🔴 CHẴN: <code>{fmt_money(chan_count)}đ</code>\n'
                        f'⚪ LẺ: <code>{fmt_money(le_count)}đ</code>\n'
                        f'━━━━━━━━━━━━━━━━━━━━━\n'
                        f'{ce("👤")} Tổng người chơi: <code>{total_players}</code>\n'
                        f'{ce("🎁")} Hũ jackpot: <code>{fmt_money(jackpot_now)}đ</code>'
                    )
                    try:
                        await bot.edit_message_text(edit_text, chat_id=chat_id,
                            message_id=game_state["message_id"], parse_mode=ParseMode.HTML)
                    except: pass

            game_state["status"] = "rolling"
            await bot.send_message(chat_id,
                f'{ce("🔒")} <b>ĐÃ ĐÓNG CƯỢC PHIÊN #{session_id}!</b>\n{ce("⏰")} Đang lắc 6 xúc xắc...',
                parse_mode=ParseMode.HTML)

            d1 = await bot.send_dice(chat_id, emoji="🎲")
            d2 = await bot.send_dice(chat_id, emoji="🎲")
            d3 = await bot.send_dice(chat_id, emoji="🎲")
            d4 = await bot.send_dice(chat_id, emoji="🎲")
            d5 = await bot.send_dice(chat_id, emoji="🎲")
            d6 = await bot.send_dice(chat_id, emoji="🎲")
            await asyncio.sleep(5)

            dice_values = [d1.dice.value, d2.dice.value, d3.dice.value,
                           d4.dice.value, d5.dice.value, d6.dice.value]
            total = sum(dice_values)
            res_tx = "tai" if total >= 21 else "xiu"
            res_cl = "chan" if total % 2 == 0 else "le"
            result_code = get_result_code(res_tx, res_cl)
            result_icons = get_result_icons(res_tx, res_cl)
            result_text = get_full_result_text(res_tx, res_cl)
            dice_str = " ".join(map(str, dice_values))

            total_win = 0
            total_lose = 0

            for bet_key, bet in game_state["bets"].items():
                uid = bet["user_id"]
                amt = bet["amount"]
                choice = bet["choice"]
                choice_display = {"tai":"T","xiu":"X","chan":"C","le":"L"}.get(choice, "?")

                is_win = (choice == "tai" and res_tx == "tai") or \
                         (choice == "xiu" and res_tx == "xiu") or \
                         (choice == "chan" and res_cl == "chan") or \
                         (choice == "le" and res_cl == "le")

                if is_win:
                    win_amt = int(amt * 1.95)
                    add_money(uid, win_amt, f"Thắng Tài Xỉu Room {choice.upper()}")
                    total_win += win_amt
                    new_balance = get_balance(uid)
                    try:
                        await bot.send_message(uid,
                            f'{ce("✅")} <b>THẮNG RỒI</b>  #{session_id}  ({dice_str} {result_code})\n'
                            f'{ce("✅")} <b>Lệnh Cược:</b> {choice_display} {fmt_money(amt)}đ\n'
                            f'{ce("💰")} <b>Tiền thắng:</b> +{fmt_money(win_amt)}đ\n'
                            f'{ce("💎")} <b>Số dư mới:</b> {fmt_money(new_balance)}đ\n'
                            f'{ce("🎉")} Chúc ông chủ may mắn',
                            parse_mode=ParseMode.HTML)
                    except: pass
                else:
                    total_lose += amt
                    new_balance = get_balance(uid)
                    try:
                        await bot.send_message(uid,
                            f'{ce("❌")} <b>THUA</b>  #{session_id}  ({dice_str} {result_code})\n'
                            f'{ce("❌")} <b>Lệnh Cược:</b> {choice_display} {fmt_money(amt)}đ\n'
                            f'{ce("❌")} <b>Tiền Thắng:</b> 0đ\n'
                            f'{ce("💵")} <b>Số dư mới:</b> {fmt_money(new_balance)}đ\n'
                            f'Chúc ông chủ may mắn',
                            parse_mode=ParseMode.HTML)
                    except: pass

            jackpot_amount = get_jackpot()
            jackpot_winners = []
            count_1 = dice_values.count(1)
            count_6 = dice_values.count(6)

            if count_6 >= 3:
                winners = [b for b in game_state["bets"].values() if b["choice"] == "tai"]
                if winners and jackpot_amount > 0:
                    total_bet_tai = sum(w["amount"] for w in winners)
                    for w in winners:
                        share = int(jackpot_amount * (w["amount"] / total_bet_tai))
                        add_money(w["user_id"], share, f"Nổ hũ Jackpot (3 con 6) +{share:,}đ")
                        jackpot_winners.append(f'{ce("👤")} <code>{w["user_id"]}</code>: <code>+{fmt_money(share)}đ</code>')
                        try:
                            await bot.send_message(w["user_id"],
                                f'{ce("🎉")} <b>NỔ HŨ JACKPOT!</b> {ce("🎉")}\n'
                                f'{ce("🎲")} Phiên #{session_id}: Ra 3 con 6!\n'
                                f'{ce("💰")} Cược: <code>{fmt_money(w["amount"])}đ</code>\n'
                                f'{ce("🎁")} Nhận hũ: <code>+{fmt_money(share)}đ</code>\n'
                                f'{ce("💵")} Số dư mới: <code>{fmt_money(get_balance(w["user_id"]))}đ</code>',
                                parse_mode=ParseMode.HTML)
                        except: pass
                    update_jackpot(11000000000)
                    jackpot_amount = 11000000000
            elif count_1 >= 3:
                winners = [b for b in game_state["bets"].values() if b["choice"] == "xiu"]
                if winners and jackpot_amount > 0:
                    total_bet_xiu = sum(w["amount"] for w in winners)
                    for w in winners:
                        share = int(jackpot_amount * (w["amount"] / total_bet_xiu))
                        add_money(w["user_id"], share, f"Nổ hũ Jackpot (3 con 1) +{share:,}đ")
                        jackpot_winners.append(f'{ce("👤")} <code>{w["user_id"]}</code>: <code>+{fmt_money(share)}đ</code>')
                        try:
                            await bot.send_message(w["user_id"],
                                f'{ce("🎉")} <b>NỔ HŨ JACKPOT!</b> {ce("🎉")}\n'
                                f'{ce("🎲")} Phiên #{session_id}: Ra 3 con 1!\n'
                                f'{ce("💰")} Cược: <code>{fmt_money(w["amount"])}đ</code>\n'
                                f'{ce("🎁")} Nhận hũ: <code>+{fmt_money(share)}đ</code>\n'
                                f'{ce("💵")} Số dư mới: <code>{fmt_money(get_balance(w["user_id"]))}đ</code>',
                                parse_mode=ParseMode.HTML)
                        except: pass
                    update_jackpot(11000000000)
                    jackpot_amount = 11000000000

            if group_id not in game_history:
                game_history[group_id] = []
            game_history[group_id].append({'tx': res_tx, 'cl': res_cl})
            if len(game_history[group_id]) > 10:
                game_history[group_id].pop(0)

            cau_tx = ""
            cau_cl = ""
            for h in game_history.get(group_id, []):
                cau_tx += "🔵" if h['tx'] == "tai" else "🔴"
                cau_cl += "⚪️" if h['cl'] == "chan" else "⚫️"

            final_msg = (
                f'{ce("📊")} <b>Kết quả Phiên #{session_id}</b>\n'
                f'┏━━━━━━━━━━━━━\n'
                f'┃ {dice_str} ➡️ {total} {result_text} {result_icons}\n'
                f'┃\n'
                f'┃ {ce("💰")} Tổng thắng: {fmt_money(total_win)}\n'
                f'┃ {ce("❌")} Tổng thua: {fmt_money(total_lose)}\n'
                f'┃\n'
                f'┃ {ce("🎁")} Hũ jackpot: {fmt_money(jackpot_amount)}đ\n'
                f'┗━━━━━━━━━━━━━\n'
                f'<b>Cầu gần đây:</b>\n'
                f'{cau_tx if cau_tx else "Chưa có"}\n'
                f'      🔵  Tài             🔴  XỈU\n'
                f'{cau_cl if cau_cl else "Chưa có"}\n'
                f'      ⚪️  Chẵn        ⚫️  Lẻ.'
            )

            if jackpot_winners:
                final_msg += (
                    f'\n\n{ce("🎉")} <b>NỔ HŨ JACKPOT!</b> {ce("🎉")}\n'
                    f'┏━━━━━━━━━━━━━\n'
                    f'┃ {ce("💰")} Chia theo tỉ lệ tiền cược:\n'
                    + "\n".join([f'┃ {w}' for w in jackpot_winners]) +
                    f'\n┗━━━━━━━━━━━━━\n'
                    f'🔄 Hũ đã reset về 11.000.000.000đ'
                )

            await bot.send_message(chat_id, final_msg, parse_mode=ParseMode.HTML)
            group_games.pop(group_id, None)
            await asyncio.sleep(10)

        except Exception as e:
            print(f"Lỗi run_dice_game_cycle: {e}")
            await asyncio.sleep(5)

# ============================================================
# ĐẶT CƯỢC NHÓM
# ============================================================
async def place_bet_in_group(bot, user_id, group_id, choice, amount, username=""):
    if not check_bank_linked(user_id):
        return False, (
            f'{ce("🚫")} <b>BẮT BUỘC LIÊN KẾT NGÂN HÀNG!</b>\n\n'
            f'Bạn cần liên kết tài khoản ngân hàng để tham gia cá cược.\n'
            f'{ce("👉") if False else "👉"} Dùng lệnh: <code>/lienket [Ngân_hàng] [STK] [Tên]</code>'
        )
    if not room_betting_enabled.get(group_id, True):
        return False, f'{ce("🔒")} <b>PHÒNG ĐÃ BỊ KHÓA CƯỢC!</b>'
    game = group_games.get(group_id)
    if not game or game["status"] != "betting":
        return False, f'{ce("❌")} Hiện tại không có phiên cược nào đang mở!'
    balance = get_balance(user_id)
    if balance < amount:
        return False, f'{ce("❌")} Số dư không đủ! Cần <code>{fmt_money(amount)}đ</code> nhưng chỉ có <code>{fmt_money(balance)}đ</code>.'
    if amount < 1000:
        return False, f'{ce("❌")} Số tiền cược tối thiểu là <code>1,000đ</code>!'

    note = f"Cược {choice.upper()} nhóm - {amount:,}đ"
    if not sub_money(user_id, amount, note):
        return False, f'{ce("❌")} Lỗi trừ tiền, vui lòng thử lại!'

    bet_key = f"{user_id}_{choice}"
    if bet_key in game["bets"]:
        old_amount = game["bets"][bet_key]["amount"]
        game["bets"][bet_key]["amount"] = old_amount + amount
        total_bet = game["bets"][bet_key]["amount"]
    else:
        game["bets"][bet_key] = {
            "user_id": user_id,
            "amount": amount,
            "choice": choice,
            "username": username
        }
        total_bet = amount

    new_balance = get_balance(user_id)
    choice_display = {"tai":"T","xiu":"X","chan":"C","le":"L"}.get(choice, "?")
    session_id = game.get("session_id", 0)

    msg = (
        f'{ce("✅")} Đặt thành công phiên #{session_id}\n'
        f'{choice_display} {fmt_money(total_bet)}\n'
        f'Số dư sau khi cược: {fmt_money(new_balance)}'
    )
    return True, msg

def get_group_game_status(group_id):
    game = group_games.get(group_id)
    if not game:
        return None
    return game["status"]

async def bet_group_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE, choice: str):
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            f'{ce("⚡")} Lệnh này chỉ sử dụng được trong NHÓM game!',
            parse_mode=ParseMode.HTML)
        return
    user_id = update.effective_user.id
    group_id = update.effective_chat.id
    username = update.effective_user.username or update.effective_user.first_name
    if is_banned(user_id):
        await update.message.reply_text(f'{ce("🚫")} Bạn đã bị khóa tài khoản!', parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await update.message.reply_text(
            f'{ce("❌")} Cú pháp: <code>{choice[0]} [số_tiền]</code> hoặc <code>{choice[0]} max</code>',
            parse_mode=ParseMode.HTML)
        return

    arg = ctx.args[0].lower()
    if arg == "max":
        amount = get_balance(user_id)
        if amount < 1000:
            await update.message.reply_text(f'{ce("❌")} Số dư không đủ (tối thiểu 1,000đ)!', parse_mode=ParseMode.HTML)
            return
    else:
        try:
            amount = int(arg)
        except ValueError:
            await update.message.reply_text(f'{ce("❌")} Số tiền không hợp lệ! VD: 50000 hoặc <code>max</code>', parse_mode=ParseMode.HTML)
            return

    success, message = await place_bet_in_group(ctx.bot, user_id, group_id, choice, amount, username)
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

async def bet_tai_group(update, ctx): await bet_group_handler(update, ctx, "tai")
async def bet_xiu_group(update, ctx): await bet_group_handler(update, ctx, "xiu")
async def bet_chan_group(update, ctx): await bet_group_handler(update, ctx, "chan")
async def bet_le_group(update, ctx): await bet_group_handler(update, ctx, "le")

async def group_status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(f'{ce("⚡")} Lệnh này chỉ sử dụng được trong NHÓM!', parse_mode=ParseMode.HTML)
        return
    group_id = update.effective_chat.id
    status = get_group_game_status(group_id)
    if status == "betting":
        await update.message.reply_text(
            f'{ce("🎲")} <b>ĐANG MỞ CƯỢC!</b>\nHãy đặt cược ngay: <code>t [tiền]</code> hoặc <code>t max</code>',
            parse_mode=ParseMode.HTML)
    elif status == "rolling":
        await update.message.reply_text(f'{ce("🎲")} <b>ĐANG TUNG XÚC SẮC!</b>', parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f'⏸️ <b>CHƯA CÓ PHIÊN CƯỢC NÀO</b>', parse_mode=ParseMode.HTML)

async def sd_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    balance = get_balance(uid)
    await update.message.reply_text(
        f'{ce("💰")} <b>SỐ DƯ HIỆN CÓ</b>\n'
        f'{ce("👤")} ID: <code>{uid}</code>\n'
        f'{ce("💵")} Số dư: <code>{fmt_money(balance)}đ</code>',
        parse_mode=ParseMode.HTML)

# ============================================================
# GAME PRIVATE
# ============================================================
async def play_dice_6d(update, ctx, choice_code, amount):
    uid = update.effective_user.id
    if is_game_banned(uid, 1):
        return await update.message.reply_text(f'{ce("🚫")} Bạn đã bị cấm chơi trò chơi này!', parse_mode=ParseMode.HTML)
    if check_mt('mt_taixiu') and uid not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("⚙️")} Game Tài Xỉu 6D đang bảo trì!', parse_mode=ParseMode.HTML)
    if not sub_money(uid, amount, f"Cược {choice_code}"):
        return await update.message.reply_text(f'{ce("❌")} Bạn không đủ số dư.', parse_mode=ParseMode.HTML)
    msg_status = await update.message.reply_text(f'{ce("🎲")} <b>ĐANG LẮC 6 XÚC XẮC...</b>', parse_mode=ParseMode.HTML)
    d1 = await update.message.reply_dice(emoji="🎲")
    d2 = await update.message.reply_dice(emoji="🎲")
    d3 = await update.message.reply_dice(emoji="🎲")
    d4 = await update.message.reply_dice(emoji="🎲")
    d5 = await update.message.reply_dice(emoji="🎲")
    d6 = await update.message.reply_dice(emoji="🎲")
    await asyncio.sleep(5)
    results = [d1.dice.value, d2.dice.value, d3.dice.value, d4.dice.value, d5.dice.value, d6.dice.value]
    total = sum(results)
    c = choice_code.upper()
    is_chan, is_tai = (total % 2 == 0), (total >= 21)
    is_win = check_win_by_id(1, uid)
    win = False
    if is_win:
        if (c == "XXC" and is_chan) or (c == "XXL" and not is_chan) or (c == "XXX" and not is_tai) or (c == "XXT" and is_tai):
            win = True
    if win:
        win_amt = int(amount * 1.95)
        add_money(uid, win_amt, f"Thắng {c}")
        status = f'{ce("✅")} <b>THẮNG</b> | Nhận: <code>+{fmt_money(win_amt)}đ</code>'
    else:
        status = f'{ce("❌")} <b>THUA</b>'
    res_str = "-".join(map(str, results))
    await msg_status.edit_text(
        f'{ce("🎲")} Kết quả: <b>{res_str}</b> => <b>{total}</b>\n'
        f'{status}\n'
        f'{ce("💰")} Số dư: <code>{fmt_money(get_balance(uid))}đ</code>',
        parse_mode=ParseMode.HTML)

async def play_xocdia(update, ctx, choice, amount):
    uid = update.effective_user.id
    if is_game_banned(uid, 2):
        return await update.message.reply_text(f'{ce("🚫")} Bạn đã bị cấm chơi trò chơi này!', parse_mode=ParseMode.HTML)
    if check_mt('mt_xocdia') and uid not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("⚙️")} Game Xóc Đĩa đang bảo trì!', parse_mode=ParseMode.HTML)
    if not sub_money(uid, amount, f"Cược Xóc Đĩa {choice.upper()}"):
        return await update.message.reply_text(f'{ce("❌")} Bạn không đủ số dư.', parse_mode=ParseMode.HTML)
    msg_status = await update.message.reply_text(f'💿 <b>ĐANG LẮC ĐĨA...</b>', parse_mode=ParseMode.HTML)
    await asyncio.sleep(2)
    is_win_game = check_win_by_id(2, uid)
    if is_win_game:
        win_sets = {"chan":[[1,1,0,0],[1,1,1,1],[0,0,0,0]], "le":[[1,0,0,0],[1,1,1,0]]}
        results = random.choice(win_sets[choice])
    else:
        all_sets = [[1,1,1,1],[0,0,0,0],[1,1,0,0],[1,1,1,0],[1,0,0,0]]
        def check_fail(res, c):
            r = sum(res)
            if c == "chan": return r % 2 != 0
            return r % 2 == 0
        fail_sets = [r for r in all_sets if check_fail(r, choice)]
        results = random.choice(fail_sets)
    random.shuffle(results)
    red_count = sum(results)
    icons = "".join(["🔴" if r == 1 else "⚪️" for r in results])
    is_chan = (red_count % 2 == 0)
    win = (choice == "chan" and is_chan) or (choice == "le" and not is_chan)
    if win:
        win_amt = int(amount * 1.95)
        add_money(uid, win_amt, f"Thắng Xóc Đĩa {choice.upper()}")
        status = f'{ce("🎉")} <b>THẮNG!</b> Nhận: <code>+{fmt_money(win_amt)}đ</code>'
    else:
        status = f'{ce("❌")} <b>THUA!</b>'
    await msg_status.edit_text(
        f'{ce("📊")} <b>KẾT QUẢ XÓC ĐĨA</b>\n'
        f'💿 {icons}\n'
        f'{ce("✍️")} {"CHẴN" if is_chan else "LẺ"} ({red_count} Đỏ)\n'
        f'{status}\n'
        f'{ce("💰")} Số dư: <code>{fmt_money(get_balance(uid))}đ</code>',
        parse_mode=ParseMode.HTML)

async def play_baucua(update, ctx, choice_idx, amount):
    uid = update.effective_user.id
    if is_game_banned(uid, 3):
        return await update.message.reply_text(f'{ce("🚫")} Bạn đã bị cấm chơi trò chơi này!', parse_mode=ParseMode.HTML)
    if check_mt('mt_baucua') and uid not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("⚙️")} Game Bầu Cua đang bảo trì!', parse_mode=ParseMode.HTML)
    items = ["🦌 NAI", "🦀 CUA", "🐟 CÁ", "🐯 HỔ", "🦐 TÔM", "🍐 BẦU"]
    if not sub_money(uid, amount, f"Cược Bầu Cua {items[choice_idx]}"):
        return await update.message.reply_text(f'{ce("❌")} Bạn không đủ số dư.', parse_mode=ParseMode.HTML)
    msg_bc = await update.message.reply_text(f'{ce("🎲")} <b>ĐANG LẮC BẦU CUA...</b>', parse_mode=ParseMode.HTML)
    await asyncio.sleep(2)
    is_win_bc = check_win_by_id(3, uid)
    if is_win_bc:
        res1 = choice_idx
        res2 = random.randint(0, 5)
        res3 = random.randint(0, 5)
    else:
        pool = [i for i in range(6) if i != choice_idx]
        res1, res2, res3 = random.choices(pool, k=3)
    results = [res1, res2, res3]
    random.shuffle(results)
    match_count = results.count(choice_idx)
    res_str = " | ".join([items[i] for i in results])
    if match_count > 0:
        rate = 1 + match_count
        win_amt = int(amount * rate * 0.95)
        add_money(uid, win_amt, f"Thắng Bầu Cua {items[choice_idx]} x{match_count}")
        status = f'{ce("🎉")} <b>THẮNG X{match_count}!</b> Nhận: <code>+{fmt_money(win_amt)}đ</code>'
    else:
        status = f'{ce("❌")} <b>THẤT BẠI!</b>'
    await msg_bc.edit_text(
        f'{ce("📊")} <b>KẾT QUẢ BẦU CUA</b>\n'
        f'✨ {res_str}\n'
        f'{ce("👉") if False else "👉"} Bạn chọn: {items[choice_idx]}\n'
        f'{status}\n'
        f'{ce("💰")} Số dư: <code>{fmt_money(get_balance(uid))}đ</code>',
        parse_mode=ParseMode.HTML)

# ============================================================
# /start
# ============================================================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid): return
    if is_total_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(
            f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ TOÀN BỘ</b>\n\nVui lòng quay lại sau ít phút!',
            parse_mode=ParseMode.HTML)
        return
    if is_system_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(
            f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ</b>\n\nVui lòng quay lại sau ít phút!',
            parse_mode=ParseMode.HTML)
        return
    get_user(uid)
    if ctx.args:
        try:
            ref = int(ctx.args[0])
            if ref != uid:
                row = query("SELECT refed FROM users WHERE user_id=%s", (uid,))
                if row and row[0][0] == 0:
                    if query("SELECT 1 FROM users WHERE user_id=%s", (ref,)):
                        add_money(ref, 500, "Ref bonus")
                        query("UPDATE users SET refs=refs+1 WHERE user_id=%s", (ref,))
                        query("UPDATE users SET refed=1 WHERE user_id=%s", (uid,))
        except: pass
    menu = ReplyKeyboardMarkup([
        ["🎮 DANH SÁCH GAME", "👤 TÀI KHOẢN"],
        ["💳 NẠP TIỀN", "🛒 RÚT TIỀN"],
        ["📜 LỊCH SỬ"],
        ["📞 HỖ TRỢ"]
    ], resize_keyboard=True)
    welcome_text = (
        f'{ce("🎉")} <b>CHÀO MỪNG {update.effective_user.first_name.upper()} ĐÃ THAM GIA!</b>\n\n'
        f'{ce("🛡")} <b>{get_bot_name()}</b>\n'
        f'Hệ thống trò chơi minh bạch — uy tín hàng đầu.\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("💰")} <b>MIN RÚT TIỀN:</b> <code>50,000đ</code>\n'
        f'{ce("💵")} <b>MIN NẠP TIỀN:</b> <code>10,000đ</code>\n\n'
        f'{ce("⚖️")} <b>CAM KẾT MINH BẠCH:</b>\n'
        f'• <b>100%</b> Kết quả hoàn toàn ngẫu nhiên.\n'
        f'• {ce("🔥")} <b>KHÔNG</b> can thiệp kết quả dưới mọi hình thức.\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("🎯")} Chúc bạn có những trải nghiệm may mắn và thú vị!'
    )
    await update.message.reply_text(welcome_text, reply_markup=menu, parse_mode=ParseMode.HTML)

# ============================================================
# /lienket
# ============================================================
async def lien_ket(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid): return
    if is_total_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ TOÀN BỘ</b>', parse_mode=ParseMode.HTML)
        return
    res = query("SELECT bank FROM users WHERE user_id=%s", (uid,))
    if res and res[0][0] is not None:
        return await update.message.reply_text(
            f'{ce("❌")} Bạn đã liên kết ngân hàng rồi. Để thay đổi, vui lòng liên hệ Admin!',
            parse_mode=ParseMode.HTML)
    if not ctx.args or len(ctx.args) < 3:
        return await update.message.reply_text(
            f'{ce("⚡")} <b>Cú pháp liên kết:</b>\n'
            f'<code>/lienket [Ngân_hàng] [STK] [Chủ_TK]</code>\n\n'
            f'VD: <code>/lienket MBBANK 0123456 NGUYEN VAN A</code>',
            parse_mode=ParseMode.HTML)
    bank = ctx.args[0].upper()
    stk = ctx.args[1]
    name = " ".join(ctx.args[2:]).upper()
    query("UPDATE users SET bank=%s, stk=%s, name=%s, bank_linked=1 WHERE user_id=%s", (bank, stk, name, uid))
    await update.message.reply_text(
        f'{ce("✅")} <b>LIÊN KẾT THÀNH CÔNG</b>\n\n'
        f'{ce("💳")} Ngân hàng: {bank}\n'
        f'{ce("💰")} STK: <code>{stk}</code>\n'
        f'{ce("👤")} Chủ TK: {name}\n\n'
        f'{ce("🎮")} Bạn đã có thể tham gia chơi game!',
        parse_mode=ParseMode.HTML)

# ============================================================
# /rut
# ============================================================
async def rut(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid): return
    if is_feature_banned(uid, 'rut'):
        return await update.message.reply_text(
            f'{ce("🚫")} Tính năng RÚT TIỀN của bạn đã bị khóa. Vui lòng liên hệ Admin!',
            parse_mode=ParseMode.HTML)
    if check_mt('mt_rut') and uid not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("⚙️")} Hệ thống Rút Tiền đang bảo trì, vui lòng quay lại sau!', parse_mode=ParseMode.HTML)
    if is_total_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ TOÀN BỘ</b>', parse_mode=ParseMode.HTML)
        return
    res = query("SELECT bank, stk, name, balance FROM users WHERE user_id=%s", (uid,))
    if not res or not res[0][0] or not res[0][1]:
        return await update.message.reply_text(
            f'{ce("❌")} Bạn chưa liên kết tài khoản ngân hàng.\n'
            f'{ce("👉") if False else "👉"} Hãy dùng lệnh: <code>/lienket [Ngân_hàng] [STK] [Tên]</code>\n\n'
            f'{ce("📌")} <b>MIN RÚT:</b> <code>50,000đ</code>',
            parse_mode=ParseMode.HTML)
    u = res[0]
    if not ctx.args:
        return await update.message.reply_text(
            f'{ce("💰")} <b>Số dư:</b> <code>{fmt_money(u[3])}đ</code>\n'
            f'{ce("📌")} <b>MIN RÚT:</b> <code>50,000đ</code>\n\n'
            f'{ce("✍️")} Nhập số tiền muốn rút: <code>/rut [số_tiền]</code>',
            parse_mode=ParseMode.HTML)
    try:
        amount = int(ctx.args[0])
        if amount < MIN_WITHDRAW:
            return await update.message.reply_text(
                f'{ce("❌")} Số tiền rút tối thiểu là <code>{fmt_money(MIN_WITHDRAW)}đ</code>',
                parse_mode=ParseMode.HTML)
        remaining = get_remaining_bet_required(uid)
        if remaining > 0:
            return await update.message.reply_text(
                f'{ce("⚠️") if "⚠️" in CUSTOM_EMOJI else "⚠️"} <b>CHƯA ĐỦ ĐIỀU KIỆN RÚT TIỀN!</b>\n\n'
                f'{ce("💰")} Bạn đang có tiền khuyến mãi cần cược đủ <b>x3</b> vòng.\n'
                f'{ce("📊")} <b>Cần cược thêm:</b> <code>{fmt_money(remaining)}đ</code>',
                parse_mode=ParseMode.HTML)
        if sub_money(uid, amount, "Rút tiền"):
            bank, stk, name = u[0], u[1], u[2]
            now_str = get_vietnam_datetime_db()
            query("INSERT INTO withdraw_history (user_id, amount, status, time) VALUES (%s, %s, %s, %s)", (uid, amount, 'pending', now_str))
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Duyệt", callback_data=f"ok_{uid}_{amount}"),
                InlineKeyboardButton("❌ Từ chối", callback_data=f"no_{uid}_{amount}")
            ]])
            for admin_id in ADMIN_IDS:
                try:
                    await ctx.bot.send_message(admin_id,
                        f'{ce("🎁")} <b>YÊU CẦU RÚT TIỀN MỚI</b> {ce("🎁")}\n'
                        f'━━━━━━━━━━━━━━━━━━━━━\n'
                        f'{ce("👤")} <b>ID:</b> <code>{uid}</code>\n'
                        f'{ce("💰")} <b>Số tiền:</b> <code>{fmt_money(amount)}đ</code>\n'
                        f'{ce("💳")} <b>Ngân hàng:</b> <code>{bank}</code>\n'
                        f'{ce("💰")} <b>STK:</b> <code>{stk}</code>\n'
                        f'{ce("👤")} <b>Chủ TK:</b> <code>{name}</code>\n'
                        f'{ce("⏰")} <b>Thời gian:</b> <code>{now_str}</code>',
                        reply_markup=keyboard, parse_mode=ParseMode.HTML)
                except Exception as e:
                    print(f"Không thể gửi tin nhắn đến admin {admin_id}: {e}")
            await update.message.reply_text(
                f'{ce("✅")} <b>GỬI YÊU CẦU RÚT THÀNH CÔNG!</b>\n\n'
                f'{ce("💰")} Số tiền: <code>{fmt_money(amount)}đ</code>\n'
                f'{ce("⏰")} Vui lòng chờ Admin duyệt (1-5 phút).',
                parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f'{ce("❌")} Số dư không đủ.', parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} Số tiền không hợp lệ.', parse_mode=ParseMode.HTML)

# ============================================================
# /code
# ============================================================
async def nhap_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid): return
    if not ctx.args:
        await update.message.reply_text(f'{ce("❌")} Vui lòng nhập kèm mã. VD: <code>/code ABC123</code>', parse_mode=ParseMode.HTML)
        return
    today = get_vietnam_date()
    code_count = query("SELECT COUNT(*) FROM code_usage WHERE user_id=%s AND used_date=%s", (uid, today))
    if code_count and code_count[0][0] >= 3:
        await update.message.reply_text(
            f'{ce("🚫")} <b>GIỚI HẠN CODE HÔM NAY!</b>\n\n'
            f'Bạn chỉ có thể nhập tối đa <b>3 CODE/ngày</b>.',
            parse_mode=ParseMode.HTML)
        return
    code_str = ctx.args[0].strip().upper()
    data = query("SELECT * FROM codes WHERE code=%s", (code_str,))
    if not data:
        await update.message.reply_text(f'{ce("❌")} Mã quà tặng không tồn tại.', parse_mode=ParseMode.HTML)
        return
    reward, uses = data[0][1], data[0][2]
    if uses <= 0:
        await update.message.reply_text(f'{ce("❌")} Mã quà tặng này đã hết lượt sử dụng.', parse_mode=ParseMode.HTML)
        return
    query("INSERT INTO code_usage VALUES(%s, %s, %s)", (uid, code_str, today))
    add_money(uid, reward, f"Code: {code_str}")
    query("UPDATE codes SET uses=uses-1 WHERE code=%s", (code_str,))
    remaining = 3 - (code_count[0][0] + 1)
    await update.message.reply_text(
        f'{ce("🎉")} <b>NHẬN QUÀ THÀNH CÔNG!</b>\n\n'
        f'{ce("💰")} Bạn nhận được: <code>+{fmt_money(reward)}đ</code>\n'
        f'{ce("📊")} Hôm nay còn: <code>{remaining}/3</code> lượt nhập code.',
        parse_mode=ParseMode.HTML)

# ============================================================
# /his
# ============================================================
async def history_pro(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid): return
    if is_total_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ TOÀN BỘ</b>', parse_mode=ParseMode.HTML)
        return
    data = query("SELECT amount, note, time FROM history WHERE user_id=%s ORDER BY time DESC LIMIT 20", (uid,))
    if not data:
        await update.message.reply_text(f'{ce("📥")} Lịch sử trống.', parse_mode=ParseMode.HTML)
    else:
        msg = f'{ce("📜")} <b>LỊCH SỬ CHI TIẾT:</b>\n\n'
        for d in data:
            icon = "➕" if d[0] > 0 else "➖"
            msg += f'{icon} <code>{fmt_money(d[0])}đ</code> | {html.escape(d[1])} | <i>{d[2]}</i>\n'
        if len(msg) > 4000:
            for x in range(0, len(msg), 4000):
                await update.message.reply_text(msg[x:x+4000], parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# ============================================================
# /checkprogress
# ============================================================
async def check_bet_progress_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid): return
    status = get_bet_progress_status(uid)
    if not status:
        await update.message.reply_text(
            f'{ce("📊")} <b>KHÔNG CÓ KHUYẾN MÃI NÀO ĐANG HOẠT ĐỘNG</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━━\n'
            f'{ce("💰")} Bạn hiện không có tiền khuyến mãi cần hoàn thành cược.',
            parse_mode=ParseMode.HTML)
        return
    percent = status['percent']
    bar_length = 20
    filled = int(bar_length * percent / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    message = (
        f'{ce("📊")} <b>TIẾN ĐỘ HOÀN THÀNH CƯỢC</b> {ce("📊")}\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("🎁")} <b>Tiền khuyến mãi đã nhận:</b> <code>+{fmt_money(status["bonus_amount"])}đ</code>\n'
        f'{ce("🎯")} <b>Yêu cầu cược:</b> <code>{fmt_money(status["required_bet"])}đ</code> (x3 vòng)\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("📈") if False else "📈"} <b>Tiến độ:</b>\n'
        f'<code>{bar}</code> <code>{percent:.1f}%</code>\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("✅")} <b>Đã cược:</b> <code>{fmt_money(status["current_bet"])}đ</code>\n'
        f'{ce("⚠️") if "⚠️" in CUSTOM_EMOJI else "⚠️"} <b>Cần cược thêm:</b> <code>{fmt_money(status["remaining"])}đ</code>\n'
    )
    if status['is_completed']:
        message += f'{ce("🎉")} <b>CHÚC MỪNG! BẠN ĐÃ HOÀN THÀNH!</b> {ce("🎉")}'
    else:
        message += f'{ce("🔥")} <b>CỐ GẮNG LÊN!</b>'
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

# ============================================================
# /xd /bc
# ============================================================
async def xd_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/xd [chan/le] [số_tiền]</code>', parse_mode=ParseMode.HTML)
    choice = ctx.args[0].lower()
    if choice not in ["chan", "le"]:
        return await update.message.reply_text(f'{ce("❌")} Chỉ chọn <code>chan</code> hoặc <code>le</code>!', parse_mode=ParseMode.HTML)
    try:
        amt = int(ctx.args[1])
    except:
        return await update.message.reply_text(f'{ce("❌")} Số tiền không hợp lệ!', parse_mode=ParseMode.HTML)
    await play_xocdia(update, ctx, choice, amt)

async def bc_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/bc [nai/cua/ca/ho/tom/bau] [số_tiền]</code>', parse_mode=ParseMode.HTML)
    choice_name = ctx.args[0].lower()
    map_idx = {"nai":0,"cua":1,"ca":2,"ho":3,"tom":4,"bau":5}
    if choice_name not in map_idx:
        return await update.message.reply_text(f'{ce("❌")} Chỉ chọn: nai, cua, ca, ho, tom, bau', parse_mode=ParseMode.HTML)
    try:
        amt = int(ctx.args[1])
    except:
        return await update.message.reply_text(f'{ce("❌")} Số tiền không hợp lệ!', parse_mode=ParseMode.HTML)
    await play_baucua(update, ctx, map_idx[choice_name], amt)

# ============================================================
# HANDLE MENU
# ============================================================
async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid, txt = update.effective_user.id, update.message.text
    if not txt or is_banned(uid): return
    if is_total_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ TOÀN BỘ</b>', parse_mode=ParseMode.HTML)
        return
    if is_system_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ</b>', parse_mode=ParseMode.HTML)
        return
    user_reply = update.message

    if txt == "👤 TÀI KHOẢN":
        res = query("SELECT balance, bank, stk, name, refs, total_bet FROM users WHERE user_id=%s", (uid,))
        if not res:
            get_user(uid)
            u = (0, None, None, None, 0, 0)
        else:
            u = res[0]
        vip_name, _ = get_vip_info(u[5])
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📥 Lịch sử Nạp", callback_data="his_deposit"),
            InlineKeyboardButton("📤 Lịch sử Rút", callback_data="his_withdraw")
        ]])
        msg = (
            f'{ce("👤")} <b>THÔNG TIN TÀI KHOẢN</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━━\n'
            f'{ce("🆔")} ID: <code>{uid}</code>\n'
            f'{ce("👑")} <b>Cấp VIP:</b> <code>{vip_name}</code>\n'
            f'{ce("💰")} Số dư: <code>{fmt_money(u[0])}đ</code>\n'
            f'{ce("📊")} <b>Tổng cược:</b> <code>{fmt_money(u[5])}đ</code>\n'
            f'{ce("👤")} Đã mời: <code>{u[4]}</code> người\n'
            f'{ce("💳")} Ngân hàng: <code>{u[1] or "Chưa liên kết"}</code>\n'
            f'{ce("💰")} STK: <code>{u[2] or "Chưa liên kết"}</code>\n'
            f'{ce("👤")} Tên: <code>{u[3] or "Chưa liên kết"}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━━'
        )
        return await user_reply.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

    if txt == "💳 NẠP TIỀN":
        if is_feature_banned(uid, 'nap'):
            return await user_reply.reply_text(f'{ce("🚫")} Tính năng NẠP TIỀN đã bị khóa!', parse_mode=ParseMode.HTML)
        if check_mt('mt_nap') and uid not in ADMIN_IDS:
            return await user_reply.reply_text(f'{ce("⚙️")} Nạp Tiền đang bảo trì!', parse_mode=ParseMode.HTML)
        qr_link, qr_text = get_deposit_info(uid)
        return await user_reply.reply_photo(photo=qr_link, caption=qr_text, parse_mode=ParseMode.HTML)

    if txt == "🎮 DANH SÁCH GAME":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 TÀI XỈU 6D", callback_data="menu_tx"),
             InlineKeyboardButton("💿 XÓC ĐĨA", callback_data="menu_xocdia")],
            [InlineKeyboardButton("🦀 BẦU CUA TÔM CÁ", callback_data="menu_bc")],
            [InlineKeyboardButton("🎲 TÀI XỈU ROOM", callback_data="menu_taixiu_room")]
        ])
        return await user_reply.reply_text(
            f'{ce("🎮")} <b>DANH SÁCH TRÒ CHƠI</b>\nVui lòng chọn game:',
            reply_markup=kb, parse_mode=ParseMode.HTML)

    if txt == "🛒 RÚT TIỀN":
        if is_feature_banned(uid, 'rut'):
            return await user_reply.reply_text(f'{ce("🚫")} Tính năng RÚT TIỀN đã bị khóa!', parse_mode=ParseMode.HTML)
        if check_mt('mt_rut') and uid not in ADMIN_IDS:
            return await user_reply.reply_text(f'{ce("⚙️")} Rút Tiền đang bảo trì!', parse_mode=ParseMode.HTML)
        res = query("SELECT bank, stk, name FROM users WHERE user_id=%s", (uid,))
        if not res or not res[0][0] or not res[0][1]:
            await user_reply.reply_text(
                f'{ce("❌")} Bạn chưa liên kết bank.\n'
                f'{ce("👉") if False else "👉"} <code>/lienket [Bank] [STK] [Tên]</code>\n\n'
                f'{ce("📌")} <b>MIN RÚT:</b> <code>50,000đ</code>',
                parse_mode=ParseMode.HTML)
        else:
            u = res[0]
            await user_reply.reply_text(
                f'{ce("💳")} <b>TÀI KHOẢN RÚT:</b>\n'
                f'{ce("💳")} Bank: {u[0]}\n'
                f'{ce("💰")} STK: <code>{u[1]}</code>\n'
                f'{ce("👤")} Tên: {u[2]}\n\n'
                f'{ce("📌")} <b>MIN RÚT:</b> <code>50,000đ</code>\n\n'
                f'{ce("👉") if False else "👉"} <code>/rut [số tiền]</code>',
                parse_mode=ParseMode.HTML)
        return

    if txt == "📜 LỊCH SỬ":
        return await history_pro(update, ctx)

    if txt == "📞 HỖ TRỢ":
        msg = (
            f'{ce("📞")} <b>HỖ TRỢ KHÁCH HÀNG</b>\n\n'
            f'{ce("👤")} <b>Hỗ Trợ:</b> @echcutodz\n'
            f'{ce("💬")} Phản hồi trong giờ hành chính!\n'
            f'━━━━━━━━━━━━━━━━━━━━━\n'
            f'{ce("📌")} <b>Các vấn đề có thể liên hệ:</b>\n'
            f'• Nạp tiền chậm\n'
            f'• Rút tiền chưa được duyệt\n'
            f'• Khiếu nại kết quả game'
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 NHẮN HỖ TRỢ", url="https://t.me/echcutodz")]])
        return await user_reply.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

    if len(txt.split()) == 2 and txt.split()[1].isdigit():
        parts = txt.split()
        code, amt = parts[0].upper(), int(parts[1])
        if code in ["XXC", "XXL", "XXX", "XXT"]:
            if check_mt('mt_taixiu') and uid not in ADMIN_IDS:
                return await update.message.reply_text(f'{ce("⚙️")} Game Tài Xỉu đang bảo trì!', parse_mode=ParseMode.HTML)
            return await play_dice_6d(update, ctx, code, amt)

# ============================================================
# GROUP MESSAGE HANDLER
# ============================================================
async def handle_group_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await main_handler(update, ctx)
        return
    if is_total_maintenance() and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ TOÀN BỘ</b>', parse_mode=ParseMode.HTML)
        return
    await track_interaction(update, ctx)
    text = update.message.text
    if not text: return
    parts = text.strip().split()
    if not parts: return
    command = parts[0].lower()
    fake_ctx = type('obj', (object,), {'bot': ctx.bot, 'args': parts[1:], 'user_data': ctx.user_data, 'chat_data': ctx.chat_data})()
    if command == "t":
        await bet_tai_group(update, fake_ctx); return
    if command == "x":
        await bet_xiu_group(update, fake_ctx); return
    if command == "c":
        await bet_chan_group(update, fake_ctx); return
    if command == "l":
        await bet_le_group(update, fake_ctx); return
    await main_handler(update, ctx)

async def main_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_total_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ TOÀN BỘ</b>', parse_mode=ParseMode.HTML)
        return
    await handle(update, ctx)

# ============================================================
# ADMIN COMMANDS (đã chuyển sang HTML)
# ============================================================
@admin_only
async def nap_tien_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(ctx.args[0])
        amount = int(ctx.args[1])
        if amount < 10000:
            await update.message.reply_text(f'{ce("❌")} Số tiền nạp tối thiểu là <code>10,000đ</code>!', parse_mode=ParseMode.HTML)
            return
        now_str = get_vietnam_datetime_db()
        query("INSERT INTO deposit_history (user_id, amount, admin_id, status, time) VALUES (%s, %s, %s, %s, %s)", (target_id, amount, update.effective_user.id, 'success', now_str))
        add_money(target_id, amount, f"Nạp tiền +{amount:,}đ")
        try:
            await ctx.bot.send_message(chat_id=LOG_GROUP_ID,
                text=f'{ce("✅")} <b>THÔNG BÁO NẠP TIỀN</b>\n{ce("👤")} ID: <code>{target_id}</code>\n{ce("💰")} Số tiền: <code>+{fmt_money(amount)}đ</code>\n{ce("👑")} Admin: <code>{update.effective_user.id}</code>',
                parse_mode=ParseMode.HTML)
        except: pass
        bonus_amount = 0
        if amount >= 1000000: bonus_amount = 888000
        elif amount >= 500000: bonus_amount = 588000
        elif amount >= 200000: bonus_amount = 208000
        elif amount >= 50000: bonus_amount = 58000
        if bonus_amount > 0:
            required_bet = bonus_amount * 3
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🎁 NHẬN KHUYẾN MÃI", callback_data=f"accept_bonus_{target_id}_{bonus_amount}_{required_bet}"),
                InlineKeyboardButton("❌ TỪ CHỐI", callback_data=f"reject_bonus_{target_id}")
            ]])
            try:
                await ctx.bot.send_message(target_id,
                    f'{ce("✅")} <b>NẠP TIỀN THÀNH CÔNG!</b>\n\n'
                    f'{ce("💰")} Số tiền nạp: <code>+{fmt_money(amount)}đ</code>\n'
                    f'{ce("💎")} Số dư hiện tại: <code>{fmt_money(get_balance(target_id))}đ</code>\n\n'
                    f'{ce("🎁")} <b>BẠN CÓ MUỐN NHẬN THÊM KHUYẾN MÃI?</b>\n'
                    f'━━━━━━━━━━━━━━━━━━━━━\n'
                    f'✨ <b>Thưởng nạp:</b> <code>+{fmt_money(bonus_amount)}đ</code>\n'
                    f'{ce("🎯")} <b>Yêu cầu cược:</b> x3 vòng (<code>{fmt_money(required_bet)}đ</code>)\n'
                    f'━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'{ce("⚠️") if "⚠️" in CUSTOM_EMOJI else "⚠️"} Lưu ý: Tiền khuyến mãi cần cược đủ x3 vòng mới có thể rút!',
                    reply_markup=keyboard, parse_mode=ParseMode.HTML)
            except Exception as e:
                print(f"Lỗi gửi tin nhắn user {target_id}: {e}")
        else:
            try:
                bill = (
                    f'{ce("✅")} <b>NẠP TIỀN THÀNH CÔNG</b>\n'
                    f'━━━━━━━━━━━━━━━━━━━━━\n'
                    f'{ce("📥")} <b>Số tiền:</b> <code>+{fmt_money(amount)}đ</code>\n'
                    f'{ce("⏰")} <b>Thời gian:</b> {now_str}\n'
                    f'━━━━━━━━━━━━━━━━━━━━━\n'
                    f'{ce("💰")} Số dư hiện tại: <code>{fmt_money(get_balance(target_id))}đ</code>'
                )
                await ctx.bot.send_message(chat_id=target_id, text=bill, parse_mode=ParseMode.HTML)
            except Exception as e:
                print(f"Lỗi gửi tin nhắn user {target_id}: {e}")
        await update.message.reply_text(
            f'{ce("✅")} <b>NẠP TIỀN THÀNH CÔNG</b>\n\n'
            f'{ce("👤")} ID: <code>{target_id}</code>\n'
            f'{ce("💰")} Số tiền: <code>+{fmt_money(amount)}đ</code>',
            parse_mode=ParseMode.HTML)
    except (IndexError, ValueError):
        await update.message.reply_text(
            f'{ce("❌")} Cú pháp: <code>/nap [ID] [Số tiền]</code>\n{ce("📌")} Min nạp: <code>10,000đ</code>',
            parse_mode=ParseMode.HTML)

@admin_only
async def add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid, amt = int(ctx.args[0]), int(ctx.args[1])
        add_money(uid, amt, "Admin cộng tiền")
        await update.message.reply_text(f'{ce("✅")} Đã cộng <code>{fmt_money(amt)}đ</code> cho ID <code>{uid}</code>', parse_mode=ParseMode.HTML)
    except: pass

@admin_only
async def sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid, amt = int(ctx.args[0]), int(ctx.args[1])
        sub_money(uid, amt, "Admin trừ tiền")
        await update.message.reply_text(f'{ce("✅")} Đã trừ <code>{fmt_money(amt)}đ</code> của ID <code>{uid}</code>', parse_mode=ParseMode.HTML)
    except: pass

@admin_only
async def ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(ctx.args[0])
        query("INSERT INTO banned(user_id) VALUES(%s) ON CONFLICT (user_id) DO NOTHING", (uid,))
        await update.message.reply_text(f'{ce("🚫")} Đã chặn người dùng <code>{uid}</code>', parse_mode=ParseMode.HTML)
    except: pass

@admin_only
async def unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(ctx.args[0])
        query("DELETE FROM banned WHERE user_id=%s", (uid,))
        await update.message.reply_text(f'{ce("✅")} Đã bỏ chặn người dùng <code>{uid}</code>', parse_mode=ParseMode.HTML)
    except: pass

@admin_only
async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    res = query("SELECT COUNT(*) FROM users")
    total = res[0][0] if res else 0
    await update.message.reply_text(
        f'{ce("📊")} <b>THỐNG KÊ:</b>\n\n{ce("👤")} Tổng số người dùng: <code>{total}</code>',
        parse_mode=ParseMode.HTML)

@admin_only
async def all_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE, page=0):
    limit = 20
    offset = page * limit
    users = query("SELECT user_id, balance FROM users ORDER BY user_id DESC LIMIT %s OFFSET %s", (limit, offset))
    res_total = query("SELECT COUNT(*) FROM users")
    total_users = res_total[0][0] if res_total else 0
    total_pages = (total_users + limit - 1) // limit
    if not users:
        return await update.message.reply_text(f'Chưa có người dùng nào.', parse_mode=ParseMode.HTML)
    kb = []
    for u in users:
        u_id, bal = u[0], u[1]
        status = "🚫" if is_banned(u_id) else "🟢"
        kb.append([InlineKeyboardButton(f"{status} ID: {u_id} | {bal:,}đ", callback_data=f"adm_manage_{u_id}_{page}")])
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"adm_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"Trang {page+1}/{total_pages}", callback_data="none"))
    if (page + 1) < total_pages:
        nav_buttons.append(InlineKeyboardButton("Sau ➡️", callback_data=f"adm_page_{page+1}"))
    kb.append(nav_buttons)
    kb.append([InlineKeyboardButton("❌ ĐÓNG BẢNG", callback_data="close_admin")])
    text = f'{ce("👤")} <b>DANH SÁCH NGƯỜI DÙNG</b> (Tổng: {total_users})\nBấm vào User để xem chi tiết:'
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

@admin_only
async def admin_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(ctx.args[0])
        res = query("SELECT balance, refs, bank, stk, name, last_checkin, total_bet FROM users WHERE user_id=%s", (target_id,))
        if not res:
            return await update.message.reply_text(f'{ce("❌")} Không tìm thấy người dùng này.', parse_mode=ParseMode.HTML)
        u = res[0]
        msg = (
            f'{ce("📜")} <b>THÔNG TIN CHI TIẾT USER</b> <code>{target_id}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━━\n'
            f'{ce("💰")} Số dư: <code>{fmt_money(u[0])}đ</code>\n'
            f'{ce("📊")} Tổng cược: <code>{fmt_money(u[6])}đ</code>\n'
            f'{ce("👤")} Số người mời: <code>{u[1]}</code>\n'
            f'{ce("💳")} Ngân hàng: <code>{u[2] or "Chưa cập nhật"}</code>\n'
            f'{ce("💰")} STK: <code>{u[3] or "Chưa cập nhật"}</code>\n'
            f'{ce("👤")} Tên: <code>{u[4] or "Chưa cập nhật"}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━━'
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/info [ID]</code>', parse_mode=ParseMode.HTML)

# ============================================================
# CÁC LỆNH ADMIN CÒN LẠI
# ============================================================
@admin_only
async def history_all_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = query("SELECT * FROM history ORDER BY time DESC LIMIT 50")
    msg = f'{ce("📊")} <b>LỊCH SỬ TOÀN HỆ THỐNG:</b>\n\n'
    if data:
        for d in data:
            msg += f'{ce("👤")} <code>{d[0]}</code> | <code>{fmt_money(d[1])}đ</code> | {html.escape(d[2])}\n'
    if len(msg) > 4000:
        for x in range(0, len(msg), 4000):
            await update.message.reply_text(msg[x:x+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg or "Trống", parse_mode=ParseMode.HTML)

@admin_only
async def broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/send [nội dung]</code>', parse_mode=ParseMode.HTML)
    msg_to_send = " ".join(ctx.args)
    users = query("SELECT user_id FROM users")
    sent, failed = 0, 0
    status_msg = await update.message.reply_text(f'{ce("🚀") if "🚀" in CUSTOM_EMOJI else "🚀"} Đang gửi tới {len(users)} người...', parse_mode=ParseMode.HTML)
    for user in users:
        try:
            await ctx.bot.send_message(chat_id=user[0],
                text=f'{ce("🔔")} <b>THÔNG BÁO MỚI</b>\n\n{html.escape(msg_to_send)}',
                parse_mode=ParseMode.HTML)
            sent += 1
            if sent % 20 == 0: await asyncio.sleep(1)
        except: failed += 1
    await status_msg.edit_text(
        f'{ce("✅")} <b>HOÀN THÀNH</b>\n\n'
        f'{ce("📊")} Thành công: <code>{sent}</code>\n'
        f'{ce("❌")} Thất bại: <code>{failed}</code>',
        parse_mode=ParseMode.HTML)

@admin_only
async def reply_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(ctx.args[0])
        msg_reply = " ".join(ctx.args[1:])
        await ctx.bot.send_message(chat_id=uid,
            text=f'{ce("✉️")} <b>PHẢN HỒI TỪ ADMIN:</b>\n\n{html.escape(msg_reply)}',
            parse_mode=ParseMode.HTML)
        await update.message.reply_text(f'{ce("✅")} Đã gửi phản hồi tới <code>{uid}</code>', parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/rep [ID] [Nội dung]</code>', parse_mode=ParseMode.HTML)

@admin_only
async def check_user_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(ctx.args[0])
        data = query("SELECT amount, note, time FROM history WHERE user_id=%s ORDER BY time DESC", (uid,))
        if not data:
            await update.message.reply_text(f'{ce("📥")} User <code>{uid}</code> chưa có giao dịch.', parse_mode=ParseMode.HTML)
        else:
            msg = f'{ce("📜")} <b>LỊCH SỬ USER <code>{uid}</code>:</b>\n\n'
            for d in data:
                msg += f'{ce("💰")} <code>{fmt_money(d[0])}</code> | {html.escape(d[1])} | <i>{d[2]}</i>\n'
            if len(msg) > 4000:
                for x in range(0, len(msg), 4000):
                    await update.message.reply_text(msg[x:x+4000], parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/check [ID]</code>', parse_mode=ParseMode.HTML)

@admin_only
async def dashboard_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    today = get_vietnam_date()
    this_month = get_vietnam_time().strftime("/%m/%Y")
    nap_today = query("SELECT SUM(amount) FROM history WHERE amount > 0 AND note ILIKE '%nạp%' AND time LIKE %s", (f"%{today}%",))[0][0] or 0
    rut_today = query("SELECT SUM(amount) FROM history WHERE amount < 0 AND note ILIKE '%Rút%' AND time LIKE %s", (f"%{today}%",))[0][0] or 0
    nap_month = query("SELECT SUM(amount) FROM history WHERE amount > 0 AND note ILIKE '%nạp%' AND time LIKE %s", (f"%{this_month}%",))[0][0] or 0
    rut_month = query("SELECT SUM(amount) FROM history WHERE amount < 0 AND note ILIKE '%Rút%' AND time LIKE %s", (f"%{this_month}%",))[0][0] or 0
    total_cuoc = query("SELECT SUM(amount) FROM history WHERE amount < 0 AND note NOT ILIKE '%Rút%' AND note NOT ILIKE '%trừ tiền%'")[0][0] or 0
    total_thang = query("SELECT SUM(amount) FROM history WHERE amount > 0 AND note NOT ILIKE '%nạp%' AND note NOT ILIKE '%Code%' AND note NOT ILIKE '%Checkin%'")[0][0] or 0
    loi_nhuan = abs(total_cuoc) - total_thang
    msg = (
        f'{ce("📊")} <b>BẢNG THỐNG KÊ DOANH THU</b>\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'📅 <b>Hôm nay ({today}):</b>\n'
        f'  {ce("📥")} Tổng nạp: <code>+{fmt_money(nap_today)}đ</code>\n'
        f'  {ce("📤")} Tổng rút: <code>{fmt_money(rut_today)}đ</code>\n\n'
        f'📅 <b>Tháng này ({get_vietnam_time().month}):</b>\n'
        f'  {ce("📥")} Tổng nạp: <code>+{fmt_money(nap_month)}đ</code>\n'
        f'  {ce("📤")} Tổng rút: <code>{fmt_money(rut_month)}đ</code>\n\n'
        f'📈 <b>Tổng kết Game (All time):</b>\n'
        f'  {ce("💰")} Lợi nhuận ròng: <code>{fmt_money(loi_nhuan)}đ</code>\n'
        f'━━━━━━━━━━━━━━━━━━━━━'
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
async def tong_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t_nap = query("SELECT SUM(amount) FROM history WHERE amount > 0 AND note ILIKE '%nạp%'")[0][0] or 0
    t_rut = query("SELECT SUM(amount) FROM history WHERE amount < 0 AND note ILIKE '%Rút%'")[0][0] or 0
    t_cuoc = query("SELECT SUM(amount) FROM history WHERE amount < 0 AND note NOT ILIKE '%Rút%' AND note NOT ILIKE '%trừ tiền%'")[0][0] or 0
    t_thang = query("SELECT SUM(amount) FROM history WHERE amount > 0 AND note NOT ILIKE '%nạp%' AND note NOT ILIKE '%Code%' AND note NOT ILIKE '%Checkin%'")[0][0] or 0
    loi_nhuan = abs(t_cuoc) - t_thang
    msg = (
        f'{ce("📊")} <b>TỔNG QUAN TÀI CHÍNH HỆ THỐNG</b>\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("📥")} <b>Tổng Nạp:</b> <code>+{fmt_money(t_nap)}đ</code>\n'
        f'{ce("📤")} <b>Tổng Rút:</b> <code>{fmt_money(t_rut)}đ</code>\n'
        f'{ce("💰")} <b>Lợi Nhuận Thực Tế (Game):</b> <code>{fmt_money(loi_nhuan)}đ</code>\n'
        f'━━━━━━━━━━━━━━━━━━━━━'
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
async def soduall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    users = query("SELECT user_id, balance FROM users WHERE balance > 0 ORDER BY balance DESC")
    if not users:
        return await update.message.reply_text(f'Hiện không có ai có số dư lớn hơn 0.', parse_mode=ParseMode.HTML)
    text = f'{ce("💰")} <b>DANH SÁCH SỐ DƯ TẤT CẢ ID:</b>\n'
    for u in users:
        text += f'ID: <code>{u[0]}</code> | Số dư: <code>{fmt_money(u[1])}đ</code>\n'
    if len(text) > 4000:
        for x in range(0, len(text), 4000):
            await update.message.reply_text(text[x:x+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

@admin_only
async def tileall_set_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/tileall [số]</code>', parse_mode=ParseMode.HTML)
    try:
        new_rate = int(ctx.args[0])
        query("UPDATE game_rates SET rate = %s", (new_rate,))
        await update.message.reply_text(f'{ce("✅")} Đã chỉnh tất cả game về tỉ lệ thắng: <code>{new_rate}%</code>', parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} Tỉ lệ phải là số nguyên.', parse_mode=ParseMode.HTML)

@admin_only
async def tile1_user_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/tile1 [ID] [Tỉ_lệ]</code>', parse_mode=ParseMode.HTML)
    try:
        uid = int(ctx.args[0])
        rate = int(ctx.args[1])
        query("UPDATE users SET rate_bonus = %s WHERE user_id = %s", (rate, uid))
        await update.message.reply_text(f'{ce("✅")} Đã áp dụng tỉ lệ thắng <code>{rate}%</code> riêng cho người dùng <code>{uid}</code>', parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} Lỗi dữ liệu nhập vào.', parse_mode=ParseMode.HTML)

@admin_only
async def tilewin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        game_id = int(ctx.args[0])
        new_rate = int(ctx.args[1])
        if not (0 <= new_rate <= 100):
            return await update.message.reply_text(f'{ce("❌")} Tỉ lệ thắng phải từ 0% đến 100%!', parse_mode=ParseMode.HTML)
        query("UPDATE game_rates SET rate=%s WHERE id=%s", (new_rate, game_id))
        res = query("SELECT name FROM game_rates WHERE id=%s", (game_id,))
        game_name = res[0][0] if res else "Không xác định"
        await update.message.reply_text(
            f'{ce("✅")} <b>CẬP NHẬT TỈ LỆ THÀNH CÔNG</b>\n\n'
            f'{ce("🎮")} Game: <code>{game_id} - {game_name}</code>\n'
            f'📈 Tỉ lệ thắng mới: <code>{new_rate}%</code>',
            parse_mode=ParseMode.HTML)
    except:
        msg = (
            f'{ce("⚡")} <b>HƯỚNG DẪN CHỈNH TỈ LỆ</b>\n'
            f'Cú pháp: <code>/tilewin [Số_ID] [Tỉ_lệ]</code>\n\n'
            f'1. TÀI XỈU 6D | 2. XÓC ĐĨA | 3. BẦU CUA | 4. TÀI XỈU ROOM'
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
async def resetsdall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query("UPDATE users SET balance = 0")
    await update.message.reply_text(f'{ce("✅")} Đã xóa toàn bộ số dư của tất cả người dùng về 0!', parse_mode=ParseMode.HTML)

@admin_only
async def xoalsall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query("DELETE FROM history")
    await update.message.reply_text(f'{ce("✅")} Đã xoá toàn bộ lịch sử cược, nạp và rút của hệ thống!', parse_mode=ParseMode.HTML)

@admin_only
async def xoals_user_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/xoals [ID]</code>', parse_mode=ParseMode.HTML)
    try:
        uid = int(ctx.args[0])
        query("DELETE FROM history WHERE user_id=%s", (uid,))
        await update.message.reply_text(f'{ce("✅")} Đã xoá sạch lịch sử của người dùng: <code>{uid}</code>', parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} ID không hợp lệ.', parse_mode=ParseMode.HTML)

@admin_only
async def set_bot_name_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/setname [Tên mới]</code>', parse_mode=ParseMode.HTML)
    new_name = " ".join(ctx.args)
    query("UPDATE settings SET value=%s WHERE key='bot_display_name'", (new_name,))
    await update.message.reply_text(f'{ce("✅")} Đã đổi tên hiển thị của Bot thành: <b>{new_name}</b>', parse_mode=ParseMode.HTML)

@admin_only
async def tao_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        reward, uses = int(ctx.args[0]), int(ctx.args[1])
        code = gen_code()
        query("INSERT INTO codes (code, reward, uses) VALUES(%s,%s,%s)", (code, reward, uses))
        await update.message.reply_text(
            f'{ce("✅")} <b>TẠO CODE THÀNH CÔNG</b>\n\n'
            f'{ce("🎁")} Code: <code>{code}</code>\n'
            f'{ce("💰")} Thưởng: <code>{fmt_money(reward)}đ</code>\n'
            f'🔄 Lượt: <code>{uses}</code>',
            parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/taocode [số tiền] [lượt dùng]</code>', parse_mode=ParseMode.HTML)

@admin_only
async def taocodeall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} <b>Cú pháp:</b> <code>/taocodeall [số_tiền] [số_lượng]</code>', parse_mode=ParseMode.HTML)
    try:
        reward = int(ctx.args[0])
        quantity = int(ctx.args[1])
        if quantity < 1 or quantity > 100:
            return await update.message.reply_text(f'{ce("❌")} Số lượng code phải từ 1 đến 100!', parse_mode=ParseMode.HTML)
        if reward < 1000:
            return await update.message.reply_text(f'{ce("❌")} Số tiền thưởng tối thiểu là 1,000đ!', parse_mode=ParseMode.HTML)
        codes = []
        for i in range(quantity):
            code = gen_code()
            query("INSERT INTO codes (code, reward, uses) VALUES(%s, %s, %s)", (code, reward, 1))
            codes.append(code)
        msg = f'{ce("🎁")} <b>TẠO {quantity} CODE THÀNH CÔNG!</b>\n━━━━━━━━━━━━━━━━━━━━━\n{ce("💰")} Mỗi code: <code>{fmt_money(reward)}đ</code>\n\n'
        for i, code in enumerate(codes, 1):
            msg += f'{i}. <code>{code}</code>\n'
        msg += f'\n{ce("📌")} Dùng lệnh <code>/code [mã]</code> để nhận thưởng!'
        if len(msg) > 4000:
            await update.message.reply_document(document=("codes.txt", "\n".join(codes)), caption=f"🎁 {quantity} code mỗi code {fmt_money(reward)}đ")
        else:
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} Số tiền hoặc số lượng không hợp lệ!', parse_mode=ParseMode.HTML)

@admin_only
async def xoacode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text(f'{ce("❌")} <b>Cú pháp:</b> <code>/xoacode [mã_code]</code>', parse_mode=ParseMode.HTML)
    code_str = ctx.args[0].strip().upper()
    data = query("SELECT reward, uses FROM codes WHERE code=%s", (code_str,))
    if not data:
        return await update.message.reply_text(f'{ce("❌")} Code <code>{code_str}</code> không tồn tại!', parse_mode=ParseMode.HTML)
    reward, uses = data[0]
    query("DELETE FROM codes WHERE code=%s", (code_str,))
    await update.message.reply_text(f'{ce("✅")} <b>ĐÃ XÓA CODE</b>\n{ce("🎁")} Mã: <code>{code_str}</code>\n{ce("💰")} Giá trị: <code>{fmt_money(reward)}đ</code>', parse_mode=ParseMode.HTML)

# ============================================================
# KM NẠP
# ============================================================
@admin_only
async def kmnap_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} <b>Cú pháp:</b> <code>/kmnap [ID] [số_tiền]</code>', parse_mode=ParseMode.HTML)
    try:
        target_id = int(ctx.args[0])
        bonus_amount = int(ctx.args[1])
        if bonus_amount <= 0:
            return await update.message.reply_text(f'{ce("❌")} Số tiền khuyến mãi phải lớn hơn 0!', parse_mode=ParseMode.HTML)
        required_bet = add_bonus_with_requirement(target_id, bonus_amount, 3)
        await update.message.reply_text(
            f'{ce("✅")} <b>KHUYẾN MÃI NẠP THÀNH CÔNG!</b>\n\n'
            f'{ce("👤")} <b>ID:</b> <code>{target_id}</code>\n'
            f'{ce("💰")} <b>Tiền thưởng:</b> <code>+{fmt_money(bonus_amount)}đ</code>\n'
            f'{ce("🎯")} <b>Yêu cầu cược:</b> <code>{fmt_money(required_bet)}đ</code>',
            parse_mode=ParseMode.HTML)
        await ctx.bot.send_message(target_id,
            f'{ce("🎁")} <b>THÔNG BÁO KHUYẾN MÃI</b>\n\n'
            f'Bạn vừa nhận được khuyến mãi nạp: <code>+{fmt_money(bonus_amount)}đ</code>\n\n'
            f'{ce("📌")} <b>Điều kiện rút tiền:</b>\n'
            f'• Cần cược <b>x3</b> vòng\n'
            f'• Số tiền cược yêu cầu: <code>{fmt_money(required_bet)}đ</code>',
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} ID hoặc số tiền không hợp lệ!', parse_mode=ParseMode.HTML)

@admin_only
async def kmnapvc_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} <b>Cú pháp:</b> <code>/kmnapvc [ID] [số_tiền]</code>', parse_mode=ParseMode.HTML)
    try:
        target_id = int(ctx.args[0])
        bet_amount = int(ctx.args[1])
        bonus_data = query("SELECT required_bet, current_bet FROM user_bonus WHERE user_id=%s", (target_id,))
        if not bonus_data or bonus_data[0][0] == 0:
            return await update.message.reply_text(f'{ce("❌")} ID <code>{target_id}</code> không có yêu cầu cược nào!', parse_mode=ParseMode.HTML)
        required_bet, current_bet = bonus_data[0]
        new_bet = current_bet + bet_amount
        query("UPDATE user_bonus SET current_bet=%s WHERE user_id=%s", (new_bet, target_id))
        remaining = required_bet - new_bet
        remaining_text = f'Còn thiếu <code>{fmt_money(remaining)}đ</code>' if remaining > 0 else f'{ce("✅")} ĐÃ HOÀN THÀNH!'
        await update.message.reply_text(
            f'{ce("✅")} <b>CẬP NHẬT CƯỢC THÀNH CÔNG!</b>\n\n'
            f'{ce("👤")} <b>ID:</b> <code>{target_id}</code>\n'
            f'➕ <b>Cược thêm:</b> <code>+{fmt_money(bet_amount)}đ</code>\n'
            f'{ce("📊")} <b>Tổng cược:</b> <code>{fmt_money(new_bet)}đ</code>\n'
            f'{ce("🎯")} <b>Yêu cầu:</b> <code>{fmt_money(required_bet)}đ</code>\n'
            f'{ce("📌")} <b>Trạng thái:</b> {remaining_text}',
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} ID hoặc số tiền không hợp lệ!', parse_mode=ParseMode.HTML)

@admin_only
async def admin_check_bet_progress_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 1:
        return await update.message.reply_text(f'{ce("❌")} <b>Cú pháp:</b> <code>/checkprogressadmin [ID]</code>', parse_mode=ParseMode.HTML)
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        return await update.message.reply_text(f'{ce("❌")} ID không hợp lệ!', parse_mode=ParseMode.HTML)
    status = get_bet_progress_status(target_id)
    if not status:
        return await update.message.reply_text(f'{ce("📊")} Người dùng <code>{target_id}</code> không có khuyến mãi nào đang hoạt động!', parse_mode=ParseMode.HTML)
    percent = status['percent']
    bar_length = 20
    filled = int(bar_length * percent / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    message = (
        f'{ce("📊")} <b>TIẾN ĐỘ CƯỢC CỦA USER</b> <code>{target_id}</code>\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("🎁")} <b>Tiền khuyến mãi:</b> <code>+{fmt_money(status["bonus_amount"])}đ</code>\n'
        f'{ce("🎯")} <b>Yêu cầu cược:</b> <code>{fmt_money(status["required_bet"])}đ</code>\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'📈 <b>Tiến độ:</b>\n<code>{bar}</code> <code>{percent:.1f}%</code>\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("✅")} <b>Đã cược:</b> <code>{fmt_money(status["current_bet"])}đ</code>\n'
        f'{ce("⚠️") if "⚠️" in CUSTOM_EMOJI else "⚠️"} <b>Còn thiếu:</b> <code>{fmt_money(status["remaining"])}đ</code>'
    )
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

# ============================================================
# BẢO TRÌ
# ============================================================
@admin_only
async def baotri_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    def st(k): return "🔴 OFF" if check_mt(k) else "🟢 ON"
    kb = [
        [InlineKeyboardButton(f"🎲 Tài Xỉu 6D: {st('mt_taixiu')}", callback_data="tg_mt_taixiu")],
        [InlineKeyboardButton(f"💿 Xóc Đĩa: {st('mt_xocdia')}", callback_data="tg_mt_xocdia")],
        [InlineKeyboardButton(f"🦀 Bầu Cua: {st('mt_baucua')}", callback_data="tg_mt_baucua")],
        [InlineKeyboardButton(f"🎲 Tài Xỉu Room: {st('mt_taixiu_room')}", callback_data="tg_mt_taixiu_room")],
        [InlineKeyboardButton(f"💳 Nạp Tiền: {st('mt_nap')}", callback_data="tg_mt_nap"),
         InlineKeyboardButton(f"🛒 Rút Tiền: {st('mt_rut')}", callback_data="tg_mt_rut")],
        [InlineKeyboardButton("❌ ĐÓNG BẢNG", callback_data="close_admin")]
    ]
    await update.message.reply_text(f'{ce("🛠")} <b>BẢNG QUẢN LÝ BẢO TRÌ</b>\n(Bấm để chuyển trạng thái On/Off)', reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

@admin_only
async def baotri_he_thong_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    maintenance_items = {
        'mt_taixiu': {'name': 'TÀI XỈU 6D', 'type': 'game', 'icon': '🎲'},
        'mt_xocdia': {'name': 'XÓC ĐĨA', 'type': 'game', 'icon': '💿'},
        'mt_baucua': {'name': 'BẦU CUA', 'type': 'game', 'icon': '🦀'},
        'mt_taixiu_room': {'name': 'TÀI XỈU ROOM', 'type': 'game', 'icon': '🎲'},
        'mt_nap': {'name': 'NẠP TIỀN', 'type': 'feature', 'icon': '💳'},
        'mt_rut': {'name': 'RÚT TIỀN', 'type': 'feature', 'icon': '🛒'},
    }
    kb = []
    kb.append([InlineKeyboardButton("━━━ 🎮 GAME 🎮 ━━━", callback_data="none")])
    game_items = [(k, v) for k, v in maintenance_items.items() if v['type'] == 'game']
    for i in range(0, len(game_items), 2):
        row = []
        for j in range(2):
            if i + j < len(game_items):
                key, item = game_items[i + j]
                status = "🔴 OFF" if check_mt(key) else "🟢 ON"
                row.append(InlineKeyboardButton(f"{item['icon']} {item['name']}: {status}", callback_data=f"mt_toggle_{key}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("━━━ ⚙️ TÍNH NĂNG ⚙️ ━━━", callback_data="none")])
    feature_items = [(k, v) for k, v in maintenance_items.items() if v['type'] == 'feature']
    for i in range(0, len(feature_items), 2):
        row = []
        for j in range(2):
            if i + j < len(feature_items):
                key, item = feature_items[i + j]
                status = "🔴 OFF" if check_mt(key) else "🟢 ON"
                row.append(InlineKeyboardButton(f"{item['icon']} {item['name']}: {status}", callback_data=f"mt_toggle_{key}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("🔴 TẮT TẤT CẢ", callback_data="mt_turnoff_all"),
               InlineKeyboardButton("🟢 BẬT TẤT CẢ", callback_data="mt_turnon_all")])
    kb.append([InlineKeyboardButton("❌ ĐÓNG BẢNG", callback_data="close_admin")])
    await update.message.reply_text(
        f'{ce("🛠")} <b>BẢNG BẢO TRÌ HỆ THỐNG</b> {ce("🛠")}\n'
        f'{ce("👉") if False else "👇"} <b>Bấm vào từng mục để bật/tắt:</b>',
        reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def handle_mt_toggle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    if uid not in ADMIN_IDS:
        await q.answer("❌ Bạn không có quyền!", show_alert=True)
        return
    data = q.data
    keys = ['mt_taixiu', 'mt_xocdia', 'mt_baucua', 'mt_taixiu_room', 'mt_nap', 'mt_rut']
    if data == "mt_turnoff_all":
        for key in keys: query("UPDATE settings SET value='1' WHERE key=%s", (key,))
        await q.answer("✅ Đã tắt BẢO TRÌ tất cả!", show_alert=True)
        await baotri_he_thong_cmd(update, ctx)
    elif data == "mt_turnon_all":
        for key in keys: query("UPDATE settings SET value='0' WHERE key=%s", (key,))
        await q.answer("✅ Đã bật HOẠT ĐỘNG tất cả!", show_alert=True)
        await baotri_he_thong_cmd(update, ctx)
    elif data.startswith("mt_toggle_"):
        key = data.replace("mt_toggle_", "")
        new_val = "1" if not check_mt(key) else "0"
        query("UPDATE settings SET value=%s WHERE key=%s", (new_val, key))
        names = {'mt_taixiu':'TÀI XỈU 6D','mt_xocdia':'XÓC ĐĨA','mt_baucua':'BẦU CUA','mt_taixiu_room':'TÀI XỈU ROOM','mt_nap':'NẠP TIỀN','mt_rut':'RÚT TIỀN'}
        status = "🔴 ĐANG BẢO TRÌ" if new_val == "1" else "🟢 HOẠT ĐỘNG"
        await q.answer(f"{names.get(key, key)}: {status}", show_alert=True)
        await baotri_he_thong_cmd(update, ctx)

@admin_only
async def baotri_id_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 1:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/baotriid [ID]</code>', parse_mode=ParseMode.HTML)
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        return await update.message.reply_text(f'{ce("❌")} ID không hợp lệ!', parse_mode=ParseMode.HTML)
    user_check = query("SELECT 1 FROM users WHERE user_id=%s", (target_id,))
    if not user_check:
        return await update.message.reply_text(f'{ce("❌")} Không tìm thấy ID <code>{target_id}</code>!', parse_mode=ParseMode.HTML)
    items = {
        1: {'name':'TÀI XỈU 6D','type':'game','icon':'🎲'},
        2: {'name':'XÓC ĐĨA','type':'game','icon':'💿'},
        3: {'name':'BẦU CUA','type':'game','icon':'🦀'},
        4: {'name':'TÀI XỈU ROOM','type':'game','icon':'🎲'},
        'nap': {'name':'NẠP TIỀN','type':'feature','icon':'💳'},
        'rut': {'name':'RÚT TIỀN','type':'feature','icon':'🛒'},
    }
    kb = []
    kb.append([InlineKeyboardButton("━━━ 🎮 GAME 🎮 ━━━", callback_data="none")])
    game_items = [(k, v) for k, v in items.items() if v['type'] == 'game']
    for i in range(0, len(game_items), 2):
        row = []
        for j in range(2):
            if i + j < len(game_items):
                gid, item = game_items[i + j]
                is_banned_item = is_game_banned(target_id, gid)
                status = "🔴 CẤM" if is_banned_item else "🟢 MỞ"
                row.append(InlineKeyboardButton(f"{item['icon']} {item['name']}: {status}", callback_data=f"user_toggle_game_{target_id}_{gid}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("━━━ ⚙️ TÍNH NĂNG ⚙️ ━━━", callback_data="none")])
    feature_items = [(k, v) for k, v in items.items() if v['type'] == 'feature']
    for i in range(0, len(feature_items), 2):
        row = []
        for j in range(2):
            if i + j < len(feature_items):
                fkey, item = feature_items[i + j]
                is_banned_item = is_feature_banned(target_id, fkey)
                status = "🔴 CẤM" if is_banned_item else "🟢 MỞ"
                row.append(InlineKeyboardButton(f"{item['icon']} {item['name']}: {status}", callback_data=f"user_toggle_feature_{target_id}_{fkey}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("🔴 CẤM TẤT CẢ", callback_data=f"user_turnoff_all_{target_id}"),
               InlineKeyboardButton("🟢 MỞ TẤT CẢ", callback_data=f"user_turnon_all_{target_id}")])
    kb.append([InlineKeyboardButton("🚫 CẤM TOÀN BỘ USER", callback_data=f"user_ban_full_{target_id}"),
               InlineKeyboardButton("✅ MỞ TOÀN BỘ USER", callback_data=f"user_unban_full_{target_id}")])
    kb.append([InlineKeyboardButton("❌ ĐÓNG BẢNG", callback_data="close_admin")])
    user_info = query("SELECT balance, total_bet FROM users WHERE user_id=%s", (target_id,))
    balance = user_info[0][0] if user_info else 0
    total_bet = user_info[0][1] if user_info else 0
    await update.message.reply_text(
        f'{ce("🛠")} <b>BẢNG BẢO TRÌ NGƯỜI DÙNG</b> {ce("🛠")}\n'
        f'{ce("👤")} <b>ID:</b> <code>{target_id}</code>\n'
        f'{ce("💰")} <b>Số dư:</b> <code>{fmt_money(balance)}đ</code>\n'
        f'{ce("📊")} <b>Tổng cược:</b> <code>{fmt_money(total_bet)}đ</code>\n'
        f'{ce("👉") if False else "👇"} <b>Bấm để bật/tắt cấm:</b>',
        reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def handle_user_maintenance_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    if uid not in ADMIN_IDS:
        await q.answer("❌ Bạn không có quyền!", show_alert=True)
        return
    data = q.data
    if data.startswith("user_toggle_game_"):
        parts = data.split("_")
        target_id = int(parts[3]); game_id = int(parts[4])
        if is_game_banned(target_id, game_id):
            query("DELETE FROM banned_games WHERE user_id=%s AND game_id=%s", (target_id, game_id))
            await q.answer(f"✅ Đã MỞ game ID {game_id}", show_alert=True)
        else:
            query("INSERT INTO banned_games VALUES(%s, %s) ON CONFLICT DO NOTHING", (target_id, game_id))
            await q.answer(f"🔴 Đã CẤM game ID {game_id}", show_alert=True)
        fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
        await baotri_id_cmd(update, fake_ctx)
    elif data.startswith("user_toggle_feature_"):
        parts = data.split("_")
        target_id = int(parts[3]); feature = parts[4]
        if is_feature_banned(target_id, feature):
            query("DELETE FROM banned_features WHERE user_id=%s AND feature=%s", (target_id, feature))
            await q.answer(f"✅ Đã MỞ tính năng {feature}", show_alert=True)
        else:
            query("INSERT INTO banned_features VALUES(%s, %s) ON CONFLICT DO NOTHING", (target_id, feature))
            await q.answer(f"🔴 Đã CẤM tính năng {feature}", show_alert=True)
        fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
        await baotri_id_cmd(update, fake_ctx)
    elif data.startswith("user_turnoff_all_"):
        target_id = int(data.split("_")[3])
        for game_id in [1, 2, 3, 4]:
            query("INSERT INTO banned_games VALUES(%s, %s) ON CONFLICT DO NOTHING", (target_id, game_id))
        for feature in ['nap', 'rut']:
            query("INSERT INTO banned_features VALUES(%s, %s) ON CONFLICT DO NOTHING", (target_id, feature))
        await q.answer(f"🔴 Đã CẤM TẤT CẢ!", show_alert=True)
        fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
        await baotri_id_cmd(update, fake_ctx)
    elif data.startswith("user_turnon_all_"):
        target_id = int(data.split("_")[3])
        query("DELETE FROM banned_games WHERE user_id=%s", (target_id,))
        query("DELETE FROM banned_features WHERE user_id=%s", (target_id,))
        await q.answer(f"🟢 Đã MỞ TẤT CẢ!", show_alert=True)
        fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
        await baotri_id_cmd(update, fake_ctx)
    elif data.startswith("user_ban_full_"):
        target_id = int(data.split("_")[3])
        query("INSERT INTO banned VALUES(%s) ON CONFLICT (user_id) DO NOTHING", (target_id,))
        await q.answer(f"🚫 Đã CẤM TOÀN BỘ!", show_alert=True)
        fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
        await baotri_id_cmd(update, fake_ctx)
    elif data.startswith("user_unban_full_"):
        target_id = int(data.split("_")[3])
        query("DELETE FROM banned WHERE user_id=%s", (target_id,))
        await q.answer(f"✅ Đã MỞ TOÀN BỘ!", show_alert=True)
        fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
        await baotri_id_cmd(update, fake_ctx)

@admin_only
async def cam_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/cam [id] [game_id/nap/rut]</code>', parse_mode=ParseMode.HTML)
    uid, target = int(ctx.args[0]), ctx.args[1]
    if target.isdigit():
        query("INSERT INTO banned_games VALUES(%s, %s) ON CONFLICT DO NOTHING", (uid, int(target)))
        await update.message.reply_text(f'{ce("🚫")} Đã cấm ID <code>{uid}</code> chơi game ID <code>{target}</code>', parse_mode=ParseMode.HTML)
    elif target in ['nap', 'rut']:
        query("INSERT INTO banned_features VALUES(%s, %s) ON CONFLICT DO NOTHING", (uid, target))
        await update.message.reply_text(f'{ce("🚫")} Đã cấm ID <code>{uid}</code> sử dụng tính năng <code>{target}</code>', parse_mode=ParseMode.HTML)

@admin_only
async def bocam_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/bocam [id] [game_id/nap/rut]</code>', parse_mode=ParseMode.HTML)
    uid, target = int(ctx.args[0]), ctx.args[1]
    if target.isdigit():
        query("DELETE FROM banned_games WHERE user_id=%s AND game_id=%s", (uid, int(target)))
        await update.message.reply_text(f'{ce("✅")} Đã gỡ cấm game ID <code>{target}</code> cho ID <code>{uid}</code>', parse_mode=ParseMode.HTML)
    elif target in ['nap', 'rut']:
        query("DELETE FROM banned_features WHERE user_id=%s AND feature=%s", (uid, target))
        await update.message.reply_text(f'{ce("✅")} Đã gỡ cấm tính năng <code>{target}</code> cho ID <code>{uid}</code>', parse_mode=ParseMode.HTML)

@admin_only
async def daban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    banned_users = query("SELECT user_id FROM banned")
    banned_games = query("SELECT bg.user_id, u.balance, gr.name as game_name, bg.game_id FROM banned_games bg LEFT JOIN game_rates gr ON bg.game_id = gr.id LEFT JOIN users u ON bg.user_id = u.user_id ORDER BY bg.user_id")
    banned_features = query("SELECT user_id, feature FROM banned_features ORDER BY user_id")
    banned_admins = query("SELECT admin_id, reason, banned_at FROM banned_admins ORDER BY banned_at DESC")
    msg = f'{ce("🚫")} <b>DANH SÁCH BỊ CẤM</b> {ce("🚫")}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{ce("👤")} <b>CẤM TOÀN BỘ:</b>\n'
    if banned_users:
        for uid in banned_users[:20]:
            user_info = query("SELECT balance FROM users WHERE user_id=%s", (uid[0],))
            balance = user_info[0][0] if user_info else 0
            msg += f'  🔴 ID <code>{uid[0]}</code> | Số dư: <code>{fmt_money(balance)}đ</code>\n'
    else:
        msg += f'  {ce("✅")} Không có\n'
    msg += f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{ce("🎮")} <b>CẤM GAME:</b>\n'
    if banned_games:
        for uid, balance, game_name, gid in banned_games[:30]:
            msg += f'  {ce("👤")} <code>{uid}</code> | Game: <code>{gid}</code> - {game_name}\n'
    else:
        msg += f'  {ce("✅")} Không có\n'
    msg += f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{ce("⚙️")} <b>CẤM TÍNH NĂNG:</b>\n'
    if banned_features:
        for uid, feature in banned_features[:30]:
            feature_name = "NẠP TIỀN" if feature == "nap" else "RÚT TIỀN"
            msg += f'  {ce("👤")} <code>{uid}</code> | {feature_name}\n'
    else:
        msg += f'  {ce("✅")} Không có\n'
    msg += f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{ce("👑")} <b>ADMIN BỊ CẤM:</b>\n'
    if banned_admins:
        for aid, reason, banned_at in banned_admins:
            msg += f'  🔴 <code>{aid}</code> | {reason} | {banned_at}\n'
    else:
        msg += f'  {ce("✅")} Không có\n'
    if len(msg) > 4000:
        for x in range(0, len(msg), 4000):
            await update.message.reply_text(msg[x:x+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
async def mofull_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ XÁC NHẬN", callback_data="confirm_mofull"),
        InlineKeyboardButton("❌ HỦY", callback_data="close_admin")
    ]])
    await update.message.reply_text(
        f'{ce("⚠️") if "⚠️" in CUSTOM_EMOJI else "⚠️"} <b>MỞ TẤT CẢ NGƯỜI BỊ CẤM</b>\n\nBạn có chắc chắn?',
        reply_markup=kb, parse_mode=ParseMode.HTML)

async def tatroom_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("❌")} Bạn không có quyền!', parse_mode=ParseMode.HTML)
        return
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private":
        await update.message.reply_text(f'{ce("❌")} Lệnh này chỉ dùng trong NHÓM!', parse_mode=ParseMode.HTML)
        return
    if len(ctx.args) < 1:
        current_status = f'{ce("🔒")} ĐÃ TẮT' if not room_betting_enabled.get(chat_id, True) else f'{ce("🔓")} ĐANG BẬT'
        await update.message.reply_text(
            f'{ce("🎮")} <b>TRẠNG THÁI CƯỢC</b>\n{ce("📊")} Hiện tại: {current_status}\n\n'
            f'{ce("✍️")} Cú pháp:\n• Tắt: <code>/tatroom off</code>\n• Bật: <code>/tatroom on</code>',
            parse_mode=ParseMode.HTML)
        return
    action = ctx.args[0].lower()
    if action == "off":
        room_betting_enabled[chat_id] = False
        await update.message.reply_text(f'{ce("🔒")} <b>ĐÃ TẮT CƯỢC TRONG NHÓM!</b>', parse_mode=ParseMode.HTML)
    elif action == "on":
        room_betting_enabled[chat_id] = True
        await update.message.reply_text(f'{ce("🔓")} <b>ĐÃ BẬT CƯỢC TRONG NHÓM!</b>', parse_mode=ParseMode.HTML)

async def baotri_hethong_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("❌")} Bạn không có quyền!', parse_mode=ParseMode.HTML)
        return
    if len(ctx.args) < 1:
        current_status = f'{ce("🔒")} ĐANG BẢO TRÌ' if is_system_maintenance() else f'{ce("🔓")} HOẠT ĐỘNG'
        await update.message.reply_text(
            f'{ce("🛠")} <b>TRẠNG THÁI</b>\n{ce("📊")} {current_status}\n\n'
            f'{ce("✍️")} <code>/baotriall on</code> hoặc <code>/baotriall off</code>',
            parse_mode=ParseMode.HTML)
        return
    action = ctx.args[0].lower()
    if action == "on":
        query("UPDATE settings SET value='1' WHERE key='system_maintenance'")
        await update.message.reply_text(f'{ce("🔒")} <b>ĐÃ BẬT BẢO TRÌ TOÀN HỆ THỐNG</b>', parse_mode=ParseMode.HTML)
    elif action == "off":
        query("UPDATE settings SET value='0' WHERE key='system_maintenance'")
        await update.message.reply_text(f'{ce("✅")} <b>ĐÃ TẮT BẢO TRÌ</b>', parse_mode=ParseMode.HTML)

async def baotri_tong_cong_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != 8619503816:
        await update.message.reply_text(f'{ce("❌")} Chỉ Admin chính mới dùng được!', parse_mode=ParseMode.HTML)
        return
    if len(ctx.args) < 1:
        current_status = f'{ce("🔒")} ĐANG BẢO TRÌ TOÀN BỘ' if is_total_maintenance() else f'{ce("🔓")} HOẠT ĐỘNG'
        await update.message.reply_text(
            f'{ce("🛠")} <b>BẢO TRÌ TOÀN BỘ</b>\n{ce("📊")} {current_status}\n\n'
            f'<code>/baotritc on</code> hoặc <code>/baotritc off</code>',
            parse_mode=ParseMode.HTML)
        return
    action = ctx.args[0].lower()
    if action == "on":
        query("UPDATE settings SET value='1' WHERE key='mt_tongbao'")
        await update.message.reply_text(f'{ce("🔒")} <b>ĐÃ BẬT BẢO TRÌ TOÀN BỘ</b>', parse_mode=ParseMode.HTML)
    elif action == "off":
        query("UPDATE settings SET value='0' WHERE key='mt_tongbao'")
        await update.message.reply_text(f'{ce("✅")} <b>ĐÃ TẮT BẢO TRÌ TOÀN BỘ</b>', parse_mode=ParseMode.HTML)

# ============================================================
# QUẢN LÝ ADMIN
# ============================================================
async def cam_admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != 8619503816:
        await update.message.reply_text(f'{ce("❌")} Chỉ Admin chính!', parse_mode=ParseMode.HTML)
        return
    if len(ctx.args) < 1:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/camadmin [ID] [lý do]</code>', parse_mode=ParseMode.HTML)
    try:
        target_admin = int(ctx.args[0])
        reason = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else "Không có lý do"
        if target_admin == user_id:
            return await update.message.reply_text(f'{ce("❌")} Không thể tự cấm chính mình!', parse_mode=ParseMode.HTML)
        if target_admin not in ADMIN_IDS:
            return await update.message.reply_text(f'{ce("❌")} ID <code>{target_admin}</code> không phải Admin!', parse_mode=ParseMode.HTML)
        now_str = get_vietnam_datetime_db()
        query("INSERT INTO banned_admins VALUES(%s, %s, %s, %s) ON CONFLICT (admin_id) DO UPDATE SET banned_by=%s, reason=%s, banned_at=%s",
              (target_admin, user_id, reason, now_str, user_id, reason, now_str))
        await update.message.reply_text(
            f'{ce("✅")} Đã cấm Admin <code>{target_admin}</code>\n{ce("✍️")} Lý do: {reason}',
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} ID không hợp lệ!', parse_mode=ParseMode.HTML)

async def unban_admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != 8619503816:
        return await update.message.reply_text(f'{ce("❌")} Chỉ Admin chính!', parse_mode=ParseMode.HTML)
    if len(ctx.args) < 1:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/unbanadmin [ID]</code>', parse_mode=ParseMode.HTML)
    try:
        target_admin = int(ctx.args[0])
        if not is_admin_banned(target_admin):
            return await update.message.reply_text(f'{ce("❌")} Admin <code>{target_admin}</code> không bị cấm!', parse_mode=ParseMode.HTML)
        query("DELETE FROM banned_admins WHERE admin_id=%s", (target_admin,))
        await update.message.reply_text(f'{ce("✅")} Đã gỡ cấm cho Admin <code>{target_admin}</code>', parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} ID không hợp lệ!', parse_mode=ParseMode.HTML)

async def list_banned_admins_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("❌")} Bạn không có quyền!', parse_mode=ParseMode.HTML)
    banned_list = query("SELECT admin_id, banned_by, reason, banned_at FROM banned_admins")
    if not banned_list:
        return await update.message.reply_text(f'{ce("📌")} Không có Admin nào bị cấm.', parse_mode=ParseMode.HTML)
    msg = f'{ce("🚫")} <b>DANH SÁCH ADMIN BỊ CẤM</b>\n━━━━━━━━━━━━━━━━━━━━━\n'
    for admin_id, banned_by, reason, banned_at in banned_list:
        msg += f'\n{ce("👤")} ID: <code>{admin_id}</code>\n{ce("👑")} Bởi: <code>{banned_by}</code>\n{ce("✍️")} Lý do: {reason}\n{ce("⏰")} Lúc: {banned_at}\n━━━━━━━━━━━━━━━━━━━━━\n'
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def camadmin1_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != 8619503816:
        return await update.message.reply_text(f'{ce("❌")} Chỉ Admin chính!', parse_mode=ParseMode.HTML)
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/camadmin1 [ID] [tên_lệnh]</code>', parse_mode=ParseMode.HTML)
    try:
        target_admin = int(ctx.args[0])
        banned_command = ctx.args[1].lower()
        if target_admin not in ADMIN_IDS:
            return await update.message.reply_text(f'{ce("❌")} ID <code>{target_admin}</code> không phải Admin!', parse_mode=ParseMode.HTML)
        now_str = get_vietnam_datetime_db()
        query("INSERT INTO banned_admin_commands VALUES(%s, %s, %s, %s, %s) ON CONFLICT (admin_id, command) DO NOTHING",
              (target_admin, banned_command, user_id, "Không có lý do", now_str))
        await update.message.reply_text(f'{ce("✅")} Đã cấm lệnh <code>/{banned_command}</code> cho Admin <code>{target_admin}</code>', parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} ID không hợp lệ!', parse_mode=ParseMode.HTML)

async def uncamadmin1_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != 8619503816:
        return await update.message.reply_text(f'{ce("❌")} Chỉ Admin chính!', parse_mode=ParseMode.HTML)
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/uncamadmin1 [ID] [tên_lệnh]</code>', parse_mode=ParseMode.HTML)
    try:
        target_admin = int(ctx.args[0])
        banned_command = ctx.args[1].lower()
        query("DELETE FROM banned_admin_commands WHERE admin_id=%s AND command=%s", (target_admin, banned_command))
        await update.message.reply_text(f'{ce("✅")} Đã gỡ cấm lệnh <code>/{banned_command}</code> cho Admin <code>{target_admin}</code>', parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} ID không hợp lệ!', parse_mode=ParseMode.HTML)

async def quanlyadmin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("❌")} Bạn không có quyền!', parse_mode=ParseMode.HTML)
    all_admins = ADMIN_IDS.copy()
    banned_admins = query("SELECT admin_id FROM banned_admins")
    banned_ids = [b[0] for b in banned_admins] if banned_admins else []
    kb = []
    kb.append([InlineKeyboardButton("👤 DANH SÁCH ADMIN", callback_data="admin_list_header")])
    for admin_id in all_admins:
        status = "🚫" if admin_id in banned_ids else "✅"
        btn_text = f"{status} ADMIN {admin_id}"
        if admin_id == 8619503816:
            btn_text = f"👑 {btn_text}"
        kb.append([InlineKeyboardButton(btn_text, callback_data=f"admin_detail_{admin_id}")])
    kb.append([InlineKeyboardButton("❌ ĐÓNG", callback_data="close_admin")])
    await update.message.reply_text(f'{ce("👑")} <b>BẢNG QUẢN LÝ ADMIN</b>\n{ce("👉") if False else "👇"} Bấm vào Admin để quản lý:', reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

# ============================================================
# LỊCH SỬ NẠP RÚT
# ============================================================
async def lsnap_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("❌")} Không có quyền!', parse_mode=ParseMode.HTML)
    if len(ctx.args) < 1:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/lsnap [ID]</code>', parse_mode=ParseMode.HTML)
    try:
        target_id = int(ctx.args[0])
        data = query("SELECT amount, admin_id, time FROM deposit_history WHERE user_id=%s AND status='success' ORDER BY time DESC LIMIT 20", (target_id,))
        if not data:
            return await update.message.reply_text(f'{ce("📌")} ID <code>{target_id}</code> chưa có lịch sử nạp!', parse_mode=ParseMode.HTML)
        msg = f'{ce("📥")} <b>LỊCH SỬ NẠP CỦA ID</b> <code>{target_id}</code>\n━━━━━━━━━━━━━━━━━━━━━\n'
        for row in data:
            msg += f'{ce("✅")} <code>+{fmt_money(row[0])}đ</code> | Admin: <code>{row[1]}</code>\n   {ce("⏰")} <i>{row[2]}</i>\n━━━━━━━━━━━━━━━━━━━━━\n'
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} ID không hợp lệ!', parse_mode=ParseMode.HTML)

async def lsrut_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("❌")} Không có quyền!', parse_mode=ParseMode.HTML)
    if len(ctx.args) < 1:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/lsrut [ID]</code>', parse_mode=ParseMode.HTML)
    try:
        target_id = int(ctx.args[0])
        data = query("SELECT amount, status, admin_id, time FROM withdraw_history WHERE user_id=%s ORDER BY time DESC LIMIT 20", (target_id,))
        if not data:
            return await update.message.reply_text(f'{ce("📌")} ID <code>{target_id}</code> chưa có lịch sử rút!', parse_mode=ParseMode.HTML)
        msg = f'{ce("📤")} <b>LỊCH SỬ RÚT CỦA ID</b> <code>{target_id}</code>\n━━━━━━━━━━━━━━━━━━━━━\n'
        for row in data:
            status_icon = "✅" if row[1] == "success" else "❌" if row[1] == "rejected" else "⏳"
            status_text = "Thành công" if row[1] == "success" else "Bị từ chối" if row[1] == "rejected" else "Chờ duyệt"
            msg += f'{status_icon} <code>{fmt_money(row[0])}đ</code> | {status_text}\n'
            if row[2]: msg += f'   {ce("👑")} Admin: <code>{row[2]}</code>\n'
            msg += f'   {ce("⏰")} <i>{row[3]}</i>\n━━━━━━━━━━━━━━━━━━━━━\n'
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} ID không hợp lệ!', parse_mode=ParseMode.HTML)

@admin_only
async def lsnapall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    limit = 20
    if ctx.args and ctx.args[0].isdigit(): limit = min(int(ctx.args[0]), 100)
    data = query("SELECT id, user_id, amount, admin_id, time FROM deposit_history WHERE status='success' ORDER BY time DESC LIMIT %s", (limit,))
    if not data:
        return await update.message.reply_text(f'{ce("📌")} Chưa có lịch sử nạp!', parse_mode=ParseMode.HTML)
    total_amount = query("SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE status='success'")[0][0] or 0
    msg = f'{ce("📥")} <b>TẤT CẢ LỊCH SỬ NẠP</b>\n{ce("💰")} Tổng: <code>{fmt_money(total_amount)}đ</code>\n━━━━━━━━━━━━━━━━━━━━━\n\n'
    for row in data:
        msg += f'{ce("🆔")} #{row[0]} | {ce("👤")} <code>{row[1]}</code> | {ce("✅")} <code>+{fmt_money(row[2])}đ</code> | {ce("👑")} <code>{row[3]}</code>\n   {ce("⏰")} <i>{row[4]}</i>\n━━━━━━━━━━━━━━━━━━━━━\n'
    if len(msg) > 4000:
        for x in range(0, len(msg), 4000):
            await update.message.reply_text(msg[x:x+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
async def lsrutall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    limit = 20
    if ctx.args and ctx.args[0].isdigit(): limit = min(int(ctx.args[0]), 100)
    data = query("SELECT id, user_id, amount, status, admin_id, time, admin_note FROM withdraw_history ORDER BY time DESC LIMIT %s", (limit,))
    if not data:
        return await update.message.reply_text(f'{ce("📌")} Chưa có lịch sử rút!', parse_mode=ParseMode.HTML)
    total_success = query("SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE status='success'")[0][0] or 0
    total_pending = query("SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE status='pending'")[0][0] or 0
    msg = f'{ce("📤")} <b>TẤT CẢ LỊCH SỬ RÚT</b>\n{ce("✅")} Thành công: <code>{fmt_money(total_success)}đ</code>\n{ce("⌛")} Chờ: <code>{fmt_money(total_pending)}đ</code>\n━━━━━━━━━━━━━━━━━━━━━\n\n'
    for row in data:
        status_icon = "✅" if row[3] == "success" else "❌" if row[3] == "rejected" else "⏳"
        msg += f'{ce("🆔")} #{row[0]} | {ce("👤")} <code>{row[1]}</code> | {status_icon} <code>{fmt_money(row[2])}đ</code>\n   {ce("⏰")} <i>{row[5]}</i>\n━━━━━━━━━━━━━━━━━━━━━\n'
    if len(msg) > 4000:
        for x in range(0, len(msg), 4000):
            await update.message.reply_text(msg[x:x+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
async def thongke_nap_rut_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    filter_type = "today"
    if ctx.args: filter_type = ctx.args[0].lower()
    now = get_vietnam_time()
    today_str = now.strftime("%d/%m/%Y")
    this_month_str = now.strftime("/%m/%Y")
    this_year_str = now.strftime("/%Y")
    if filter_type in ["today", "ngay"]:
        nap_data = query("SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE status='success' AND time LIKE %s", (f"%{today_str}%",))
        rut_data = query("SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE status='success' AND time LIKE %s", (f"%{today_str}%",))
        title = f'📅 HÔM NAY ({today_str})'
    elif filter_type in ["month", "tháng"]:
        nap_data = query("SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE status='success' AND time LIKE %s", (f"%{this_month_str}%",))
        rut_data = query("SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE status='success' AND time LIKE %s", (f"%{this_month_str}%",))
        title = f'📅 THÁNG {now.month}/{now.year}'
    elif filter_type in ["year", "năm"]:
        nap_data = query("SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE status='success' AND time LIKE %s", (f"%{this_year_str}%",))
        rut_data = query("SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE status='success' AND time LIKE %s", (f"%{this_year_str}%",))
        title = f'📅 NĂM {now.year}'
    else:
        nap_data = query("SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE status='success'")
        rut_data = query("SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE status='success'")
        title = "📊 TOÀN THỜI GIAN"
    total_nap = nap_data[0][0] if nap_data else 0
    total_rut = rut_data[0][0] if rut_data else 0
    loi_nhuan = total_nap - total_rut
    msg = (
        f'{ce("💰")} <b>THỐNG KÊ NẠP - RÚT</b>\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'📌 <b>{title}</b>\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("📥")} <b>TỔNG NẠP:</b> <code>{fmt_money(total_nap)}đ</code>\n'
        f'{ce("📤")} <b>TỔNG RÚT:</b> <code>{fmt_money(total_rut)}đ</code>\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'{"📈" if loi_nhuan >= 0 else "📉"} <b>LỢI NHUẬN:</b> <code>{fmt_money(loi_nhuan)}đ</code>\n'
        f'━━━━━━━━━━━━━━━━━━━━━'
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# ============================================================
# BANK / XUẤT DB / MISC
# ============================================================
@admin_only
async def reset_bank(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(ctx.args[0])
        query("UPDATE users SET bank=NULL, stk=NULL, name=NULL, bank_linked=0 WHERE user_id=%s", (target_id,))
        await update.message.reply_text(f'{ce("✅")} Đã reset bank cho ID <code>{target_id}</code>.', parse_mode=ParseMode.HTML)
        await ctx.bot.send_message(chat_id=target_id,
            text=f'{ce("🔔")} Admin đã reset thông tin ngân hàng của bạn.',
            parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/resetbank [ID]</code>', parse_mode=ParseMode.HTML)

@admin_only
async def check_bank_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    users = query("SELECT user_id, bank, stk, name FROM users WHERE bank_linked=0 OR bank_linked IS NULL")
    if not users:
        return await update.message.reply_text(f'{ce("✅")} Tất cả người dùng đã liên kết ngân hàng!', parse_mode=ParseMode.HTML)
    msg = f'{ce("💳")} <b>DANH SÁCH CHƯA LIÊN KẾT</b> {ce("💳")}\n━━━━━━━━━━━━━━━━━━━━━\n'
    for uid, bank, stk, name in users:
        msg += f'{ce("👤")} <code>{uid}</code>\n'
        if bank:
            msg += f'   {ce("✍️")} Đã nhập: {bank} - {stk} - {name}\n'
        else:
            msg += f'   {ce("❌")} Chưa nhập thông tin\n'
        msg += '━━━━━━━━━━━━━━━━━━━━━\n'
    if len(msg) > 4000:
        for x in range(0, len(msg), 4000):
            await update.message.reply_text(msg[x:x+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
async def export_db_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    users = query("SELECT user_id, balance, total_bet, refs FROM users ORDER BY balance DESC")
    if not users:
        return await update.message.reply_text(f'{ce("❌")} Không có dữ liệu!', parse_mode=ParseMode.HTML)
    output = BytesIO()
    output.write(u'\ufeff'.encode('utf-8'))
    writer = csv.writer(output, delimiter=',')
    writer.writerow(['User ID', 'Số dư', 'Tổng cược', 'Số người mời'])
    for user in users:
        writer.writerow([user[0], f"{user[1]:,}", f"{user[2]:,}", user[3]])
    output.seek(0)
    await update.message.reply_document(document=output, filename=f"users_export_{get_vietnam_time().strftime('%Y%m%d_%H%M%S')}.csv")

@admin_only
async def reset_all_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ XÁC NHẬN XÓA TẤT CẢ", callback_data="confirm_reset_all_final")
    ], [InlineKeyboardButton("❌ HỦY", callback_data="close_admin")]])
    await update.message.reply_text(
        f'{ce("⚠️") if "⚠️" in CUSTOM_EMOJI else "⚠️"} <b>CẢNH BÁO NGUY HIỂM</b> {ce("⚠️") if "⚠️" in CUSTOM_EMOJI else "⚠️"}\n\n'
        f'Thao tác này sẽ xóa sạch dữ liệu: Users, History, Codes, Banned.\n\n'
        f'Bạn có chắc chắn?',
        reply_markup=kb, parse_mode=ParseMode.HTML)

@admin_only
async def gift_all_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 1:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/giftall [số_tiền] [lý_do]</code>', parse_mode=ParseMode.HTML)
    try:
        amount = int(ctx.args[0])
        reason = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else "Quà tặng từ Admin"
        if amount < 1000:
            return await update.message.reply_text(f'{ce("❌")} Số tiền tối thiểu 1,000đ!', parse_mode=ParseMode.HTML)
        users = query("SELECT user_id FROM users")
        total_users = len(users) if users else 0
        if total_users == 0:
            return await update.message.reply_text(f'{ce("❌")} Không có người dùng!', parse_mode=ParseMode.HTML)
        confirm_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ XÁC NHẬN", callback_data=f"confirm_giftall_{amount}_{reason}_{total_users}"),
            InlineKeyboardButton("❌ HỦY", callback_data="close_admin")
        ]])
        await update.message.reply_text(
            f'{ce("🎁")} <b>XÁC NHẬN TẶNG QUÀ</b>\n'
            f'{ce("💰")} <code>{fmt_money(amount)}đ/người</code>\n'
            f'{ce("👤")} <code>{total_users}</code> người\n'
            f'{ce("💵")} Tổng: <code>{fmt_money(amount * total_users)}đ</code>\n'
            f'{ce("✍️")} {reason}',
            reply_markup=confirm_kb, parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} Số tiền không hợp lệ!', parse_mode=ParseMode.HTML)

@admin_only
async def top_thang_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = query("SELECT user_id, SUM(amount) as total_win FROM history WHERE amount > 0 AND note NOT ILIKE '%nạp%' AND note NOT ILIKE '%Code%' GROUP BY user_id ORDER BY total_win DESC LIMIT 10")
    if not data:
        return await update.message.reply_text(f'{ce("📊")} Chưa có dữ liệu!', parse_mode=ParseMode.HTML)
    msg = f'{ce("🏆")} <b>TOP 10 NGƯỜI THẮNG</b> {ce("🏆")}\n━━━━━━━━━━━━━━━━━━━━━\n'
    for i, (uid, total) in enumerate(data, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        msg += f'{medal} <code>{uid}</code> — <code>+{fmt_money(total)}đ</code>\n'
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
async def chinhkq_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rates = query("SELECT id, name, rate FROM game_rates ORDER BY id ASC")
    kb = []
    for game_id, name, rate in rates:
        kb.append([InlineKeyboardButton(f"🎮 {name} | {rate}%", callback_data=f"rate_show_{game_id}")])
        kb.append([
            InlineKeyboardButton(f"🔻 -10%", callback_data=f"rate_dec_{game_id}"),
            InlineKeyboardButton(f"🔺 +10%", callback_data=f"rate_inc_{game_id}")
        ])
    kb.append([InlineKeyboardButton("❌ ĐÓNG", callback_data="close_admin")])
    msg = f'{ce("📊")} <b>BẢNG CHỈNH TỈ LỆ THẮNG GAME</b> {ce("📊")}\n━━━━━━━━━━━━━━━━━━━━━\n'
    for game_id, name, rate in rates:
        msg += f'{ce("🆔")} <code>{game_id}</code> | {name}: <b>{rate}%</b>\n'
    msg += f'\n{ce("👉") if False else "👇"} <b>Bấm +10% hoặc -10% để điều chỉnh</b>'
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def handle_rate_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    if uid not in ADMIN_IDS:
        return await q.answer("❌ Không có quyền!", show_alert=True)
    data = q.data
    if data.startswith("rate_show_"):
        game_id = int(data.split("_")[2])
        rate_info = query("SELECT id, name, rate FROM game_rates WHERE id=%s", (game_id,))
        if rate_info:
            gid, name, rate = rate_info[0]
            await q.answer(f"🎮 {name}\n📊 Tỉ lệ: {rate}%", show_alert=True)
    elif data.startswith("rate_inc_"):
        game_id = int(data.split("_")[2])
        current = query("SELECT rate FROM game_rates WHERE id=%s", (game_id,))
        if current:
            new_rate = min(100, current[0][0] + 10)
            query("UPDATE game_rates SET rate=%s WHERE id=%s", (new_rate, game_id))
            await q.answer(f"✅ Tăng lên {new_rate}%", show_alert=True)
            await chinhkq_cmd(update, ctx)
    elif data.startswith("rate_dec_"):
        game_id = int(data.split("_")[2])
        current = query("SELECT rate FROM game_rates WHERE id=%s", (game_id,))
        if current:
            new_rate = max(0, current[0][0] - 10)
            query("UPDATE game_rates SET rate=%s WHERE id=%s", (new_rate, game_id))
            await q.answer(f"✅ Giảm xuống {new_rate}%", show_alert=True)
            await chinhkq_cmd(update, ctx)

@admin_only
async def tile1all_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/tile1all [id] [tỉ_lệ]</code>', parse_mode=ParseMode.HTML)
    try:
        target_id = int(ctx.args[0])
        rate = int(ctx.args[1])
        if rate < 0 or rate > 100:
            return await update.message.reply_text(f'{ce("❌")} Tỉ lệ 0-100%!', parse_mode=ParseMode.HTML)
        query("UPDATE users SET rate_bonus = %s WHERE user_id = %s", (rate, target_id))
        await update.message.reply_text(f'{ce("✅")} ID <code>{target_id}</code> | Tỉ lệ: <code>{rate}%</code>', parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} ID hoặc tỉ lệ không hợp lệ!', parse_mode=ParseMode.HTML)

@admin_only
async def check_top_interaction(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id if update.effective_chat.type != "private" else None
    if not gid:
        return await update.message.reply_text(f'{ce("❌")} Chỉ dùng trong nhóm!', parse_mode=ParseMode.HTML)
    top = query("SELECT user_id, interaction_count, last_interaction FROM group_interactions WHERE group_id=%s ORDER BY interaction_count DESC LIMIT 10", (gid,))
    if not top:
        return await update.message.reply_text(f'{ce("📊")} Chưa có dữ liệu!', parse_mode=ParseMode.HTML)
    msg = f'{ce("🔥")} <b>TOP TƯƠNG TÁC NHÓM</b> {ce("🔥")}\n━━━━━━━━━━━━━━━━━━━━━\n'
    for i, (uid, count, last) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        msg += f'{medal} <code>{uid}</code> — <code>{count}</code> lượt\n'
    msg += f'━━━━━━━━━━━━━━━━━━━━━\n{ce("🎯")} <b>MỐC:</b> 200 lượt → Liên hệ Admin!'
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
async def set_xoso_result_cmd(update, ctx):
    await update.message.reply_text(f'{ce("⚠️") if "⚠️" in CUSTOM_EMOJI else "⚠️"} Game Xổ Số đã bị xóa khỏi hệ thống!', parse_mode=ParseMode.HTML)

@admin_only
async def set_vongquay_result_cmd(update, ctx):
    await update.message.reply_text(f'{ce("⚠️") if "⚠️" in CUSTOM_EMOJI else "⚠️"} Game Vòng Quay đã bị xóa khỏi hệ thống!', parse_mode=ParseMode.HTML)

@admin_only
async def reset_tanthu_code_cmd(update, ctx):
    if len(ctx.args) < 1:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/resettanthu [ID]</code>', parse_mode=ParseMode.HTML)
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        return await update.message.reply_text(f'{ce("❌")} ID không hợp lệ!', parse_mode=ParseMode.HTML)
    user_check = query("SELECT 1 FROM users WHERE user_id=%s", (target_id,))
    if not user_check:
        return await update.message.reply_text(f'{ce("❌")} Không tìm thấy ID <code>{target_id}</code>!', parse_mode=ParseMode.HTML)
    query("DELETE FROM tanthu_code WHERE user_id=%s", (target_id,))
    new_code = gen_code()
    current_time = get_vietnam_datetime_db()
    query("INSERT INTO tanthu_code (user_id, code, received_at, used) VALUES (%s, %s, %s, 0)", (target_id, new_code, current_time))
    query("INSERT INTO codes (code, reward, uses) VALUES (%s, %s, %s)", (new_code, 20000, 1))
    await update.message.reply_text(f'{ce("✅")} Đã reset code tân thủ cho ID <code>{target_id}</code>\n{ce("🎁")} Code mới: <code>{new_code}</code>', parse_mode=ParseMode.HTML)

@admin_only
async def list_tanthu_code_cmd(update, ctx):
    pending_codes = query("SELECT tc.user_id, tc.code, tc.received_at, u.balance FROM tanthu_code tc LEFT JOIN users u ON tc.user_id = u.user_id WHERE tc.used = 0 ORDER BY tc.received_at DESC")
    if not pending_codes:
        return await update.message.reply_text(f'{ce("📌")} Không có code tân thủ nào!', parse_mode=ParseMode.HTML)
    msg = f'{ce("🎁")} <b>CODE TÂN THỦ CHƯA DÙNG</b>\n━━━━━━━━━━━━━━━━━━━━━\n'
    for user_id, code, received_at, balance in pending_codes[:20]:
        msg += f'\n{ce("👤")} <code>{user_id}</code>\n{ce("🎁")} <code>{code}</code>\n{ce("💰")} <code>{fmt_money(balance or 0)}đ</code>\n📅 {received_at}\n━━━━━━━━━━━━━━━━━━━━━\n'
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
async def lock_game_cmd(update, ctx):
    if len(ctx.args) < 3:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/lockgame [id] [game_id] [lock/unlock]</code>', parse_mode=ParseMode.HTML)
    try:
        target_id = int(ctx.args[0])
        game_id = int(ctx.args[1])
        action = ctx.args[2].lower()
        if action == "lock":
            query("INSERT INTO banned_games VALUES(%s, %s) ON CONFLICT DO NOTHING", (target_id, game_id))
            await update.message.reply_text(f'{ce("🔒")} Đã khóa game <code>{game_id}</code> cho <code>{target_id}</code>', parse_mode=ParseMode.HTML)
        elif action == "unlock":
            query("DELETE FROM banned_games WHERE user_id=%s AND game_id=%s", (target_id, game_id))
            await update.message.reply_text(f'{ce("🔓")} Đã mở game <code>{game_id}</code> cho <code>{target_id}</code>', parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f'{ce("❌")} ID không hợp lệ!', parse_mode=ParseMode.HTML)

@admin_only
async def bonus_vip_cmd(update, ctx):
    users = query("SELECT user_id, total_bet FROM users")
    if not users:
        return await update.message.reply_text(f'{ce("❌")} Không có người dùng!', parse_mode=ParseMode.HTML)
    confirm_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ XÁC NHẬN", callback_data="confirm_bonus_vip"),
        InlineKeyboardButton("❌ HỦY", callback_data="close_admin")
    ]])
    await update.message.reply_text(
        f'{ce("👑")} <b>THƯỞNG VIP HÀNG THÁNG</b>\n\nXác nhận?',
        reply_markup=confirm_kb, parse_mode=ParseMode.HTML)

@admin_only
async def give_money_cmd(update, ctx):
    uid = update.effective_user.id
    if is_banned(uid): return
    if len(ctx.args) < 2:
        return await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/give [ID] [Số_Tiền]</code>', parse_mode=ParseMode.HTML)
    try:
        target_id = int(ctx.args[0])
        amount = int(ctx.args[1])
        if amount < 10000:
            return await update.message.reply_text(f'{ce("❌")} Tối thiểu 10,000đ', parse_mode=ParseMode.HTML)
        if sub_money(uid, amount, f"Chuyển tiền tới {target_id}"):
            add_money(target_id, amount, f"Nhận tiền từ {uid}")
            await update.message.reply_text(f'{ce("✅")} Đã chuyển <code>{fmt_money(amount)}đ</code> tới <code>{target_id}</code>', parse_mode=ParseMode.HTML)
            try:
                await ctx.bot.send_message(target_id,
                    f'{ce("🔔")} Bạn nhận được <code>{fmt_money(amount)}đ</code> từ <code>{uid}</code>',
                    parse_mode=ParseMode.HTML)
            except: pass
        else:
            await update.message.reply_text(f'{ce("❌")} Số dư không đủ.', parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} Lỗi định dạng.', parse_mode=ParseMode.HTML)

# ============================================================
# JOB QUEUE
# ============================================================
async def bao_hiem_vip(context: ContextTypes.DEFAULT_TYPE):
    yesterday = (get_vietnam_time() - timedelta(days=1)).strftime("%d/%m/%Y")
    users = query("SELECT user_id, SUM(amount) FROM history WHERE time LIKE %s GROUP BY user_id", (f"%{yesterday}%",))
    for u_id, total in users:
        if total < -1000000:
            res = query("SELECT total_bet FROM users WHERE user_id=%s", (u_id,))
            total_bet = res[0][0] if res else 0
            vip_name, _ = get_vip_info(total_bet)
            if "VIP" in vip_name:
                percent = 2 if "VIP 1" in vip_name else 5
                hoan_tien = int(abs(total) * (percent / 100))
                add_money(u_id, hoan_tien, f"Bảo hiểm VIP {yesterday}")
                try:
                    await context.bot.send_message(u_id,
                        f'{ce("🛡")} <b>BẢO HIỂM VIP</b>\n\nHoàn <code>{percent}%</code>: <code>+{fmt_money(hoan_tien)}đ</code>.',
                        parse_mode=ParseMode.HTML)
                except: pass

async def send_interaction_reward(ctx: ContextTypes.DEFAULT_TYPE):
    today = get_vietnam_date()
    for gid in GROUP_IDS:
        try:
            top_users = query("SELECT user_id, interaction_count FROM daily_top_interactions WHERE group_id=%s AND date=%s AND rewarded=0 ORDER BY interaction_count DESC LIMIT 5", (gid, today))
            if not top_users or len(top_users) < 5: continue
            rewards = {1: 22000, 2: 11000, 3: 5000, 4: 5000, 5: 5000}
            codes = []
            for i, (uid, count) in enumerate(top_users[:5], 1):
                code = gen_code()
                reward = rewards.get(i, 5000)
                query("INSERT INTO codes (code, reward, uses) VALUES(%s, %s, %s)", (code, reward, 1))
                codes.append(f'Top {i} (ID {uid}): <code>{code}</code> - {fmt_money(reward)}đ')
                query("UPDATE daily_top_interactions SET rank=%s, reward_amount=%s, rewarded=1 WHERE user_id=%s AND group_id=%s AND date=%s", (i, reward, uid, gid, today))
            if codes:
                msg = f'{ce("🎁")} <b>CODE TƯƠNG TÁC NHÓM</b> {ce("🎁")}\n━━━━━━━━━━━━━━━━━━━━━\n' + "\n".join(codes) + f'\n━━━━━━━━━━━━━━━━━━━━━\n📅 {today}\n{ce("📌")} <code>/code [mã]</code> để nhận!'
                await ctx.bot.send_message(gid, msg, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f"Lỗi code tương tác nhóm {gid}: {e}")

# ============================================================
# CALLBACK HANDLER
# ============================================================
async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data
    uid = q.from_user.id

    if d.startswith("admin_") or d.startswith("mt_") or d.startswith("user_"):
        if d.startswith("mt_toggle_") or d in ["mt_turnoff_all", "mt_turnon_all"]:
            return await handle_mt_toggle_callback(update, ctx)
        if d.startswith("user_"):
            return await handle_user_maintenance_callback(update, ctx)
        if uid not in ADMIN_IDS:
            return await q.answer("❌ Không có quyền!", show_alert=True)
        if d.startswith("admin_detail_"):
            target_admin_id = int(d.split("_")[2])
            is_banned_flag = is_admin_banned(target_admin_id)
            kb = [[InlineKeyboardButton("🔧 QUẢN LÝ LỆNH", callback_data=f"admin_manage_cmds_{target_admin_id}")],
                  [InlineKeyboardButton("🚫 CẤM ADMIN" if not is_banned_flag else "✅ BỎ CẤM", callback_data=f"admin_toggle_ban_{target_admin_id}")],
                  [InlineKeyboardButton("🔙 QUAY LẠI", callback_data="admin_back")]]
            await q.edit_message_text(
                f'{ce("👤")} <b>ADMIN</b> <code>{target_admin_id}</code>\n'
                f'{ce("📊")} {"🚫 BỊ CẤM" if is_banned_flag else "✅ HOẠT ĐỘNG"}',
                reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
            return
        if d.startswith("admin_toggle_ban_"):
            target_admin_id = int(d.split("_")[3])
            if is_admin_banned(target_admin_id):
                query("DELETE FROM banned_admins WHERE admin_id=%s", (target_admin_id,))
                await q.answer(f"✅ Bỏ cấm admin {target_admin_id}", show_alert=True)
            else:
                now_str = get_vietnam_datetime_db()
                query("INSERT INTO banned_admins VALUES(%s, %s, %s, %s)", (target_admin_id, uid, "Quản lý qua bảng", now_str))
                await q.answer(f"🚫 Đã cấm admin {target_admin_id}", show_alert=True)
            await handle_callback(update, ctx)
            return
        if d.startswith("admin_manage_cmds_"):
            target_admin_id = int(d.split("_")[3])
            admin_commands = ["tile1","tileall","resetall","xoalsall","soduall","tong","thongke","baotri","cam","bocam","add","sub","ban","unban","nap","kmnap","kmnapvc","taocode","setname","resetsdall","xoals","check","info","resetbank","send","rep","tatroom","baotriall"]
            kb = []
            for cmd in admin_commands:
                is_banned_cmd = is_admin_command_banned(target_admin_id, cmd)
                status = "❌" if is_banned_cmd else "✅"
                kb.append([InlineKeyboardButton(f"{status} /{cmd}", callback_data=f"admin_toggle_cmd_{target_admin_id}_{cmd}")])
            kb.append([InlineKeyboardButton("🔙 QUAY LẠI", callback_data=f"admin_detail_{target_admin_id}")])
            await q.edit_message_text(f'{ce("📜")} <b>LỆNH CỦA ADMIN</b> <code>{target_admin_id}</code>', reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
            return
        if d.startswith("admin_toggle_cmd_"):
            parts = d.split("_")
            target_admin_id = int(parts[3])
            cmd_name = parts[4]
            if is_admin_command_banned(target_admin_id, cmd_name):
                query("DELETE FROM banned_admin_commands WHERE admin_id=%s AND command=%s", (target_admin_id, cmd_name))
                await q.answer(f"✅ MỞ /{cmd_name}", show_alert=True)
            else:
                now_str = get_vietnam_datetime_db()
                query("INSERT INTO banned_admin_commands VALUES(%s, %s, %s, %s, %s)", (target_admin_id, cmd_name, uid, "Qua bảng", now_str))
                await q.answer(f"❌ CẤM /{cmd_name}", show_alert=True)
            await handle_callback(update, ctx)
            return
        if d == "admin_back":
            return await quanlyadmin_cmd(update, ctx)

    if d == "menu_taixiu_room":
        msg = (
            f'{ce("🎲")} <b>TÀI XỈU ROOM</b> {ce("🎲")}\n\n'
            f'🔗 <b>Link vào phòng:</b>\n<a href="https://t.me/tai36xiu6">https://t.me/tai36xiu6</a>\n\n'
            f'{ce("📜")} <b>HƯỚNG DẪN:</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━━\n'
            f'1️⃣ Bấm link trên vào nhóm\n'
            f'2️⃣ Đặt cược:\n'
            f'   • <code>t [số_tiền]</code> hoặc <code>t max</code> - TÀI\n'
            f'   • <code>x [số_tiền]</code> hoặc <code>x max</code> - XỈU\n'
            f'   • <code>c [số_tiền]</code> hoặc <code>c max</code> - CHẴN\n'
            f'   • <code>l [số_tiền]</code> hoặc <code>l max</code> - LẺ\n\n'
            f'{ce("🏆")} <b>Tỉ lệ: x1.95</b>\n'
            f'{ce("💰")} <b>Cược không giới hạn!</b>\n'
            f'{ce("💵")} <b>Xem số dư:</b> <code>/sd</code>'
        )
        await q.message.edit_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        return

    if d == "confirm_reset_all_final":
        if uid not in ADMIN_IDS: return
        query("TRUNCATE users, history, codes, banned RESTART IDENTITY CASCADE")
        return await q.edit_message_text(f'{ce("✅")} <b>ĐÃ RESET SẠCH!</b>', parse_mode=ParseMode.HTML)

    if d.startswith("confirm_giftall_"):
        if uid not in ADMIN_IDS: return
        parts = d.split("_")
        amount = int(parts[2])
        reason = "_".join(parts[3:-1])
        users = query("SELECT user_id FROM users")
        sent_count = 0
        for user in users:
            try:
                add_money(user[0], amount, f"Quà Admin: {reason}")
                sent_count += 1
                await asyncio.sleep(0.1)
            except: pass
        await q.edit_message_text(f'{ce("✅")} Đã tặng <code>{fmt_money(amount)}đ</code> cho <code>{sent_count}</code> người!', parse_mode=ParseMode.HTML)
        return

    if d == "confirm_bonus_vip":
        if uid not in ADMIN_IDS: return
        users = query("SELECT user_id, total_bet FROM users")
        sent_count = 0
        for uid_, total_bet in users:
            if total_bet >= 50000000: bonus = 5000
            elif total_bet >= 20000000: bonus = 3000
            elif total_bet >= 10000000: bonus = 1500
            elif total_bet >= 5000000: bonus = 800
            elif total_bet >= 1000000: bonus = 500
            else: bonus = 0
            if bonus > 0:
                add_money(uid_, bonus, f"Thưởng VIP")
                sent_count += 1
        await q.edit_message_text(f'{ce("✅")} Đã thưởng VIP cho <code>{sent_count}</code> người!', parse_mode=ParseMode.HTML)
        return

    if d == "confirm_mofull":
        if uid not in ADMIN_IDS: return
        query("DELETE FROM banned")
        query("DELETE FROM banned_games")
        query("DELETE FROM banned_features")
        query("DELETE FROM banned_admins")
        query("DELETE FROM banned_admin_commands")
        await q.edit_message_text(f'{ce("✅")} <b>ĐÃ MỞ TẤT CẢ THÀNH CÔNG!</b>', parse_mode=ParseMode.HTML)
        return

    if d == "his_deposit":
        data = query("SELECT amount, time FROM deposit_history WHERE user_id=%s AND status='success' ORDER BY time DESC LIMIT 10", (uid,))
        text = f'{ce("📥")} <b>10 GIAO DỊCH NẠP GẦN NHẤT:</b>\n\n'
        if not data: text += "Trống."
        else:
            for row in data:
                text += f'{ce("✅")} <code>+{fmt_money(row[0])}đ</code> | <i>{row[1]}</i>\n'
        return await ctx.bot.send_message(uid, text, parse_mode=ParseMode.HTML)

    if d == "his_withdraw":
        data = query("SELECT amount, status, time FROM withdraw_history WHERE user_id=%s ORDER BY time DESC LIMIT 10", (uid,))
        text = f'{ce("📤")} <b>10 GIAO DỊCH RÚT GẦN NHẤT:</b>\n\n'
        if not data: text += "Trống."
        else:
            for row in data:
                status_icon = "✅" if row[1] == "success" else "❌" if row[1] == "rejected" else "⏳"
                text += f'{status_icon} <code>{fmt_money(row[0])}đ</code> | {row[1]} | <i>{row[2]}</i>\n'
        return await ctx.bot.send_message(uid, text, parse_mode=ParseMode.HTML)

    if d.startswith("accept_bonus_"):
        parts = d.split("_")
        target_id = int(parts[2]); bonus_amount = int(parts[3]); required_bet = int(parts[4])
        if q.from_user.id != target_id:
            return await q.answer("❌ Không phải yêu cầu của bạn!", show_alert=True)
        existing = query("SELECT 1 FROM user_bonus WHERE user_id=%s", (target_id,))
        if existing:
            await q.answer("❌ Đã nhận rồi!", show_alert=True)
            return
        add_bonus_with_requirement(target_id, bonus_amount, 3)
        await q.message.edit_text(
            f'{ce("🎁")} <b>ĐÃ NHẬN KHUYẾN MÃI!</b>\n'
            f'{ce("💰")} <code>+{fmt_money(bonus_amount)}đ</code>\n'
            f'{ce("🎯")} Yêu cầu cược: <code>{fmt_money(required_bet)}đ</code>',
            parse_mode=ParseMode.HTML)
        return

    if d.startswith("reject_bonus_"):
        target_id = int(d.split("_")[2])
        if q.from_user.id != target_id:
            return await q.answer("❌ Không phải yêu cầu của bạn!", show_alert=True)
        await q.message.edit_text(
            f'{ce("❌")} <b>Đã từ chối khuyến mãi!</b>\n{ce("💰")} Số dư: <code>{fmt_money(get_balance(target_id))}đ</code>',
            parse_mode=ParseMode.HTML)
        return

    if d.startswith("adm_page_"):
        if uid not in ADMIN_IDS: return
        new_page = int(d.split("_")[2])
        return await all_user(update, ctx, page=new_page)

    if d.startswith("adm_manage_"):
        if uid not in ADMIN_IDS: return
        parts = d.split("_")
        target_id = int(parts[2])
        current_page = int(parts[3]) if len(parts) > 3 else 0
        res = query("SELECT balance, refs, bank, stk, name, last_checkin, total_bet FROM users WHERE user_id=%s", (target_id,))
        if not res: return await q.answer("Không tìm thấy user!")
        u = res[0]
        status_text = f'{ce("🚫")} ĐANG CHẶN' if is_banned(target_id) else f'{ce("✅")} HOẠT ĐỘNG'
        msg = f'{ce("👤")} <b>USER:</b> <code>{target_id}</code>\n{ce("💰")} <code>{fmt_money(u[0])}đ</code>\n{ce("📊")} Tổng cược: <code>{fmt_money(u[6])}đ</code>\n{ce("🚦") if False else "🚦"} {status_text}'
        kb = [[InlineKeyboardButton("🚫 BAN", callback_data=f"adm_act_ban_{target_id}_{current_page}"),
               InlineKeyboardButton("✅ UNBAN", callback_data=f"adm_act_unban_{target_id}_{current_page}")],
              [InlineKeyboardButton("🔙 QUAY LẠI", callback_data=f"adm_page_{current_page}")]]
        return await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    if d.startswith("adm_act_"):
        if uid not in ADMIN_IDS: return
        parts = d.split("_")
        act = parts[2]; tid = int(parts[3]); page_to_return = int(parts[-1])
        if act == "ban": query("INSERT INTO banned VALUES(%s) ON CONFLICT (user_id) DO NOTHING", (tid,))
        elif act == "unban": query("DELETE FROM banned WHERE user_id=%s", (tid,))
        await q.answer("✅ OK!")
        return await handle_callback(update, ctx)

    if d.startswith("tg_mt_"):
        if uid not in ADMIN_IDS:
            return await q.answer("❌ Không có quyền!", show_alert=True)
        key = d.replace("tg_", "")
        new_val = "0" if check_mt(key) else "1"
        query("UPDATE settings SET value=%s WHERE key=%s", (new_val, key))
        await q.answer("✅ Đã cập nhật!", show_alert=True)
        return await baotri_cmd(update, ctx)

    if d == "close_admin":
        await q.message.delete()
        return

    if d.startswith("rate_"):
        return await handle_rate_callback(update, ctx)

    if d.startswith("ok_") or d.startswith("no_"):
        if uid not in ADMIN_IDS: return
        act, u_id, amt = d.split("_")
        u_id, amt = int(u_id), int(amt)
        if act == "ok":
            query("UPDATE withdraw_history SET status='success', admin_id=%s WHERE user_id=%s AND amount=%s AND status='pending'", (uid, u_id, amt))
            try:
                await ctx.bot.send_message(chat_id=LOG_GROUP_ID,
                    text=f'{ce("📤")} <b>RÚT TIỀN</b>\n{ce("👤")} <code>{u_id}</code>\n{ce("💰")} <code>{fmt_money(amt)}đ</code>\n{ce("✅")} Đã duyệt!',
                    parse_mode=ParseMode.HTML)
            except: pass
            await ctx.bot.send_message(u_id,
                f'{ce("✅")} Yêu cầu rút <code>{fmt_money(amt)}đ</code> đã được duyệt!',
                parse_mode=ParseMode.HTML)
            await q.edit_message_text(f'{ce("✅")} ĐÃ DUYỆT ID {u_id}', parse_mode=ParseMode.HTML)
        else:
            query("UPDATE withdraw_history SET status='rejected', admin_id=%s, admin_note='Từ chối' WHERE user_id=%s AND amount=%s AND status='pending'", (uid, u_id, amt))
            add_money(u_id, amt, "Hoàn tiền rút")
            await ctx.bot.send_message(u_id,
                f'{ce("❌")} Yêu cầu rút bị từ chối. Tiền đã hoàn lại.',
                parse_mode=ParseMode.HTML)
            await q.edit_message_text(f'{ce("❌")} TỪ CHỐI ID {u_id}', parse_mode=ParseMode.HTML)
        return

    if d == "menu_tx":
        if is_game_banned(uid, 1):
            return await ctx.bot.send_message(uid, f'{ce("🚫")} Bạn đã bị cấm chơi game này!', parse_mode=ParseMode.HTML)
        if check_mt('mt_taixiu') and uid not in ADMIN_IDS:
            return await ctx.bot.send_message(uid, f'{ce("⚙️")} Game đang bảo trì!', parse_mode=ParseMode.HTML)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("TÀI CHẴN (XXT + XXC)", callback_data="tx_XXTC")],
            [InlineKeyboardButton("TÀI LẺ (XXT + XXL)", callback_data="tx_XXTL")],
            [InlineKeyboardButton("XỈU CHẴN (XXX + XXC)", callback_data="tx_XXSC")],
            [InlineKeyboardButton("XỈU LẺ (XXX + XXL)", callback_data="tx_XXSL")]
        ])
        return await q.edit_message_text(
            f'{ce("🎲")} <b>TÀI XỈU 6D</b>\n\nChọn kiểu cược:\nVD cú pháp: <code>XXT 50000</code> hoặc <code>XXC 50000</code>',
            reply_markup=kb, parse_mode=ParseMode.HTML)

    if d.startswith("tx_"):
        code = d.replace("tx_", "")
        map_code = {"XXTC":"XXT","XXTL":"XXT","XXSC":"XXX","XXSL":"XXX"}
        real_code = map_code.get(code, code)
        await q.edit_message_text(
            f'{ce("🎲")} <b>{code}</b>\n\n{ce("👉") if False else "👉"} Gõ: <code>{real_code} [số_tiền]</code>\nVD: <code>{real_code} 50000</code>',
            parse_mode=ParseMode.HTML)
        return

    if d == "menu_xocdia":
        if is_game_banned(uid, 2):
            return await ctx.bot.send_message(uid, f'{ce("🚫")} Bạn đã bị cấm chơi game này!', parse_mode=ParseMode.HTML)
        if check_mt('mt_xocdia') and uid not in ADMIN_IDS:
            return await ctx.bot.send_message(uid, f'{ce("⚙️")} Game đang bảo trì!', parse_mode=ParseMode.HTML)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔴 CHẴN", callback_data="xd_chan_10000"), InlineKeyboardButton("⚪ LẺ", callback_data="xd_le_10000")],
        ])
        return await q.edit_message_text(
            f'💿 <b>XÓC ĐĨA</b>\n\nGõ lệnh: <code>/xd [chan/le] [số_tiền]</code>\nVD: <code>/xd chan 50000</code>',
            reply_markup=kb, parse_mode=ParseMode.HTML)

    if d.startswith("xd_"):
        parts = d.split("_")
        choice, amt = parts[1], int(parts[2])
        return await play_xocdia(update, ctx, choice, amt)

    if d == "menu_bc":
        if is_game_banned(uid, 3):
            return await ctx.bot.send_message(uid, f'{ce("🚫")} Bạn đã bị cấm chơi game này!', parse_mode=ParseMode.HTML)
        if check_mt('mt_baucua') and uid not in ADMIN_IDS:
            return await ctx.bot.send_message(uid, f'{ce("⚙️")} Game đang bảo trì!', parse_mode=ParseMode.HTML)
        await q.edit_message_text(
            f'🦀 <b>BẦU CUA TÔM CÁ</b>\n\nGõ lệnh: <code>/bc [nai/cua/ca/ho/tom/bau] [số_tiền]</code>\nVD: <code>/bc cua 50000</code>',
            parse_mode=ParseMode.HTML)
        return

# ============================================================
# ĐĂNG KÝ HANDLER
# ============================================================
application = ApplicationBuilder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("lienket", lien_ket))
application.add_handler(CommandHandler("rut", rut))
application.add_handler(CommandHandler("code", nhap_code))
application.add_handler(CommandHandler("his", history_pro))
application.add_handler(CommandHandler("checkprogress", check_bet_progress_cmd))
application.add_handler(CommandHandler("sd", sd_cmd))
application.add_handler(CommandHandler("xd", xd_cmd))
application.add_handler(CommandHandler("bc", bc_cmd))
application.add_handler(CommandHandler("group_status", group_status_cmd))

application.add_handler(CommandHandler("t", bet_tai_group))
application.add_handler(CommandHandler("x", bet_xiu_group))
application.add_handler(CommandHandler("c", bet_chan_group))
application.add_handler(CommandHandler("l", bet_le_group))

application.add_handler(CommandHandler("nap", nap_tien_admin))
application.add_handler(CommandHandler("add", add))
application.add_handler(CommandHandler("sub", sub))
application.add_handler(CommandHandler("ban", ban))
application.add_handler(CommandHandler("unban", unban))
application.add_handler(CommandHandler("stats", stats))
application.add_handler(CommandHandler("all", all_user))
application.add_handler(CommandHandler("info", admin_info))
application.add_handler(CommandHandler("hisall", history_all_admin))
application.add_handler(CommandHandler("send", broadcast))
application.add_handler(CommandHandler("rep", reply_user))
application.add_handler(CommandHandler("check", check_user_history))
application.add_handler(CommandHandler("thongke", dashboard_cmd))
application.add_handler(CommandHandler("tong", tong_cmd))
application.add_handler(CommandHandler("soduall", soduall_cmd))
application.add_handler(CommandHandler("tileall", tileall_set_cmd))
application.add_handler(CommandHandler("tile1", tile1_user_cmd))
application.add_handler(CommandHandler("tile1all", tile1all_cmd))
application.add_handler(CommandHandler("tilewin", tilewin_cmd))
application.add_handler(CommandHandler("chinhkq", chinhkq_cmd))
application.add_handler(CommandHandler("resetsdall", resetsdall_cmd))
application.add_handler(CommandHandler("xoalsall", xoalsall_cmd))
application.add_handler(CommandHandler("xoals", xoals_user_cmd))
application.add_handler(CommandHandler("setname", set_bot_name_cmd))
application.add_handler(CommandHandler("taocode", tao_code))
application.add_handler(CommandHandler("taocodeall", taocodeall_cmd))
application.add_handler(CommandHandler("xoacode", xoacode_cmd))
application.add_handler(CommandHandler("kmnap", kmnap_cmd))
application.add_handler(CommandHandler("kmnapvc", kmnapvc_cmd))
application.add_handler(CommandHandler("checkprogressadmin", admin_check_bet_progress_cmd))
application.add_handler(CommandHandler("baotri", baotri_cmd))
application.add_handler(CommandHandler("baotriht", baotri_he_thong_cmd))
application.add_handler(CommandHandler("baotriid", baotri_id_cmd))
application.add_handler(CommandHandler("baotriall", baotri_hethong_cmd))
application.add_handler(CommandHandler("baotritc", baotri_tong_cong_cmd))
application.add_handler(CommandHandler("cam", cam_cmd))
application.add_handler(CommandHandler("bocam", bocam_cmd))
application.add_handler(CommandHandler("daban", daban_cmd))
application.add_handler(CommandHandler("mofull", mofull_cmd))
application.add_handler(CommandHandler("tatroom", tatroom_cmd))
application.add_handler(CommandHandler("camadmin", cam_admin_cmd))
application.add_handler(CommandHandler("unbanadmin", unban_admin_cmd))
application.add_handler(CommandHandler("listbannedadmins", list_banned_admins_cmd))
application.add_handler(CommandHandler("camadmin1", camadmin1_cmd))
application.add_handler(CommandHandler("uncamadmin1", uncamadmin1_cmd))
application.add_handler(CommandHandler("quanlyadmin", quanlyadmin_cmd))
application.add_handler(CommandHandler("lsnap", lsnap_cmd))
application.add_handler(CommandHandler("lsrut", lsrut_cmd))
application.add_handler(CommandHandler("lsnapall", lsnapall_cmd))
application.add_handler(CommandHandler("lsrutall", lsrutall_cmd))
application.add_handler(CommandHandler("thongkenaprut", thongke_nap_rut_cmd))
application.add_handler(CommandHandler("resetbank", reset_bank))
application.add_handler(CommandHandler("checkbank", check_bank_cmd))
application.add_handler(CommandHandler("exportdb", export_db_cmd))
application.add_handler(CommandHandler("resetall", reset_all_confirm))
application.add_handler(CommandHandler("giftall", gift_all_cmd))
application.add_handler(CommandHandler("topthang", top_thang_cmd))
application.add_handler(CommandHandler("checktt", check_top_interaction))
application.add_handler(CommandHandler("lockgame", lock_game_cmd))
application.add_handler(CommandHandler("bonusvip", bonus_vip_cmd))
application.add_handler(CommandHandler("give", give_money_cmd))
application.add_handler(CommandHandler("resettanthu", reset_tanthu_code_cmd))
application.add_handler(CommandHandler("listtanthu", list_tanthu_code_cmd))
application.add_handler(CommandHandler("setxoso", set_xoso_result_cmd))
application.add_handler(CommandHandler("setvongquay", set_vongquay_result_cmd))

if application.job_queue:
    application.job_queue.run_daily(bao_hiem_vip, time=datetime.strptime("00:00:01", "%H:%M:%S").time())
    application.job_queue.run_repeating(send_interaction_reward, interval=60, first=10)

application.add_handler(CallbackQueryHandler(handle_callback))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_message))

async def main():
    global _bot_instance
    await application.initialize()
    await application.start()
    _bot_instance = application.bot
    for gid in GROUP_IDS:
        try:
            room_betting_enabled[gid] = True
            asyncio.create_task(run_dice_game_cycle(application.bot, gid, gid))
            print(f"✅ Đã khởi động game cho nhóm {gid}")
        except Exception as e:
            print(f"Lỗi nhóm {gid}: {e}")
    await application.updater.start_polling(drop_pending_updates=True)
    print("🤖 BOT ĐÃ ONLINE...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Bot đã dừng.")
    except Exception as e:
        print(f"❌ Lỗi: {e}")
