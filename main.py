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
import hashlib
from io import BytesIO
import pytz
import html

# ============================================================
# CUSTOM EMOJI MAPPING (Telegram Premium)
# ============================================================
CUSTOM_EMOJI = {
    "🎲": "5260547274957672345",
    "👥": "5453957997418004470",
    "💰": "5224257782013769471",
    "💸": "5231005931550030290",
    "📊": "5231200819986047254",
    "💬": "5303138782004924588",
    "🦌": "5422516277010774456",
    "🦀": "5319247469165433798",
    "💿": "5429118663946945233",
    "🎰": "5321295593040010652",
    "🃏": "5298499667569425533",
    "🎮": "5235989279024373566",
    "🎯": "5256131095094652290",
    "💎": "6003595618100974363",
    "💍": "5262922516426420894",
    "🍬": "5404573776253825754",
    "❤️": "5406926593698312391",
    "🏅": "5204271353565300127",
    "🥇": "5440539497383087970",
    "🥈": "5447203607294265305",
    "🥉": "5453902265922376865",
    "⚠️": "5447644880824181073",
    "➕": "5397916757333654639",
    "➖": "5382261056078881010",
    "📈": "5244837092042750681",
    "📉": "5246762912428603768",
    "✨": "5325547803936572038",
    "🌟": "5267500801240092311",
    "✅": "6003745186042089867",
    "❌": "5210952531676504517",
    "🔥": "5424972470023104089",
    "⚡": "5411590687663608498",
    "🔒": "5296369303661067030",
    "🔓": "5291873529464122510",
    "🔑": "5278573677900752088",
    "✔️": "5780463361175066565",
    "🆗": "5413617405421167103",
    "🆘": "5429262837409138106",
    "✏️": "5395444784611480792",
    "📍": "5321275372333979355",
    "🔗": "5271604874419647061",
    "📎": "5305265301917549162",
    "🗑": "5372825386591732174",
    "🗓": "5287606810168028257",
    "⌛": "5472026645659401564",
    "🔜": "5440621591387980068",
    "🚀": "5372917041193828849",
    "🌈": "5409109841538994759",
    "☀️": "5373021138316186413",
    "🌛": "5438362704878250587",
    "🎉": "5208541126583136130",
    "🏆": "5188344996356448758",
    "👑": "5433758796289685818",
    "🚫": "5462882007451185227",
    "💳": "5445353829304387411",
    "🛒": "5400090058030075645",
    "📥": "5443127283898405358",
    "📤": "5445355530111437729",
    "⏰": "5386415655253730366",
    "👀": "5210956306952758910",
    "💵": "5409048419211682843",
    "🎁": "5203996991054432397",
    "💠": "5461151367559141950",
    "🔔": "5458603043203327669",
    "📫": "5287533898803211359",
    "⚙️": "5267334530171169409",
    "🛠": "5462921117423384478",
    "📌": "5397782960512444700",
    "✍️": "5258500400918587241",
    "🆔": "5443038326535759644",
    "📜": "6098288123580518916",
    "📞": "5237988788164107500",
    "🛡": "5400250414929041085",
    "🔮": "5278651867780377852",
    "🐯": "5456463412393342595",
    "🐉": "5395493912344353272",
}

def ce(emoji: str) -> str:
    emoji_id = CUSTOM_EMOJI.get(emoji)
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>'
    return emoji

def ce_text(text: str) -> str:
    for emoji, emoji_id in CUSTOM_EMOJI.items():
        text = text.replace(emoji, f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>')
    return text

def fmt_money(amount: int) -> str:
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

# ============================================================
# DANH SÁCH GAME - ĐÃ XÓA GAME RỒNG HỔ (ID 6)
# ============================================================
games_to_keep = [
    (1, "TÀI XỈU ROOM"),
    (2, "XÚC XẮC ĐƠN"),
    (3, "LONG HỔ"),
    (4, "MINI POKER"),
    (5, "BACCARAT"),
    (7, "XÓC ĐĨA 4 VỊ"),
    (8, "TÀI XỈU MD5"),
]
for gid, name in games_to_keep:
    res = query("SELECT 1 FROM game_rates WHERE id=%s", (gid,))
    if not res:
        query("INSERT INTO game_rates VALUES(%s, %s, 10)", (gid, name))
    else:
        query("UPDATE game_rates SET name=%s WHERE id=%s", (name, gid))

query("DELETE FROM game_rates WHERE id > 8 OR id = 6")

try:
    query("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_bet BIGINT DEFAULT 0")
except:
    pass
try:
    query("ALTER TABLE users ADD COLUMN IF NOT EXISTS rate_bonus INTEGER DEFAULT NULL")
except:
    pass
try:
    query("ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_linked INTEGER DEFAULT 0")
except:
    pass

query("CREATE TABLE IF NOT EXISTS history (user_id BIGINT, amount BIGINT, note TEXT, time TEXT)")
query("CREATE TABLE IF NOT EXISTS banned (user_id BIGINT PRIMARY KEY)")
query("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

maintenance_keys = ['mt_taixiu_room', 'mt_xucxac_don', 'mt_longho', 'mt_minipoker', 'mt_baccarat', 'mt_xocdia4', 'mt_taixiumd5', 'mt_nap', 'mt_rut']
for k in maintenance_keys:
    res = query("SELECT 1 FROM settings WHERE key=%s", (k,))
    if not res:
        query("INSERT INTO settings VALUES(%s, '0')", (k,))

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
    query("INSERT INTO settings VALUES('jackpot_amount', '100000')")

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
    if rate >= 100:
        return True
    if rate <= 0:
        return False
    return random.randint(1, 100) <= rate

def is_game_banned(uid, gid):
    res = query("SELECT 1 FROM banned_games WHERE user_id=%s AND game_id=%s", (uid, gid))
    return len(res) > 0 if res else False

def is_feature_banned(uid, feature):
    res = query("SELECT 1 FROM banned_features WHERE user_id=%s AND feature=%s", (uid, feature))
    return len(res) > 0 if res else False

def get_vip_info(total_bet):
    if total_bet >= 50000000:
        return "VIP 5 (Kim Cương)", 5000
    if total_bet >= 20000000:
        return "VIP 4 (Vàng)", 3000
    if total_bet >= 10000000:
        return "VIP 3 (Bạc)", 1500
    if total_bet >= 5000000:
        return "VIP 2 (Đồng)", 800
    if total_bet >= 1000000:
        return "VIP 1", 500
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

def add_bonus_with_requirement(user_id, bonus_amount, required_multiplier=2):
    # Yêu cầu x2 vòng cược tổng số dư theo yêu cầu mới
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
                f'{ce("🎯")} <b>Yêu cầu cược:</b> <code>{fmt_money(req_bet)}đ</code> (x2 vòng)\n'
                f'{ce("✅")} <b>Tổng cược đã thực hiện:</b> <code>{fmt_money(curr_bet)}đ</code>\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'{ce("🔓")} <b>Bạn đã có thể rút tiền bình thường!</b>'
            )
            try:
                if _bot_instance:
                    await _bot_instance.send_message(user_id, message, parse_mode=ParseMode.HTML)
            except:
                pass
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

def get_deposit_info(user_id, amount=0):
    # Tạo QR với số tiền cụ thể nếu có
    qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-qr_only.png?amount={amount}&addInfo=Ndech%20{user_id}&accountName={ACCOUNT_NAME}"
    caption = (
        f'{ce("💳")} <b>THÔNG TIN NẠP TIỀN</b>\n\n'
        f'{ce("💳")} Ngân hàng: <b>MBBANK</b>\n'
        f'{ce("👥")} CTK: <b>{ACCOUNT_NAME}</b>\n'
        f'{ce("💰")} STK: <code>{ACCOUNT_NO}</code>\n'
        f'{ce("✍️")} Nội dung: <code>Ndech {user_id}</code>\n'
        f'{ce("💰")} Số tiền: <code>{fmt_money(amount)}đ</code>\n\n'
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
# JACKPOT / HŨ - RESET VỀ 100.000
# ============================================================
def get_jackpot():
    res = query("SELECT value FROM settings WHERE key='jackpot_amount'")
    if res:
        return int(res[0][0])
    query("INSERT INTO settings (key, value) VALUES ('jackpot_amount', '100000') ON CONFLICT (key) DO NOTHING")
    return 100000

def update_jackpot(amount):
    query("UPDATE settings SET value=%s WHERE key='jackpot_amount'", (str(amount),))

# ============================================================
# TÀI XỈU ROOM - 3 XÚC XẮC - RESET HŨ 100.000
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
                f'• Tài (11-18): <code>t [số_tiền]</code> hoặc <code>t max</code>\n'
                f'• Xỉu (3-10): <code>x [số_tiền]</code> hoặc <code>x max</code>\n'
                f'• Chẵn: <code>c [số_tiền]</code> hoặc <code>c max</code>\n'
                f'• Lẻ: <code>l [số_tiền]</code> hoặc <code>l max</code>\n\n'
                f'{ce("🏆")} <b>Tỉ lệ thưởng: x1.95</b>\n'
                f'{ce("💰")} <b>Cược không giới hạn!</b>\n\n'
                f'{ce("📊")} <b>TỔNG CƯỢC:</b>\n'
                f'{ce("🎲")} TÀI: <code>0đ</code>\n'
                f'{ce("🎲")} XỈU: <code>0đ</code>\n'
                f'🔴 CHẴN: <code>0đ</code>\n'
                f'⚪ LẺ: <code>0đ</code>\n'
                f'{ce("👥")} Người chơi: <code>0</code>\n\n'
                f'{ce("🎁")} Hũ jackpot: <code>{fmt_money(jackpot_now)}đ</code>'
            )
            start_msg = await bot.send_message(chat_id, start_text, parse_mode=ParseMode.HTML)
            game_state["message_id"] = start_msg.message_id
            last_sent_msg_id = start_msg.message_id

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
                    total_bet = tai_count + xiu_count + chan_count + le_count
                    
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
                        f'{ce("📊")} <b>TỔNG CƯỢC:</b> <code>{fmt_money(total_bet)}đ</code>\n'
                        f'{ce("👥")} Tổng người chơi: <code>{total_players}</code>\n'
                        f'{ce("🎁")} Hũ jackpot: <code>{fmt_money(jackpot_now)}đ</code>'
                    )
                    
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=last_sent_msg_id)
                    except:
                        pass
                    
                    try:
                        new_msg = await bot.send_message(chat_id, edit_text, parse_mode=ParseMode.HTML)
                        last_sent_msg_id = new_msg.message_id
                        game_state["message_id"] = new_msg.message_id
                    except:
                        pass

            game_state["status"] = "rolling"
            try:
                await bot.delete_message(chat_id=chat_id, message_id=last_sent_msg_id)
            except:
                pass
            await bot.send_message(chat_id,
                f'{ce("🔒")} <b>ĐÃ ĐÓNG CƯỢC PHIÊN #{session_id}!</b>\n{ce("⏰")} Đang lắc 3 xúc xắc...',
                parse_mode=ParseMode.HTML)

            # CHỈ CÒN 3 XÚC XẮC
            d1 = await bot.send_dice(chat_id, emoji="🎲")
            d2 = await bot.send_dice(chat_id, emoji="🎲")
            d3 = await bot.send_dice(chat_id, emoji="🎲")
            await asyncio.sleep(4)

            dice_values = [d1.dice.value, d2.dice.value, d3.dice.value]
            total = sum(dice_values)
            res_tx = "tai" if total >= 11 else "xiu"
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
                choice_display = {"tai": "T", "xiu": "X", "chan": "C", "le": "L"}.get(choice, "?")

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
                    except:
                        pass
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
                    except:
                        pass

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
                        jackpot_winners.append(f'{ce("👥")} <code>{w["user_id"]}</code>: <code>+{fmt_money(share)}đ</code>')
                        try:
                            await bot.send_message(w["user_id"],
                                f'{ce("🎉")} <b>NỔ HŨ JACKPOT!</b> {ce("🎉")}\n'
                                f'{ce("🎲")} Phiên #{session_id}: Ra 3 con 6!\n'
                                f'{ce("💰")} Cược: <code>{fmt_money(w["amount"])}đ</code>\n'
                                f'{ce("🎁")} Nhận hũ: <code>+{fmt_money(share)}đ</code>\n'
                                f'{ce("💵")} Số dư mới: <code>{fmt_money(get_balance(w["user_id"]))}đ</code>',
                                parse_mode=ParseMode.HTML)
                        except:
                            pass
                    # RESET HŨ VỀ 100.000
                    update_jackpot(100000)
                    jackpot_amount = 100000
            elif count_1 >= 3:
                winners = [b for b in game_state["bets"].values() if b["choice"] == "xiu"]
                if winners and jackpot_amount > 0:
                    total_bet_xiu = sum(w["amount"] for w in winners)
                    for w in winners:
                        share = int(jackpot_amount * (w["amount"] / total_bet_xiu))
                        add_money(w["user_id"], share, f"Nổ hũ Jackpot (3 con 1) +{share:,}đ")
                        jackpot_winners.append(f'{ce("👥")} <code>{w["user_id"]}</code>: <code>+{fmt_money(share)}đ</code>')
                        try:
                            await bot.send_message(w["user_id"],
                                f'{ce("🎉")} <b>NỔ HŨ JACKPOT!</b> {ce("🎉")}\n'
                                f'{ce("🎲")} Phiên #{session_id}: Ra 3 con 1!\n'
                                f'{ce("💰")} Cược: <code>{fmt_money(w["amount"])}đ</code>\n'
                                f'{ce("🎁")} Nhận hũ: <code>+{fmt_money(share)}đ</code>\n'
                                f'{ce("💵")} Số dư mới: <code>{fmt_money(get_balance(w["user_id"]))}đ</code>',
                                parse_mode=ParseMode.HTML)
                        except:
                            pass
                    # RESET HŨ VỀ 100.000
                    update_jackpot(100000)
                    jackpot_amount = 100000

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
                    f'🔄 Hũ đã reset về 100.000đ'
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
            f'Dùng lệnh: <code>/lienket [Ngân_hàng] [STK] [Tên]</code>'
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
    choice_display = {"tai": "T", "xiu": "X", "chan": "C", "le": "L"}.get(choice, "?")
    session_id = game.get("session_id", 0)
    win_amount = int(total_bet * 1.95)

    msg = (
        f'{ce("✅")} Đặt thành công — Phiên #{session_id}\n\n'
        f'🥷 Ẩn Danh\n'
        f'🎯 {choice_display} · {fmt_money(total_bet)}\n'
        f'💲 Tỷ lệ x1.95 · Thắng {fmt_money(win_amount)}\n'
        f'💰 Số dư: {fmt_money(new_balance)}'
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

async def bet_tai_group(update, ctx):
    await bet_group_handler(update, ctx, "tai")

async def bet_xiu_group(update, ctx):
    await bet_group_handler(update, ctx, "xiu")

async def bet_chan_group(update, ctx):
    await bet_group_handler(update, ctx, "chan")

async def bet_le_group(update, ctx):
    await bet_group_handler(update, ctx, "le")

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
        f'{ce("👥")} ID: <code>{uid}</code>\n'
        f'{ce("💵")} Số dư: <code>{fmt_money(balance)}đ</code>',
        parse_mode=ParseMode.HTML)

# ============================================================
# GAME XÚC XẮC ĐƠN
# ============================================================
async def play_xucxac_don(update, ctx, choice_code, amount):
    uid = update.effective_user.id
    if is_game_banned(uid, 2):
        return await update.message.reply_text(f'{ce("🚫")} Bạn đã bị cấm chơi trò chơi này!', parse_mode=ParseMode.HTML)
    if check_mt('mt_xucxac_don') and uid not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("⚙️")} Game Xúc Xắc Đơn đang bảo trì!', parse_mode=ParseMode.HTML)
    if not sub_money(uid, amount, f"Cược Xúc Xắc Đơn {choice_code}"):
        return await update.message.reply_text(f'{ce("❌")} Bạn không đủ số dư.', parse_mode=ParseMode.HTML)
    
    msg_status = await update.message.reply_text(f'{ce("🎲")} <b>ĐANG LẮC XÚC XẮC...</b>', parse_mode=ParseMode.HTML)
    dice = await update.message.reply_dice(emoji="🎲")
    await asyncio.sleep(4)
    
    result = dice.dice.value
    c = choice_code.upper()
    
    win = False
    multiplier = 1.95
    
    if c in ["XXC", "XXL", "XXT", "XXX"]:
        if c == "XXC" and result in [2, 4, 6]:
            win = True
        elif c == "XXL" and result in [1, 3, 5]:
            win = True
        elif c == "XXT" and result in [4, 5, 6]:
            win = True
        elif c == "XXX" and result in [1, 2, 3]:
            win = True
    elif c.startswith("D"):
        try:
            target = int(c[1])
            if result == target:
                win = True
                multiplier = 5
        except:
            pass
    
    if win:
        win_amt = int(amount * multiplier)
        add_money(uid, win_amt, f"Thắng Xúc Xắc Đơn {c}")
        status = f'{ce("✅")} <b>THẮNG</b> | Nhận: <code>+{fmt_money(win_amt)}đ</code>'
    else:
        status = f'{ce("❌")} <b>THUA</b>'
    
    await msg_status.edit_text(
        f'{ce("🎲")} <b>KẾT QUẢ XÚC XẮC ĐƠN</b>\n\n'
        f'{ce("🎲")} Xúc xắc: <b>{result}</b>\n'
        f'{ce("✍️")} Bạn chọn: <b>{c}</b>\n\n'
        f'{status}\n'
        f'{ce("💰")} Số dư: <code>{fmt_money(get_balance(uid))}đ</code>',
        parse_mode=ParseMode.HTML)

# ============================================================
# GAME LONG HỔ - ĐÃ SỬA LỖI TREO
# ============================================================
async def play_longho(update, ctx, choice, amount):
    uid = update.effective_user.id
    if is_game_banned(uid, 3):
        return await update.message.reply_text(f'{ce("🚫")} Bạn đã bị cấm chơi trò chơi này!', parse_mode=ParseMode.HTML)
    if check_mt('mt_longho') and uid not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("⚙️")} Game Long Hổ đang bảo trì!', parse_mode=ParseMode.HTML)
    if not sub_money(uid, amount, f"Cược Long Hổ {choice.upper()}"):
        return await update.message.reply_text(f'{ce("❌")} Bạn không đủ số dư.', parse_mode=ParseMode.HTML)
    
    msg_status = await update.message.reply_text(f'{ce("🎲")} <b>ĐANG CHIA BÀI...</b>', parse_mode=ParseMode.HTML)
    
    # SỬA LỖI TREO: Thêm timeout cho quá trình chia bài
    try:
        await asyncio.wait_for(asyncio.sleep(2), timeout=5.0)
    except asyncio.TimeoutError:
        await msg_status.edit_text(f'{ce("⚠️")} Hệ thống bận, vui lòng thử lại sau!', parse_mode=ParseMode.HTML)
        add_money(uid, amount, "Hoàn tiền Long Hổ (Lỗi hệ thống)")
        return
    
    long_card = random.randint(1, 13)
    ho_card = random.randint(1, 13)
    card_names = {1: "A", 11: "J", 12: "Q", 13: "K"}
    
    if long_card == ho_card:
        add_money(uid, amount, "Hoàn tiền Long Hổ (Hòa)")
        await msg_status.edit_text(
            f'{ce("🐯")} <b>LONG HỔ</b>\n\n'
            f'🐯 LONG: <b>{card_names.get(long_card, long_card)}</b>\n'
            f'🐉 HỔ: <b>{card_names.get(ho_card, ho_card)}</b>\n\n'
            f'⚖️ <b>HÒA!</b> Hoàn tiền: <code>{fmt_money(amount)}đ</code>\n'
            f'{ce("💰")} Số dư: <code>{fmt_money(get_balance(uid))}đ</code>',
            parse_mode=ParseMode.HTML)
        return
    
    result = "long" if long_card > ho_card else "ho"
    is_win = (choice == result)
    
    if is_win:
        win_amt = int(amount * 1.95)
        add_money(uid, win_amt, f"Thắng Long Hổ {choice.upper()}")
        status = f'{ce("🎉")} <b>THẮNG!</b> Nhận: <code>+{fmt_money(win_amt)}đ</code>'
    else:
        status = f'{ce("❌")} <b>THUA!</b>'
    
    await msg_status.edit_text(
        f'{ce("🐯")} <b>LONG HỔ</b>\n\n'
        f'🐯 LONG: <b>{card_names.get(long_card, long_card)}</b>\n'
        f'🐉 HỔ: <b>{card_names.get(ho_card, ho_card)}</b>\n\n'
        f'Kết quả: <b>{"LONG" if result == "long" else "HỔ"}</b>\n'
        f'{status}\n'
        f'{ce("💰")} Số dư: <code>{fmt_money(get_balance(uid))}đ</code>',
        parse_mode=ParseMode.HTML)

async def lh_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(
            f'{ce("❌")} Cú pháp: <code>/lh [long/ho] [số_tiền]</code>',
            parse_mode=ParseMode.HTML)
    choice = ctx.args[0].lower()
    if choice not in ["long", "ho"]:
        return await update.message.reply_text(
            f'{ce("❌")} Chỉ chọn <code>long</code> hoặc <code>ho</code>!',
            parse_mode=ParseMode.HTML)
    try:
        amt = int(ctx.args[1])
    except:
        return await update.message.reply_text(f'{ce("❌")} Số tiền không hợp lệ!', parse_mode=ParseMode.HTML)
    await play_longho(update, ctx, choice, amt)

# ============================================================
# GAME MINI POKER
# ============================================================
async def play_minipoker(update, ctx, amount):
    uid = update.effective_user.id
    if is_game_banned(uid, 4):
        return await update.message.reply_text(f'{ce("🚫")} Bạn đã bị cấm chơi trò chơi này!', parse_mode=ParseMode.HTML)
    if check_mt('mt_minipoker') and uid not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("⚙️")} Game Mini Poker đang bảo trì!', parse_mode=ParseMode.HTML)
    if not sub_money(uid, amount, f"Cược Mini Poker"):
        return await update.message.reply_text(f'{ce("❌")} Bạn không đủ số dư.', parse_mode=ParseMode.HTML)
    
    msg_status = await update.message.reply_text(f'{ce("🃏")} <b>ĐANG CHIA BÀI...</b>', parse_mode=ParseMode.HTML)
    await asyncio.sleep(2)
    
    suits = ["♠️", "♥️", "♦️", "♣️"]
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    
    cards = []
    for _ in range(5):
        suit = random.choice(suits)
        rank = random.choice(ranks)
        cards.append((rank, suit))
    
    rank_counts = {}
    for rank, suit in cards:
        rank_counts[rank] = rank_counts.get(rank, 0) + 1
    
    max_count = max(rank_counts.values())
    
    if max_count == 4:
        multiplier = 100
        hand_name = "TỨ QUÝ"
    elif max_count == 3:
        multiplier = 25
        hand_name = "BỘ BA"
    elif max_count == 2:
        pairs = sum(1 for c in rank_counts.values() if c == 2)
        if pairs == 2:
            multiplier = 10
            hand_name = "HAI ĐÔI"
        else:
            multiplier = 2
            hand_name = "MỘT ĐÔI"
    else:
        multiplier = 0
        hand_name = "BÀI RÁC"
    
    cards_str = " ".join([f"{r}{s}" for r, s in cards])
    
    if multiplier > 0:
        win_amt = int(amount * multiplier)
        add_money(uid, win_amt, f"Thắng Mini Poker {hand_name} x{multiplier}")
        status = f'{ce("🎉")} <b>THẮNG {hand_name}!</b> x{multiplier}\nNhận: <code>+{fmt_money(win_amt)}đ</code>'
    else:
        status = f'{ce("❌")} <b>THUA!</b> Bài rác'
    
    await msg_status.edit_text(
        f'{ce("🃏")} <b>MINI POKER</b>\n\n'
        f'🎴 Bài của bạn: {cards_str}\n'
        f'🏆 Bộ: <b>{hand_name}</b>\n\n'
        f'{status}\n'
        f'{ce("💰")} Số dư: <code>{fmt_money(get_balance(uid))}đ</code>',
        parse_mode=ParseMode.HTML)

async def mp_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 1:
        return await update.message.reply_text(
            f'{ce("❌")} Cú pháp: <code>/mp [số_tiền]</code>',
            parse_mode=ParseMode.HTML)
    try:
        amt = int(ctx.args[0])
    except:
        return await update.message.reply_text(f'{ce("❌")} Số tiền không hợp lệ!', parse_mode=ParseMode.HTML)
    await play_minipoker(update, ctx, amt)

# ============================================================
# GAME BACCARAT
# ============================================================
async def play_baccarat(update, ctx, choice, amount):
    uid = update.effective_user.id
    if is_game_banned(uid, 5):
        return await update.message.reply_text(f'{ce("🚫")} Bạn đã bị cấm chơi trò chơi này!', parse_mode=ParseMode.HTML)
    if check_mt('mt_baccarat') and uid not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("⚙️")} Game Baccarat đang bảo trì!', parse_mode=ParseMode.HTML)
    if not sub_money(uid, amount, f"Cược Baccarat {choice.upper()}"):
        return await update.message.reply_text(f'{ce("❌")} Bạn không đủ số dư.', parse_mode=ParseMode.HTML)
    
    msg_status = await update.message.reply_text(f'{ce("🎰")} <b>ĐANG CHIA BÀI BACCARAT...</b>', parse_mode=ParseMode.HTML)
    await asyncio.sleep(2)
    
    def draw_card():
        return random.randint(0, 9)
    
    player_score = (draw_card() + draw_card()) % 10
    banker_score = (draw_card() + draw_card()) % 10
    
    if player_score < 6:
        player_score = (player_score + draw_card()) % 10
    if banker_score < 6:
        banker_score = (banker_score + draw_card()) % 10
    
    if player_score > banker_score:
        result = "player"
        result_name = "PLAYER"
    elif banker_score > player_score:
        result = "banker"
        result_name = "BANKER"
    else:
        result = "tie"
        result_name = "TIE"
    
    is_win = (choice == result)
    
    if result == "tie" and choice != "tie":
        add_money(uid, amount, "Hoàn tiền Baccarat (Hòa)")
        status = f'⚖️ <b>HÒA!</b> Hoàn tiền: <code>{fmt_money(amount)}đ</code>'
    elif is_win:
        if choice == "tie":
            multiplier = 9
        elif choice == "banker":
            multiplier = 2
        else:
            multiplier = 2
        win_amt = int(amount * multiplier)
        add_money(uid, win_amt, f"Thắng Baccarat {choice.upper()} x{multiplier}")
        status = f'{ce("🎉")} <b>THẮNG!</b> x{multiplier}\nNhận: <code>+{fmt_money(win_amt)}đ</code>'
    else:
        status = f'{ce("❌")} <b>THUA!</b>'
    
    await msg_status.edit_text(
        f'{ce("🎰")} <b>BACCARAT</b>\n\n'
        f'👤 PLAYER: <b>{player_score}</b>\n'
        f'🏦 BANKER: <b>{banker_score}</b>\n\n'
        f'Kết quả: <b>{result_name}</b>\n'
        f'{status}\n'
        f'{ce("💰")} Số dư: <code>{fmt_money(get_balance(uid))}đ</code>',
        parse_mode=ParseMode.HTML)

async def baccarat_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(
            f'{ce("❌")} Cú pháp: <code>/bcr [player/banker/tie] [số_tiền]</code>',
            parse_mode=ParseMode.HTML)
    choice = ctx.args[0].lower()
    if choice not in ["player", "banker", "tie"]:
        return await update.message.reply_text(
            f'{ce("❌")} Chỉ chọn <code>player</code>, <code>banker</code> hoặc <code>tie</code>!',
            parse_mode=ParseMode.HTML)
    try:
        amt = int(ctx.args[1])
    except:
        return await update.message.reply_text(f'{ce("❌")} Số tiền không hợp lệ!', parse_mode=ParseMode.HTML)
    await play_baccarat(update, ctx, choice, amt)

# ============================================================
# GAME XÓC ĐĨA 4 VỊ
# ============================================================
async def play_xocdia4(update, ctx, choice, amount):
    uid = update.effective_user.id
    if is_game_banned(uid, 7):
        return await update.message.reply_text(f'{ce("🚫")} Bạn đã bị cấm chơi trò chơi này!', parse_mode=ParseMode.HTML)
    if check_mt('mt_xocdia4') and uid not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("⚙️")} Game Xóc Đĩa 4 Vị đang bảo trì!', parse_mode=ParseMode.HTML)
    if not sub_money(uid, amount, f"Cược Xóc Đĩa 4 Vị {choice.upper()}"):
        return await update.message.reply_text(f'{ce("❌")} Bạn không đủ số dư.', parse_mode=ParseMode.HTML)
    
    msg_status = await update.message.reply_text(f'💿 <b>ĐANG XÓC ĐĨA 4 VỊ...</b>', parse_mode=ParseMode.HTML)
    await asyncio.sleep(2)
    
    results = [random.randint(0, 1) for _ in range(4)]
    red_count = sum(results)
    icons = "".join(["🔴" if r == 1 else "⚪️" for r in results])
    is_chan = (red_count % 2 == 0)
    
    win = (choice == "chan" and is_chan) or (choice == "le" and not is_chan)
    
    if win:
        win_amt = int(amount * 1.95)
        add_money(uid, win_amt, f"Thắng Xóc Đĩa 4 Vị {choice.upper()}")
        status = f'{ce("🎉")} <b>THẮNG!</b> Nhận: <code>+{fmt_money(win_amt)}đ</code>'
    else:
        status = f'{ce("❌")} <b>THUA!</b>'
    
    await msg_status.edit_text(
        f'💿 <b>XÓC ĐĨA 4 VỊ</b>\n\n'
        f'{icons}\n'
        f'{ce("✍️")} {"CHẴN" if is_chan else "LẺ"} ({red_count} Đỏ)\n\n'
        f'{status}\n'
        f'{ce("💰")} Số dư: <code>{fmt_money(get_balance(uid))}đ</code>',
        parse_mode=ParseMode.HTML)

async def xd4_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(
            f'{ce("❌")} Cú pháp: <code>/xd4 [chan/le] [số_tiền]</code>',
            parse_mode=ParseMode.HTML)
    choice = ctx.args[0].lower()
    if choice not in ["chan", "le"]:
        return await update.message.reply_text(
            f'{ce("❌")} Chỉ chọn <code>chan</code> hoặc <code>le</code>!',
            parse_mode=ParseMode.HTML)
    try:
        amt = int(ctx.args[1])
    except:
        return await update.message.reply_text(f'{ce("❌")} Số tiền không hợp lệ!', parse_mode=ParseMode.HTML)
    await play_xocdia4(update, ctx, choice, amt)

# ============================================================
# GAME TÀI XỈU MD5
# ============================================================
async def play_taixiumd5(update, ctx, choice, amount):
    uid = update.effective_user.id
    if is_game_banned(uid, 8):
        return await update.message.reply_text(f'{ce("🚫")} Bạn đã bị cấm chơi trò chơi này!', parse_mode=ParseMode.HTML)
    if check_mt('mt_taixiumd5') and uid not in ADMIN_IDS:
        return await update.message.reply_text(f'{ce("⚙️")} Game Tài Xỉu MD5 đang bảo trì!', parse_mode=ParseMode.HTML)
    if not sub_money(uid, amount, f"Cược Tài Xỉu MD5 {choice.upper()}"):
        return await update.message.reply_text(f'{ce("❌")} Bạn không đủ số dư.', parse_mode=ParseMode.HTML)
    
    msg_status = await update.message.reply_text(f'{ce("🎲")} <b>ĐANG RANDOM MD5...</b>', parse_mode=ParseMode.HTML)
    await asyncio.sleep(2)
    
    seed_str = f"{uid}{get_vietnam_time().timestamp()}{random.randint(1, 999999)}"
    md5_hash = hashlib.md5(seed_str.encode()).hexdigest()
    
    d1 = int(md5_hash[0:2], 16) % 6 + 1
    d2 = int(md5_hash[2:4], 16) % 6 + 1
    d3 = int(md5_hash[4:6], 16) % 6 + 1
    
    total = d1 + d2 + d3
    is_tai = total >= 11
    is_chan = total % 2 == 0
    
    win = False
    if choice == "tai" and is_tai:
        win = True
    elif choice == "xiu" and not is_tai:
        win = True
    elif choice == "chan" and is_chan:
        win = True
    elif choice == "le" and not is_chan:
        win = True
    
    if win:
        win_amt = int(amount * 1.95)
        add_money(uid, win_amt, f"Thắng Tài Xỉu MD5 {choice.upper()}")
        status = f'{ce("🎉")} <b>THẮNG!</b> Nhận: <code>+{fmt_money(win_amt)}đ</code>'
    else:
        status = f'{ce("❌")} <b>THUA!</b>'
    
    await msg_status.edit_text(
        f'{ce("🎲")} <b>TÀI XỈU MD5</b>\n\n'
        f'🎲 Xúc xắc: <b>{d1} - {d2} - {d3}</b>\n'
        f'{ce("📊")} Tổng: <b>{total}</b> → {"TÀI" if is_tai else "XỈU"} {"CHẴN" if is_chan else "LẺ"}\n'
        f'🔐 MD5: <code>{md5_hash[:16]}...</code>\n\n'
        f'{status}\n'
        f'{ce("💰")} Số dư: <code>{fmt_money(get_balance(uid))}đ</code>',
        parse_mode=ParseMode.HTML)

async def txmd5_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(
            f'{ce("❌")} Cú pháp: <code>/txmd5 [tai/xiu/chan/le] [số_tiền]</code>',
            parse_mode=ParseMode.HTML)
    choice = ctx.args[0].lower()
    if choice not in ["tai", "xiu", "chan", "le"]:
        return await update.message.reply_text(
            f'{ce("❌")} Chỉ chọn <code>tai</code>, <code>xiu</code>, <code>chan</code> hoặc <code>le</code>!',
            parse_mode=ParseMode.HTML)
    try:
        amt = int(ctx.args[1])
    except:
        return await update.message.reply_text(f'{ce("❌")} Số tiền không hợp lệ!', parse_mode=ParseMode.HTML)
    await play_taixiumd5(update, ctx, choice, amt)

# ============================================================
# /start
# ============================================================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid):
        return
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
        except:
            pass
    menu = ReplyKeyboardMarkup([
        ["🎲 DANH SÁCH GAME", "👥 TÀI KHOẢN"],
        ["💰 NẠP TIỀN", "💸 RÚT TIỀN"],
        ["📊 LỊCH SỬ", "💬 HỖ TRỢ"]
    ], resize_keyboard=True)
    welcome_text = (
        f'{ce("🎉")} <b>CHÀO MỪNG {update.effective_user.first_name.upper()} ĐÃ THAM GIA!</b>\n\n'
        f'{ce("🛡")} <b>{get_bot_name()}</b>\n'
        f'Hệ thống trò chơi minh bạch — uy tín hàng đầu.\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("💰")} <b>MIN RÚT TIỀN:</b> <code>50,000đ</code>\n'
        f'{ce("💵")} <b>MIN NẠP TIỀN:</b> <code>10,000đ</code>\n\n'
        f'⚖️ <b>CAM KẾT MINH BẠCH:</b>\n'
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
    if is_banned(uid):
        return
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
        f'{ce("👥")} Chủ TK: {name}\n\n'
        f'{ce("🎮")} Bạn đã có thể tham gia chơi game!',
        parse_mode=ParseMode.HTML)

# ============================================================
# /rut
# ============================================================
async def rut(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid):
        return
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
            f'Hãy dùng lệnh: <code>/lienket [Ngân_hàng] [STK] [Tên]</code>\n\n'
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
                f'⚠️ <b>CHƯA ĐỦ ĐIỀU KIỆN RÚT TIỀN!</b>\n\n'
                f'{ce("💰")} Bạn đang có tiền khuyến mãi cần cược đủ <b>x2</b> vòng.\n'
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
                        f'{ce("👥")} <b>ID:</b> <code>{uid}</code>\n'
                        f'{ce("💰")} <b>Số tiền:</b> <code>{fmt_money(amount)}đ</code>\n'
                        f'{ce("💳")} <b>Ngân hàng:</b> <code>{bank}</code>\n'
                        f'{ce("💰")} <b>STK:</b> <code>{stk}</code>\n'
                        f'{ce("👥")} <b>Chủ TK:</b> <code>{name}</code>\n'
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
    if is_banned(uid):
        return
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
    if is_banned(uid):
        return
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
    if is_banned(uid):
        return
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
        f'{ce("🎯")} <b>Yêu cầu cược:</b> <code>{fmt_money(status["required_bet"])}đ</code> (x2 vòng)\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("📈")} <b>Tiến độ:</b>\n'
        f'<code>{bar}</code> <code>{percent:.1f}%</code>\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'{ce("✅")} <b>Đã cược:</b> <code>{fmt_money(status["current_bet"])}đ</code>\n'
        f'⚠️ <b>Cần cược thêm:</b> <code>{fmt_money(status["remaining"])}đ</code>\n'
    )
    if status['is_completed']:
        message += f'{ce("🎉")} <b>CHÚC MỪNG! BẠN ĐÃ HOÀN THÀNH!</b> {ce("🎉")}'
    else:
        message += f'{ce("🔥")} <b>CỐ GẮNG LÊN!</b>'
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

# ============================================================
# MENU HANDLER
# ============================================================
async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid, txt = update.effective_user.id, update.message.text
    if not txt or is_banned(uid):
        return
    if is_total_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ TOÀN BỘ</b>', parse_mode=ParseMode.HTML)
        return
    if is_system_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ</b>', parse_mode=ParseMode.HTML)
        return
    user_reply = update.message

    if txt == "👥 TÀI KHOẢN":
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
            f'{ce("👥")} <b>THÔNG TIN TÀI KHOẢN</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━━\n'
            f'{ce("🆔")} ID: <code>{uid}</code>\n'
            f'{ce("👑")} <b>Cấp VIP:</b> <code>{vip_name}</code>\n'
            f'{ce("💰")} Số dư: <code>{fmt_money(u[0])}đ</code>\n'
            f'{ce("📊")} <b>Tổng cược:</b> <code>{fmt_money(u[5])}đ</code>\n'
            f'{ce("👥")} Đã mời: <code>{u[4]}</code> người\n'
            f'{ce("💳")} Ngân hàng: <code>{u[1] or "Chưa liên kết"}</code>\n'
            f'{ce("💰")} STK: <code>{u[2] or "Chưa liên kết"}</code>\n'
            f'{ce("👥")} Tên: <code>{u[3] or "Chưa liên kết"}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━━'
        )
        return await user_reply.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

    if txt == "💰 NẠP TIỀN":
        if is_feature_banned(uid, 'nap'):
            return await user_reply.reply_text(f'{ce("🚫")} Tính năng NẠP TIỀN đã bị khóa!', parse_mode=ParseMode.HTML)
        if check_mt('mt_nap') and uid not in ADMIN_IDS:
            return await user_reply.reply_text(f'{ce("⚙️")} Nạp Tiền đang bảo trì!', parse_mode=ParseMode.HTML)
        # Hiển thị menu nạp tiền với các nút chọn mệnh giá
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("20k", callback_data="dep_20000"), InlineKeyboardButton("50k", callback_data="dep_50000"), InlineKeyboardButton("100k", callback_data="dep_100000")],
            [InlineKeyboardButton("200k", callback_data="dep_200000"), InlineKeyboardButton("500k", callback_data="dep_500000"), InlineKeyboardButton("1m", callback_data="dep_1000000")],
            [InlineKeyboardButton("2m", callback_data="dep_2000000"), InlineKeyboardButton("5m", callback_data="dep_5000000"), InlineKeyboardButton("10m", callback_data="dep_10000000")],
            [InlineKeyboardButton("20m", callback_data="dep_20000000"), InlineKeyboardButton("50m", callback_data="dep_50000000")],
            [InlineKeyboardButton("🔔 Hỗ Trợ", callback_data="dep_support")]
        ])
        caption = (
            f'{ce("🎁")} <b>Khuyến Mãi 10% NẠP TIỀN SIÊU TỐC</b>\n\n'
            f'{ce("📝")} <b>Lệnh nạp:</b> <code>/nap [số tiền]</code>\n'
            f'{ce("📝")} <b>Ví dụ:</b> <code>/nap 50000</code>\n'
            f'<code>/nap 50k</code>   <code>/nap 5m</code>\n\n'
            f'{ce("⚡")} <i>Chọn mệnh giá bên dưới hoặc nhập lệnh /nap số tiền</i>'
        )
        qr_url, _ = get_deposit_info(uid, 0)
        return await user_reply.reply_photo(photo=qr_url, caption=caption, reply_markup=kb, parse_mode=ParseMode.HTML)

    if txt == "🎲 DANH SÁCH GAME":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 TÀI XỈU ROOM", callback_data="menu_taixiu_room")],
            [InlineKeyboardButton("🎲 XÚC XẮC ĐƠN", callback_data="menu_xucxac_don")],
            [InlineKeyboardButton("🐯 LONG HỔ", callback_data="menu_longho")],
            [InlineKeyboardButton("🃏 MINI POKER", callback_data="menu_minipoker")],
            [InlineKeyboardButton("🎰 BACCARAT", callback_data="menu_baccarat")],
            [InlineKeyboardButton("💿 XÓC ĐĨA 4 VỊ", callback_data="menu_xocdia4")],
            [InlineKeyboardButton("🎲 TÀI XỈU MD5", callback_data="menu_taixiumd5")],
        ])
        return await user_reply.reply_text(
            f'{ce("🎲")} <b>DANH SÁCH TRÒ CHƠI</b>\nVui lòng chọn game:',
            reply_markup=kb, parse_mode=ParseMode.HTML)

    if txt == "💸 RÚT TIỀN":
        if is_feature_banned(uid, 'rut'):
            return await user_reply.reply_text(f'{ce("🚫")} Tính năng RÚT TIỀN đã bị khóa!', parse_mode=ParseMode.HTML)
        if check_mt('mt_rut') and uid not in ADMIN_IDS:
            return await user_reply.reply_text(f'{ce("⚙️")} Rút Tiền đang bảo trì!', parse_mode=ParseMode.HTML)
        res = query("SELECT bank, stk, name FROM users WHERE user_id=%s", (uid,))
        if not res or not res[0][0] or not res[0][1]:
            await user_reply.reply_text(
                f'{ce("❌")} Bạn chưa liên kết bank.\n'
                f'<code>/lienket [Bank] [STK] [Tên]</code>\n\n'
                f'{ce("📌")} <b>MIN RÚT:</b> <code>50,000đ</code>',
                parse_mode=ParseMode.HTML)
        else:
            u = res[0]
            await user_reply.reply_text(
                f'{ce("💳")} <b>TÀI KHOẢN RÚT:</b>\n'
                f'{ce("💳")} Bank: {u[0]}\n'
                f'{ce("💰")} STK: <code>{u[1]}</code>\n'
                f'{ce("👥")} Tên: {u[2]}\n\n'
                f'{ce("📌")} <b>MIN RÚT:</b> <code>50,000đ</code>\n\n'
                f'<code>/rut [số tiền]</code>',
                parse_mode=ParseMode.HTML)
        return

    if txt == "📊 LỊCH SỬ":
        return await history_pro(update, ctx)

    if txt == "💬 HỖ TRỢ":
        msg = (
            f'{ce("💬")} <b>HỖ TRỢ KHÁCH HÀNG</b>\n\n'
            f'{ce("👥")} <b>Hỗ Trợ:</b> @echcutodz\n'
            f'{ce("💬")} Phản hồi trong giờ hành chính!\n'
            f'━━━━━━━━━━━━━━━━━━━━━\n'
            f'{ce("📌")} <b>Các vấn đề có thể liên hệ:</b>\n'
            f'• Nạp tiền chậm\n'
            f'• Rút tiền chưa được duyệt\n'
            f'• Khiếu nại kết quả game'
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 NHẮN HỖ TRỢ", url="https://tply.me/echcutodz")]])
        return await user_reply.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

    # Xử lý lệnh Xúc Xắc Đơn (VD: D1 10000, XXC 50000)
    if len(txt.split()) == 2:
        parts = txt.split()
        code, amt_str = parts[0].upper(), parts[1]
        if code in ["XXC", "XXL", "XXX", "XXT", "D1", "D2", "D3", "D4", "D5", "D6"]:
            if check_mt('mt_xucxac_don') and uid not in ADMIN_IDS:
                return await update.message.reply_text(f'{ce("⚙️")} Game Xúc Xắc Đơn đang bảo trì!', parse_mode=ParseMode.HTML)
            try:
                amt = int(amt_str)
                return await play_xucxac_don(update, ctx, code, amt)
            except:
                pass

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
    if not text:
        return
    parts = text.strip().split()
    if not parts:
        return
    command = parts[0].lower()
    fake_ctx = type('obj', (object,), {'bot': ctx.bot, 'args': parts[1:], 'user_data': ctx.user_data, 'chat_data': ctx.chat_data})()
    if command == "t":
        await bet_tai_group(update, fake_ctx)
        return
    if command == "x":
        await bet_xiu_group(update, fake_ctx)
        return
    if command == "c":
        await bet_chan_group(update, fake_ctx)
        return
    if command == "l":
        await bet_le_group(update, fake_ctx)
        return
    await main_handler(update, ctx)

async def main_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_total_maintenance() and uid not in ADMIN_IDS:
        await update.message.reply_text(f'{ce("⚡")} <b>HỆ THỐNG ĐANG BẢO TRÌ TOÀN BỘ</b>', parse_mode=ParseMode.HTML)
        return
    await handle(update, ctx)

# ============================================================
# ADMIN COMMANDS
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
                text=f'{ce("✅")} <b>THÔNG BÁO NẠP TIỀN</b>\n{ce("👥")} ID: <code>{target_id}</code>\n{ce("💰")} Số tiền: <code>+{fmt_money(amount)}đ</code>\n{ce("👑")} Admin: <code>{update.effective_user.id}</code>',
                parse_mode=ParseMode.HTML)
        except:
            pass
        
        # Gửi thông báo nạp tiền thành công với nút nhận/từ chối khuyến mãi
        bonus_amount = int(amount * 0.10)  # 10% khuyến mãi
        if bonus_amount > 0:
            required_bet = bonus_amount * 2  # Yêu cầu x2 vòng cược
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
                    f'✨ <b>Thưởng nạp 10%:</b> <code>+{fmt_money(bonus_amount)}đ</code>\n'
                    f'{ce("🎯")} <b>Yêu cầu cược:</b> x2 vòng (<code>{fmt_money(required_bet)}đ</code>)\n'
                    f'⚠️ <b>Lưu ý:</b> Sau khi nhận thưởng phải x2 vòng cược tổng số dư tài khoản\n'
                    f'━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'Vui lòng chọn bên dưới:',
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
            f'{ce("👥")} ID: <code>{target_id}</code>\n'
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
    except:
        pass

@admin_only
async def sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid, amt = int(ctx.args[0]), int(ctx.args[1])
        sub_money(uid, amt, "Admin trừ tiền")
        await update.message.reply_text(f'{ce("✅")} Đã trừ <code>{fmt_money(amt)}đ</code> của ID <code>{uid}</code>', parse_mode=ParseMode.HTML)
    except:
        pass

@admin_only
async def ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(ctx.args[0])
        query("INSERT INTO banned(user_id) VALUES(%s) ON CONFLICT (user_id) DO NOTHING", (uid,))
        await update.message.reply_text(f'{ce("🚫")} Đã chặn người dùng <code>{uid}</code>', parse_mode=ParseMode.HTML)
    except:
        pass

@admin_only
async def unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(ctx.args[0])
        query("DELETE FROM banned WHERE user_id=%s", (uid,))
        await update.message.reply_text(f'{ce("✅")} Đã bỏ chặn người dùng <code>{uid}</code>', parse_mode=ParseMode.HTML)
    except:
        pass

@admin_only
async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    res = query("SELECT COUNT(*) FROM users")
    total = res[0][0] if res else 0
    await update.message.reply_text(
        f'{ce("📊")} <b>THỐNG KÊ:</b>\n\n{ce("👥")} Tổng số người dùng: <code>{total}</code>',
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
    text = f'{ce("👥")} <b>DANH SÁCH NGƯỜI DÙNG</b> (Tổng: {total_users})\nBấm vào User để xem chi tiết:'
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
            f'{ce("👥")} Số người mời: <code>{u[1]}</code>\n'
            f'{ce("💳")} Ngân hàng: <code>{u[2] or "Chưa cập nhật"}</code>\n'
            f'{ce("💰")} STK: <code>{u[3] or "Chưa cập nhật"}</code>\n'
            f'{ce("👥")} Tên: <code>{u[4] or "Chưa cập nhật"}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━━'
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(f'{ce("❌")} Cú pháp: <code>/info [ID]</code>', parse_mode=ParseMode.HTML)

@admin_only
async def history_all_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = query("SELECT * FROM history ORDER BY time DESC LIMIT 50")
    msg = f'{ce("📊")} <b>LỊCH SỬ TOÀN HỆ THỐNG:</b>\n\n'
    if data:
        for d in data:
            msg += f'{ce("👥")} <code>{d[0]}</code> | <code>{fmt_money(d[1])}đ</code> | {html.escape(d[2])}\n'
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
    status_msg = await update.message.reply_text(f'{ce("🚀")} Đang gửi tới {len(users)} người...', parse_mode=ParseMode.HTML)
    for user in users:
        try:
            await ctx.bot.send_message(chat_id=user[0],
                text=f'{ce("🔔")} <b>THÔNG BÁO MỚI</b>\n\n{html.escape(msg_to_send)}',
                parse_mode=ParseMode.HTML)
            sent += 1
            if sent % 20 == 0:
                await asyncio.sleep(1)
        except:
            failed += 1
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
            text=f'{ce("✍️")} <b>PHẢN HỒI TỪ ADMIN:</b>\n\n{html.escape(msg_reply)}',
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
            f'1. TÀI XỈU ROOM | 2. XÚC XẮC ĐƠN | 3. LONG HỔ | 4. MINI POKER\n'
            f'5. BACCARAT | 7. XÓC ĐĨA 4 VỊ | 8. TÀI XỈU MD5'
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
async def sethu_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin chỉnh số tiền trong hũ (jackpot)"""
    if not ctx.args:
        current_jackpot = get_jackpot()
        return await update.message.reply_text(
            f'{ce("🎁")} <b>QUẢN LÝ HŨ JACKPOT</b>\n\n'
            f'{ce("💰")} Số tiền hũ hiện tại: <code>{fmt_money(current_jackpot)}đ</code>\n\n'
            f'{ce("✍️")} <b>Cú pháp:</b> <code>/sethu [số_tiền]</code>\n'
            f'VD: <code>/sethu 50000000</code> (50 triệu)\n'
            f'Hoặc: <code>/sethu 11tỷ</code> (hỗ trợ đơn vị k, m, tỷ)',
            parse_mode=ParseMode.HTML)
    try:
        arg = ctx.args[0].lower().replace(".", "").replace(",", "")
        # Hỗ trợ đơn vị: k (nghìn), m (triệu), ty/tỷ (tỷ)
        if arg.endswith("ty") or arg.endswith("tỷ"):
            amount = int(float(arg.replace("ty", "").replace("tỷ", "")) * 1000000000)
        elif arg.endswith("m"):
            amount = int(float(arg.replace("m", "")) * 1000000)
        elif arg.endswith("k"):
            amount = int(float(arg.replace("k", "")) * 1000)
        else:
            amount = int(arg)
        
        if amount < 0:
            return await update.message.reply_text(f'{ce("❌")} Số tiền không được âm!', parse_mode=ParseMode.HTML)
        
        old_jackpot = get_jackpot()
        update_jackpot(amount)
        
        await update.message.reply_text(
            f'{ce("✅")} <b>ĐÃ CẬP NHẬT HŨ JACKPOT</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━━\n'
            f'{ce("📊")} <b>Số cũ:</b> <code>{fmt_money(old_jackpot)}đ</code>\n'
            f'{ce("💰")} <b>Số mới:</b> <code>{fmt_money(amount)}đ</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━━',
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(
            f'{ce("❌")} Số tiền không hợp lệ!\n'
            f'VD: <code>/sethu 50000000</code> hoặc <code>/sethu 50m</code> hoặc <code>/sethu 11tỷ</code>',
            parse_mode=ParseMode.HTML)

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
        required_bet = add_bonus_with_requirement(target_id, bonus_amount, 2)
        await update.message.reply_text(
            f'{ce("✅")} <b>KHUYẾN MÃI NẠP THÀNH CÔNG!</b>\n\n'
            f'{ce("👥")} <b>ID:</b> <code>{target_id}</code>\n'
            f'{ce("💰")} <b>Tiền thưởng:</b> <code>+{fmt_money(bonus_amount)}đ</code>\n'
            f'{ce("🎯")} <b>Yêu cầu cược:</b> <code>{fmt_money(required_bet)}đ</code>',
            parse_mode=ParseMode.HTML)
        await ctx.bot.send_message(target_id,
            f'{ce("🎁")} <b>THÔNG BÁO KHUYẾN MÃI</b>\n\n'
            f'Bạn vừa nhận được khuyến mãi nạp: <code>+{fmt_money(bonus_amount)}đ</code>\n\n'
            f'{ce("📌")} <b>Điều kiện rút tiền:</b>\n'
            f'• Cần cược <b>x2</b> vòng\n'
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
            f'{ce("👥")} <b>ID:</b> <code>{target_id}</code>\n'
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
        f'⚠️ <b>Còn thiếu:</b> <code>{fmt_money(status["remaining"])}đ</code>'
    )
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

# ============================================================
# BẢO TRÌ
# ============================================================
@admin_only
async def baotri_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    def st(k):
        return "🔴 OFF" if check_mt(k) else "🟢 ON"
    kb = [
        [InlineKeyboardButton(f"🎲 Tài Xỉu Room: {st('mt_taixiu_room')}", callback_data="tg_mt_taixiu_room")],
        [InlineKeyboardButton(f"🎲 Xúc Xắc Đơn: {st('mt_xucxac_don')}", callback_data="tg_mt_xucxac_don")],
        [InlineKeyboardButton(f"🐯 Long Hổ: {st('mt_longho')}", callback_data="tg_mt_longho")],
        [InlineKeyboardButton(f"🃏 Mini Poker: {st('mt_minipoker')}", callback_data="tg_mt_minipoker")],
        [InlineKeyboardButton(f"🎰 Baccarat: {st('mt_baccarat')}", callback_data="tg_mt_baccarat")],
        [InlineKeyboardButton(f"💿 Xóc Đĩa 4 Vị: {st('mt_xocdia4')}", callback_data="tg_mt_xocdia4")],
        [InlineKeyboardButton(f"🎲 Tài Xỉu MD5: {st('mt_taixiumd5')}", callback_data="tg_mt_taixiumd5")],
        [InlineKeyboardButton(f"💳 Nạp Tiền: {st('mt_nap')}", callback_data="tg_mt_nap"),
         InlineKeyboardButton(f"💸 Rút Tiền: {st('mt_rut')}", callback_data="tg_mt_rut")],
        [InlineKeyboardButton("❌ ĐÓNG BẢNG", callback_data="close_admin")]
    ]
    await update.message.reply_text(
        f'{ce("🛠")} <b>BẢNG QUẢN LÝ BẢO TRÌ</b>\n(Bấm để chuyển trạng thái On/Off)',
        reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

@admin_only
async def baotri_he_thong_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    maintenance_items = {
        'mt_taixiu_room': {'name': 'TÀI XỈU ROOM', 'type': 'game', 'icon': '🎲'},
        'mt_xucxac_don': {'name': 'XÚC XẮC ĐƠN', 'type': 'game', 'icon': '🎲'},
        'mt_longho': {'name': 'LONG HỔ', 'type': 'game', 'icon': '🐯'},
        'mt_minipoker': {'name': 'MINI POKER', 'type': 'game', 'icon': '🃏'},
        'mt_baccarat': {'name': 'BACCARAT', 'type': 'game', 'icon': '🎰'},
        'mt_xocdia4': {'name': 'XÓC ĐĨA 4 VỊ', 'type': 'game', 'icon': '💿'},
        'mt_taixiumd5': {'name': 'TÀI XỈU MD5', 'type': 'game', 'icon': '🎲'},
        'mt_nap': {'name': 'NẠP TIỀN', 'type': 'feature', 'icon': '💳'},
        'mt_rut': {'name': 'RÚT TIỀN', 'type': 'feature', 'icon': '💸'},
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
        f'<b>Bấm vào từng mục để bật/tắt:</b>',
        reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def handle_mt_toggle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    if uid not in ADMIN_IDS:
        await q.answer("❌ Bạn không có quyền!", show_alert=True)
        return
    data = q.data
    keys = ['mt_taixiu_room', 'mt_xucxac_don', 'mt_longho', 'mt_minipoker', 'mt_baccarat', 'mt_xocdia4', 'mt_taixiumd5', 'mt_nap', 'mt_rut']
    if data == "mt_turnoff_all":
        for key in keys:
            query("UPDATE settings SET value='1' WHERE key=%s", (key,))
        await q.answer("✅ Đã tắt BẢO TRÌ tất cả!", show_alert=True)
        await baotri_he_thong_cmd(update, ctx)
    elif data == "mt_turnon_all":
        for key in keys:
            query("UPDATE settings SET value='0' WHERE key=%s", (key,))
        await q.answer("✅ Đã bật HOẠT ĐỘNG tất cả!", show_alert=True)
        await baotri_he_thong_cmd(update, ctx)
    elif data.startswith("mt_toggle_"):
        key = data.replace("mt_toggle_", "")
        new_val = "1" if not check_mt(key) else "0"
        query("UPDATE settings SET value=%s WHERE key=%s", (new_val, key))
        names = {'mt_taixiu_room': 'TÀI XỈU ROOM', 'mt_xucxac_don': 'XÚC XẮC ĐƠN', 'mt_longho': 'LONG HỔ', 'mt_minipoker': 'MINI POKER', 'mt_baccarat': 'BACCARAT', 'mt_xocdia4': 'XÓC ĐĨA 4 VỊ', 'mt_taixiumd5': 'TÀI XỈU MD5', 'mt_nap': 'NẠP TIỀN', 'mt_rut': 'RÚT TIỀN'}
        status = "🔴 ĐANG BẢO TRÌ" if new_val == "1" else "🟢 HOẠT ĐỘNG"
        await q.answer(f"{names.get(key, key)}: {status}", show_alert=True)
        await baotri_he_thong_cmd(update, ctx)

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

# ============================================================
# CALLBACK HANDLER
# ============================================================
async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data
    uid = q.from_user.id

    # ===== XỬ LÝ NÚT NẠP TIỀN =====
    if d.startswith("dep_"):
        if d == "dep_support":
            return await q.message.edit_text(
                f'{ce("🔔")} <b>HỖ TRỢ NẠP TIỀN</b>\n\n'
                f'Vui lòng liên hệ Admin: @echcutodz\n'
                f'Hoặc nhập lệnh <code>/nap [số tiền]</code> để tạo QR.',
                parse_mode=ParseMode.HTML)
        try:
            amount = int(d.split("_")[1])
            qr_url, caption = get_deposit_info(uid, amount)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Đổi số tiền", callback_data="dep_change")],
                [InlineKeyboardButton("🔔 Hỗ Trợ", callback_data="dep_support")]
            ])
            return await q.message.edit_media(
                media=InputMediaPhoto(media=qr_url, caption=caption, parse_mode=ParseMode.HTML),
                reply_markup=kb
            )
        except:
            pass

    if d == "dep_change":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("20k", callback_data="dep_20000"), InlineKeyboardButton("50k", callback_data="dep_50000"), InlineKeyboardButton("100k", callback_data="dep_100000")],
            [InlineKeyboardButton("200k", callback_data="dep_200000"), InlineKeyboardButton("500k", callback_data="dep_500000"), InlineKeyboardButton("1m", callback_data="dep_1000000")],
            [InlineKeyboardButton("2m", callback_data="dep_2000000"), InlineKeyboardButton("5m", callback_data="dep_5000000"), InlineKeyboardButton("10m", callback_data="dep_10000000")],
            [InlineKeyboardButton("20m", callback_data="dep_20000000"), InlineKeyboardButton("50m", callback_data="dep_50000000")],
            [InlineKeyboardButton("🔔 Hỗ Trợ", callback_data="dep_support")]
        ])
        caption = (
            f'{ce("🎁")} <b>Khuyến Mãi 10% NẠP TIỀN SIÊU TỐC</b>\n\n'
            f'{ce("📝")} <b>Lệnh nạp:</b> <code>/nap [số tiền]</code>\n'
            f'{ce("📝")} <b>Ví dụ:</b> <code>/nap 50000</code>\n'
            f'<code>/nap 50k</code>   <code>/nap 5m</code>\n\n'
            f'{ce("⚡")} <i>Chọn mệnh giá bên dưới hoặc nhập lệnh /nap số tiền</i>'
        )
        qr_url, _ = get_deposit_info(uid, 0)
        return await q.message.edit_media(
            media=InputMediaPhoto(media=qr_url, caption=caption, parse_mode=ParseMode.HTML),
            reply_markup=kb
        )

    # ===== MENU TÀI XỈU ROOM =====
    if d == "menu_taixiu_room":
        msg = (
            f'🎲 <b>TÀI XỈU ROOM</b> 🎲\n\n'
            f'🔗 <b>Link vào phòng:</b>\n'
            f'https://t.me/fb88clmmcx\n\n'
            f'📜 <b>HƯỚNG DẪN:</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━━\n'
            f'1️⃣ Bấm link trên vào nhóm\n'
            f'2️⃣ Đặt cược:\n'
            f'   • <code>t [số_tiền]</code> hoặc <code>t max</code> - TÀI\n'
            f'   • <code>x [số_tiền]</code> hoặc <code>x max</code> - XỈU\n'
            f'   • <code>c [số_tiền]</code> hoặc <code>c max</code> - CHẴN\n'
            f'   • <code>l [số_tiền]</code> hoặc <code>l max</code> - LẺ\n\n'
            f'🏆 <b>Tỉ lệ: x1.95</b>\n\n'
            f'❓ <b>Luật chơi Tài Xỉu</b>\n\n'
            f'🎲 <b>T / X:</b> Tổng 11–18 Tài / 3–10 Xỉu\n'
            f'🎯 <b>C / L:</b> Tổng chẵn Chẵn / lẻ Lẻ\n'
            f'🔥 <b>TL/TC/XL/XC:</b> một lệnh kết hợp hai cửa — phải thắng cả hai mới ăn · trả x3.2\n'
            f'👑 <b>A1–A6:</b> chọn bộ ba　• <b>D4–D17:</b> tổng điểm\n'
            f'🥷 <b>Ẩn danh:</b> TT · XX · CC · LL — nhắn riêng FB88\n'
            f'❗️ Min 1.000. Không đặt ngược cửa.\n\n'
            f'🥇 <b>Hũ Tài Xỉu</b>\n'
            f'1️⃣ Phiên nhà cái có lời → góp 1% vào hũ nhóm đó\n'
            f'2️⃣ Ra Bão 666 → trả 50% hũ hiện tại theo tỉ lệ cược phiên\n'
            f'3️⃣ Cược cộng dồn trong phiên đủ 10.000 mới được chia hũ\n'
            f'🎁 Tiền vào số dư ngay · Cược lại x1\n'
            f'🔥 Giờ vàng (13:00–14:00 & 21:00–22:00): hũ +888K\n'
            f'🎉 Ra Bão 111–666: TOP 3 cược phiên nhận Code Bão\n\n'
            f'📣 Kết quả cược và trả thưởng sẽ được FB88 báo riêng cho bạn.'
        )
        await q.message.edit_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        return

    # ===== MENU XÚC XẮC ĐƠN =====
    if d == "menu_xucxac_don":
        msg = (
            f'🎲 <b>XÚC XẮC TELEGRAM</b> 🎲\n\n'
            f'👉 Khi BOT trả lời mới được tính là đã đặt cược thành công. Nếu BOT không trả lời => Lượt chơi không hợp lệ và không bị trừ tiền trong tài khoản.\n'
            f'👉 Xúc xắc được quay random bởi Telegram nên hoàn toàn xanh chín.\n\n'
            f'❗️❗️❗️ <b>Lưu ý:</b> Các biểu tượng Emoji của Telegram click vào có thể tương tác được tránh bị nhầm lẫn các đối tượng giả mạo bằng ảnh gif ❗️❗️❗️\n\n'
            f'🔖 <b>Thể lệ:</b>\n'
            f'👍 Kết quả được tính bằng mặt Xúc Xắc Telegram trả về sau khi người chơi đặt cược:\n'
            f'<code>XXC</code>  ➤   x1.95  ➤ Xúc Xắc: 2,4,6\n'
            f'<code>XXL</code>  ➤   x1.95  ➤ Xúc Xắc: 1,3,5\n'
            f'<code>XXT</code>  ➤   x1.95  ➤ Xúc Xắc: 4,5,6\n'
            f'<code>XXX</code>  ➤   x1.95  ➤ Xúc Xắc: 1,2,3\n'
            f'<code>D1</code>   ➤   x5  ➤ Xúc Xắc: 1\n'
            f'<code>D2</code>   ➤   x5  ➤ Xúc Xắc: 2\n'
            f'<code>D3</code>   ➤   x5  ➤ Xúc Xắc: 3\n'
            f'<code>D4</code>   ➤   x5  ➤ Xúc Xắc: 4\n'
            f'<code>D5</code>   ➤   x5  ➤ Xúc Xắc: 5\n'
            f'<code>D6</code>   ➤   x5  ➤ Xúc Xắc: 6\n\n'
            f'🎮 <b>Cách chơi:</b>\n'
            f'👉 Chat tại đây nội dung như sau:\n'
            f'   "Nội dung" dấu cách "Số tiền cược"\n'
            f'   VD: <code>D1 10000</code> hoặc <code>XXC 50000</code>'
        )
        await q.message.edit_text(msg, parse_mode=ParseMode.HTML)
        return

    # ===== MENU LONG HỔ =====
    if d == "menu_longho":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🐯 LONG", callback_data="lh_long"), InlineKeyboardButton("🐉 HỔ", callback_data="lh_ho")]
        ])
        await q.message.edit_text(
            f'🐯 <b>LONG HỔ</b> 🐉\n\n'
            f'📜 <b>Luật chơi:</b>\n'
            f'• So sánh điểm 2 lá bài LONG và HỔ\n'
            f'• Bên nào điểm cao hơn thắng\n'
            f'• Nếu bằng điểm → Hòa, hoàn tiền\n\n'
            f'🏆 <b>Tỉ lệ ăn: x1.95</b>\n\n'
            f'Chọn cửa để đặt cược:',
            reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if d.startswith("lh_"):
        choice = d.split("_")[1]
        choice_name = "LONG" if choice == "long" else "HỔ"
        await q.message.edit_text(
            f'🐯 <b>LONG HỔ</b>\n\n'
            f'Bạn chọn: <b>{choice_name}</b>\n\n'
            f'Nhập số tiền cược: <code>/lh {choice} [số_tiền]</code>\n'
            f'VD: <code>/lh {choice} 50000</code>',
            parse_mode=ParseMode.HTML)
        return

    # ===== MENU MINI POKER =====
    if d == "menu_minipoker":
        msg = (
            f'🃏 <b>MINI POKER</b>\n\n'
            f'📜 <b>Luật chơi:</b>\n'
            f'• Nhận 5 lá bài ngẫu nhiên\n'
            f'• So sánh bộ bài để tính thưởng:\n'
            f'  - <b>Tứ Quý</b> (4 lá cùng rank): x100\n'
            f'  - <b>Bộ Ba</b> (3 lá cùng rank): x25\n'
            f'  - <b>Hai Đôi</b>: x10\n'
            f'  - <b>Một Đôi</b>: x2\n'
            f'  - <b>Bài Rác</b>: Thua\n\n'
            f'🎮 <b>Cách chơi:</b>\n'
            f'<code>/mp [số_tiền]</code>\n'
            f'VD: <code>/mp 50000</code>'
        )
        await q.message.edit_text(msg, parse_mode=ParseMode.HTML)
        return

    # ===== MENU BACCARAT =====
    if d == "menu_baccarat":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 PLAYER (x2)", callback_data="bcr_player"), InlineKeyboardButton("🏦 BANKER (x2)", callback_data="bcr_banker")],
            [InlineKeyboardButton("⚖️ TIE (x9)", callback_data="bcr_tie")]
        ])
        await q.message.edit_text(
            f'🎰 <b>BACCARAT</b>\n\n'
            f'📜 <b>Luật chơi:</b>\n'
            f'• So sánh điểm PLAYER và BANKER\n'
            f'• Điểm gần 9 nhất thắng\n'
            f'• TIE (Hòa) trả x9\n\n'
            f'🏆 <b>Tỉ lệ:</b>\n'
            f'• PLAYER: x2\n'
            f'• BANKER: x2\n'
            f'• TIE: x9\n\n'
            f'Chọn cửa để đặt cược:',
            reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if d.startswith("bcr_"):
        choice = d.split("_")[1]
        choice_name = choice.upper()
        await q.message.edit_text(
            f'🎰 <b>BACCARAT</b>\n\n'
            f'Bạn chọn: <b>{choice_name}</b>\n\n'
            f'Nhập số tiền cược: <code>/bcr {choice} [số_tiền]</code>\n'
            f'VD: <code>/bcr {choice} 50000</code>',
            parse_mode=ParseMode.HTML)
        return

    # ===== MENU XÓC ĐĨA 4 VỊ =====
    if d == "menu_xocdia4":
        msg = (
            f'💿 <b>XÓC ĐĨA 4 VỊ</b>\n\n'
            f'📜 <b>Luật chơi:</b>\n'
            f'• 4 đồng xu được xóc ngẫu nhiên\n'
            f'• Đếm số mặt ĐỎ (🔴)\n'
            f'• Chẵn: 0, 2, 4 đỏ\n'
            f'• Lẻ: 1, 3 đỏ\n\n'
            f'🏆 <b>Tỉ lệ ăn: x1.95</b>\n\n'
            f'🎮 <b>Cách chơi:</b>\n'
            f'<code>/xd4 [chan/le] [số_tiền]</code>\n'
            f'VD: <code>/xd4 chan 50000</code>'
        )
        await q.message.edit_text(msg, parse_mode=ParseMode.HTML)
        return

    # ===== MENU TÀI XỈU MD5 =====
    if d == "menu_taixiumd5":
        msg = (
            f'🎲 <b>TÀI XỈU MD5</b>\n\n'
            f'📜 <b>Luật chơi:</b>\n'
            f'• Dùng hash MD5 để random 3 xúc xắc\n'
            f'• Tổng 11-18: TÀI\n'
            f'• Tổng 3-10: XỈU\n'
            f'• Tổng chẵn: CHẴN\n'
            f'• Tổng lẻ: LẺ\n\n'
            f'🏆 <b>Tỉ lệ ăn: x1.95</b>\n\n'
            f'🎮 <b>Cách chơi:</b>\n'
            f'<code>/txmd5 [tai/xiu/chan/le] [số_tiền]</code>\n'
            f'VD: <code>/txmd5 tai 50000</code>'
        )
        await q.message.edit_text(msg, parse_mode=ParseMode.HTML)
        return

    # ===== CALLBACK ADMIN =====
    if d.startswith("admin_") or d.startswith("mt_") or d.startswith("user_"):
        if d.startswith("mt_toggle_") or d in ["mt_turnoff_all", "mt_turnon_all"]:
            return await handle_mt_toggle_callback(update, ctx)
        if d.startswith("user_"):
            return await handle_user_maintenance_callback(update, ctx)
        if uid not in ADMIN_IDS:
            return await q.answer("❌ Không có quyền!", show_alert=True)
        if d == "admin_back":
            return await quanlyadmin_cmd(update, ctx)

    if d == "confirm_reset_all_final":
        if uid not in ADMIN_IDS:
            return
        query("TRUNCATE users, history, codes, banned RESTART IDENTITY CASCADE")
        return await q.edit_message_text(f'{ce("✅")} <b>ĐÃ RESET SẠCH!</b>', parse_mode=ParseMode.HTML)

    if d == "confirm_mofull":
        if uid not in ADMIN_IDS:
            return
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
        if not data:
            text += "Trống."
        else:
            for row in data:
                text += f'{ce("✅")} <code>+{fmt_money(row[0])}đ</code> | <i>{row[1]}</i>\n'
        return await ctx.bot.send_message(uid, text, parse_mode=ParseMode.HTML)

    if d == "his_withdraw":
        data = query("SELECT amount, status, time FROM withdraw_history WHERE user_id=%s ORDER BY time DESC LIMIT 10", (uid,))
        text = f'{ce("📤")} <b>10 GIAO DỊCH RÚT GẦN NHẤT:</b>\n\n'
        if not data:
            text += "Trống."
        else:
            for row in data:
                status_icon = "✅" if row[1] == "success" else "❌" if row[1] == "rejected" else "⏳"
                text += f'{status_icon} <code>{fmt_money(row[0])}đ</code> | {row[1]} | <i>{row[2]}</i>\n'
        return await ctx.bot.send_message(uid, text, parse_mode=ParseMode.HTML)

    if d.startswith("accept_bonus_"):
        parts = d.split("_")
        target_id = int(parts[2])
        bonus_amount = int(parts[3])
        required_bet = int(parts[4])
        if q.from_user.id != target_id:
            return await q.answer("❌ Không phải yêu cầu của bạn!", show_alert=True)
        existing = query("SELECT 1 FROM user_bonus WHERE user_id=%s", (target_id,))
        if existing:
            await q.answer("❌ Đã nhận rồi!", show_alert=True)
            return
        add_bonus_with_requirement(target_id, bonus_amount, 2)
        await q.message.edit_text(
            f'{ce("🎁")} <b>ĐÃ NHẬN KHUYẾN MÃI!</b>\n'
            f'{ce("💰")} <code>+{fmt_money(bonus_amount)}đ</code>\n'
            f'{ce("🎯")} Yêu cầu cược: <code>{fmt_money(required_bet)}đ</code>\n'
            f'⚠️ <b>Lưu ý:</b> Sau khi nhận thưởng phải x2 vòng cược tổng số dư tài khoản',
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
        if uid not in ADMIN_IDS:
            return
        new_page = int(d.split("_")[2])
        return await all_user(update, ctx, page=new_page)

    if d.startswith("adm_manage_"):
        if uid not in ADMIN_IDS:
            return
        parts = d.split("_")
        target_id = int(parts[2])
        current_page = int(parts[3]) if len(parts) > 3 else 0
        res = query("SELECT balance, refs, bank, stk, name, last_checkin, total_bet FROM users WHERE user_id=%s", (target_id,))
        if not res:
            return await q.answer("Không tìm thấy user!")
        u = res[0]
        status_text = f'{ce("🚫")} ĐANG CHẶN' if is_banned(target_id) else f'{ce("✅")} HOẠT ĐỘNG'
        msg = f'{ce("👥")} <b>USER:</b> <code>{target_id}</code>\n{ce("💰")} <code>{fmt_money(u[0])}đ</code>\n{ce("📊")} Tổng cược: <code>{fmt_money(u[6])}đ</code>\n🚦 {status_text}'
        kb = [[InlineKeyboardButton("🚫 BAN", callback_data=f"adm_act_ban_{target_id}_{current_page}"),
               InlineKeyboardButton("✅ UNBAN", callback_data=f"adm_act_unban_{target_id}_{current_page}")],
              [InlineKeyboardButton("🔙 QUAY LẠI", callback_data=f"adm_page_{current_page}")]]
        return await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    if d.startswith("adm_act_"):
        if uid not in ADMIN_IDS:
            return
        parts = d.split("_")
        act = parts[2]
        tid = int(parts[3])
        if act == "ban":
            query("INSERT INTO banned VALUES(%s) ON CONFLICT (user_id) DO NOTHING", (tid,))
        elif act == "unban":
            query("DELETE FROM banned WHERE user_id=%s", (tid,))
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

    if d.startswith("ok_") or d.startswith("no_"):
        if uid not in ADMIN_IDS:
            return
        act, u_id, amt = d.split("_")
        u_id, amt = int(u_id), int(amt)
        if act == "ok":
            query("UPDATE withdraw_history SET status='success', admin_id=%s WHERE user_id=%s AND amount=%s AND status='pending'", (uid, u_id, amt))
            try:
                await ctx.bot.send_message(chat_idền=LOG_GROUP_ID,
                    text=f đ'{ce("📤")} <b>ãRÚT TIỀN</ hob>\n{ce("àn👥")} <code>{u_id}</code>\ lạin{ce("💰")} <code>{fmt_money(amt)}đ</code>\n{ce("✅")} Đã duyệt!',
                    parse_mode=ParseMode.HTML)
            except:
                pass
            await ctx.bot.send_message(u_id,
                f'{ce("✅")} Yêu cầu rút <code>{fmt_money(amt)}đ</code> đã được duyệt!',
                parse_mode=ParseMode.HTML)
            await q.edit_message_text(f'{ce("✅")} ĐÃ DUYỆT ID {u_id}', parse_mode=ParseMode.HTML)
        else:
            query("UPDATE withdraw_history SET status='rejected', admin_id=%s, admin_note='Từ chối' WHERE user_id=%s AND amount=%s AND status='pending'", (uid, u_id, amt))
            add_money(u_id, amt, "Hoàn tiền rút")
            await ctx.bot.send_message(u_id,
                f'{ce("❌")} Yêu cầu rút bị từ chối. Ti.',
                parse_mode=ParseMode.HTML)
            await q.edit_message_text(f'{ce("❌")} TỪ CHỐI ID {u_id}', parse_mode=ParseMode.HTML)
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
application.add_handler(CommandHandler("lh", lh_cmd))
application.add_handler(CommandHandler("mp", mp_cmd))
application.add_handler(CommandHandler("bcr", baccarat_cmd))
application.add_handler(CommandHandler("xd4", xd4_cmd))
application.add_handler(CommandHandler("txmd5", txmd5_cmd))
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
application.add_handler(CommandHandler("tilewin", tilewin_cmd))
application.add_handler(CommandHandler("resetsdall", resetsdall_cmd))
application.add_handler(CommandHandler("xoalsall", xoalsall_cmd))
application.add_handler(CommandHandler("xoals", xoals_user_cmd))
application.add_handler(CommandHandler("setname", set_bot_name_cmd))
application.add_handler(CommandHandler("sethu", sethu_cmd))
application.add_handler(CommandHandler("taocode", tao_code))
application.add_handler(CommandHandler("taocodeall", taocodeall_cmd))
application.add_handler(CommandHandler("xoacode", xoacode_cmd))
application.add_handler(CommandHandler("kmnap", kmnap_cmd))
application.add_handler(CommandHandler("kmnapvc", kmnapvc_cmd))
application.add_handler(CommandHandler("checkprogressadmin", admin_check_bet_progress_cmd))
application.add_handler(CommandHandler("baotri", baotri_cmd))
application.add_handler(CommandHandler("baotriht", baotri_he_thong_cmd))
application.add_handler(CommandHandler("baotriall", baotri_hethong_cmd))
application.add_handler(CommandHandler("baotritc", baotri_tong_cong_cmd))
application.add_handler(CommandHandler("tatroom", tatroom_cmd))

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
