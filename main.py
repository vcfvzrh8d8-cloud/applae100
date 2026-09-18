import asyncio
import csv
from datetime import datetime, timedelta
from io import BytesIO
import os
import random
import matplotlib.pyplot as plt
import psycopg2
from psycopg2 import extras
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ===== MÚI GIỜ VIỆT NAM =====
VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')


def get_vietnam_time():
  return datetime.now(VIETNAM_TZ)


def get_vietnam_date():
  return get_vietnam_time().strftime('%d/%m/%Y')


def get_vietnam_datetime_db():
  return get_vietnam_time().strftime('%H:%M - %d/%m/%Y')


# ===== GROUP DICE GAME MODULE =====
group_games = {}
room_betting_enabled = {}

DEFAULT_BET_AMOUNTS = [1000, 5000, 10000, 50000, 100000, 500000]
DEFAULT_CYCLE_TIME = 60
DEFAULT_REMINDER_INTERVALS = [60, 40, 20, 10, 5, 4, 3, 2, 1]

# ===== BIẾN TOÀN CỤC =====
_bot_instance = None


# ===== HÀM KIỂM TRA BẢO TRÌ =====
def is_system_maintenance():
  res = query("SELECT value FROM settings WHERE key='system_maintenance'")
  return res[0][0] == '1' if res else False


def is_total_maintenance():
  res = query("SELECT value FROM settings WHERE key='mt_tongbao'")
  return res[0][0] == '1' if res else False


def is_admin_banned(admin_id):
  res = query('SELECT 1 FROM banned_admins WHERE admin_id=%s', (admin_id,))
  return len(res) > 0 if res else False


def is_admin_command_banned(admin_id, command):
  res = query(
      'SELECT 1 FROM banned_admin_commands WHERE admin_id=%s AND command=%s',
      (admin_id, command),
  )
  return len(res) > 0 if res else False


def check_bank_linked(user_id):
  res = query(
      'SELECT bank, stk, bank_linked FROM users WHERE user_id=%s', (user_id,)
  )
  if res and res[0][0] and res[0][1] and res[0][2] == 1:
    return True
  return False


def admin_only(func):

  async def wrapper(
      update: Update, ctx: ContextTypes.DEFAULT_TYPE, *args, **kwargs
  ):
    user_id = update.effective_user.id
    if is_system_maintenance() and user_id not in ADMIN_IDS:
      await update.message.reply_text(
          '🔧 **HỆ THỐNG ĐANG BẢO TRÌ**\n\nVui lòng quay lại sau ít phút!\nCảm'
          ' ơn bạn đã thông cảm.',
          parse_mode='Markdown',
      )
      return
    if user_id in ADMIN_IDS and is_admin_banned(user_id):
      await update.message.reply_text(
          '❌ Bạn đã bị cấm sử dụng các lệnh Admin!\nVui lòng liên hệ Admin cấp'
          ' cao hơn.',
          parse_mode='Markdown',
      )
      return
    if user_id not in ADMIN_IDS:
      await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
      return
    return await func(update, ctx, *args, **kwargs)

  return wrapper


# ===== VÒNG LẶP GAME XÚC XẮC NHÓM (6 XÚC XẮC) =====
async def run_dice_game_cycle(bot, group_id: int, chat_id: int):
  while True:
    try:
      if not room_betting_enabled.get(group_id, True):
        await asyncio.sleep(10)
        continue

      game_state = {
          'status': 'betting',
          'bets': {},  # Key: f"{user_id}_{choice}"
          'message_id': None,
          'cycle_start': datetime.now(),
      }
      group_games[group_id] = game_state

      start_msg = await bot.send_message(
          chat_id,
          f'🎲 **{get_bot_name()} - TÀI XỈU 6D** 🎲\n\n'
          f'⚡ **ĐẶT CƯỢC NGAY!**\n'
          f'⏱️ Thời gian còn lại: `60s`\n\n'
          f'🎯 **CÁCH CHƠI:**\n'
          f'• Tài (21-36 điểm): `t [số_tiền]`\n'
          f'• Xỉu (6-20 điểm): `x [số_tiền]`\n'
          f'• Chẵn (tổng điểm chẵn): `c [số_tiền]`\n'
          f'• Lẻ (tổng điểm lẻ): `l [số_tiền]`\n\n'
          f'🏆 **Tỉ lệ thưởng: x1.95**\n\n'
          f'📝 **Ví dụ:** `t 100000` | `c 50000`\n'
          f'💡 *Có thể đặt nhiều lần, tiền sẽ cộng dồn!*',
          parse_mode='Markdown',
      )
      game_state['message_id'] = start_msg.message_id

      current_second = 60
      REMINDER_SECONDS = [60, 40, 20, 10, 5, 3, 2, 1]

      while current_second > 0:
        await asyncio.sleep(1)
        current_second -= 1

        if current_second in REMINDER_SECONDS:
          tai_count = sum(
              b['amount']
              for b in game_state['bets'].values()
              if b['choice'] == 'tai'
          )
          xiu_count = sum(
              b['amount']
              for b in game_state['bets'].values()
              if b['choice'] == 'xiu'
          )
          chan_count = sum(
              b['amount']
              for b in game_state['bets'].values()
              if b['choice'] == 'chan'
          )
          le_count = sum(
              b['amount']
              for b in game_state['bets'].values()
              if b['choice'] == 'le'
          )
          total_players = len(
              set(b['user_id'] for b in game_state['bets'].values())
          )

          try:
            await bot.edit_message_text(
                f'🎲 **{get_bot_name()} - TÀI XỈU 6D** 🎲\n\n'
                f"{'⚠️ **SẮP ĐÓNG CƯỢC!**' if current_second < 10 else '⚡ **ĐẶT CƯỢC NGAY!**'}\n"
                f'⏱️ Thời gian còn lại: `{current_second}s`\n\n'
                f'💰 **THỐNG KÊ TIỀN CƯỢC:**\n'
                f'🎲 TÀI: `{tai_count:,}đ`\n'
                f'🎲 XỈU: `{xiu_count:,}đ`\n'
                f'🔴 CHẴN: `{chan_count:,}đ`\n'
                f'⚪ LẺ: `{le_count:,}đ`\n'
                f'━━━━━━━━━━━━━━━━━━━━━\n'
                f'👥 Tổng người chơi: `{total_players}`\n'
                f'📝 *Đặt thêm sẽ cộng dồn vào cửa cũ!*',
                chat_id=chat_id,
                message_id=game_state['message_id'],
                parse_mode='Markdown',
            )
          except:
            pass

      game_state['status'] = 'rolling'
      await bot.send_message(
          chat_id,
          '🔒 **ĐÃ ĐÓNG CƯỢC!**\n⏳ Đang lắc 6 xúc xắc...',
          parse_mode='Markdown',
      )

      d1 = await bot.send_dice(chat_id, emoji='🎲')
      d2 = await bot.send_dice(chat_id, emoji='🎲')
      d3 = await bot.send_dice(chat_id, emoji='🎲')
      d4 = await bot.send_dice(chat_id, emoji='🎲')
      d5 = await bot.send_dice(chat_id, emoji='🎲')
      d6 = await bot.send_dice(chat_id, emoji='🎲')

      await asyncio.sleep(5)

      v1, v2, v3, v4, v5, v6 = (
          d1.dice.value,
          d2.dice.value,
          d3.dice.value,
          d4.dice.value,
          d5.dice.value,
          d6.dice.value,
      )
      total = v1 + v2 + v3 + v4 + v5 + v6
      res_tx = 'tai' if total >= 21 else 'xiu'
      res_cl = 'chan' if total % 2 == 0 else 'le'

      total_win = 0
      total_lose = 0
      win_list = []
      lose_list = []

      for bet_key, bet in game_state['bets'].items():
        uid = bet['user_id']
        amt = bet['amount']
        choice = bet['choice']
        u_name = bet.get('username', f'ID {uid}')

        is_win = (
            (choice == 'tai' and res_tx == 'tai')
            or (choice == 'xiu' and res_tx == 'xiu')
            or (choice == 'chan' and res_cl == 'chan')
            or (choice == 'le' and res_cl == 'le')
        )

        if is_win:
          win_amt = int(amt * 1.95)
          add_money(uid, win_amt, f'Thắng Tài Xỉu {choice.upper()}')
          total_win += win_amt
          win_list.append(f'✅ {u_name}: {choice.upper()} +`{win_amt:,}đ`')
        else:
          total_lose += amt
          lose_list.append(f'❌ {u_name}: {choice.upper()} -`{amt:,}đ`')

      final_msg = (
          f'🎲 **KẾT QUẢ PHIÊN (6 XÚC XẮC)** 🎲\n'
          f'━━━━━━━━━━━━━━━━━━━━━\n'
          f'✨ Kết quả: **{v1} - {v2} - {v3} - {v4} - {v5} - {v6}** (Tổng:'
          f' `{total}`)\n'
          f'🏆 Cửa thắng: **{res_tx.upper()} - {res_cl.upper()}**\n'
          f'━━━━━━━━━━━━━━━━━━━━━\n'
          f'📈 **DANH SÁCH THẮNG:**\n'
          + (('\n'.join(win_list)) if win_list else '  (Không có)')
          + '\n\n'
          f'📉 **DANH SÁCH THUA:**\n'
          + (('\n'.join(lose_list)) if lose_list else '  (Không có)')
          + '\n'
          f'━━━━━━━━━━━━━━━━━━━━━\n'
          f'💰 **TỔNG THẮNG:** `+{total_win:,}đ`\n'
          f'💀 **TỔNG THUA:** `-{total_lose:,}đ`\n'
          f'━━━━━━━━━━━━━━━━━━━━━\n'
          f'🔓 **MỞ KHÓA CHAT!** Ván mới bắt đầu sau 10s.'
      )

      await bot.send_message(chat_id, final_msg, parse_mode='Markdown')

      group_games.pop(group_id, None)
      await asyncio.sleep(10)

    except Exception as e:
      print(f'Lỗi run_dice_game_cycle: {e}')
      await asyncio.sleep(5)


# ===== HÀM ĐẶT CƯỢC NHÓM (CỘNG DỒN) =====
async def place_bet_in_group(
    bot,
    user_id: int,
    group_id: int,
    choice: str,
    amount: int,
    username: str = '',
):
  if not check_bank_linked(user_id):
    return (
        False,
        '❌ **BẮT BUỘC LIÊN KẾT NGÂN HÀNG!**\n\nBạn cần liên kết tài khoản ngân'
        ' hàng để tham gia cá cược.\n👉 Dùng lệnh: `/lienket [Ngân_hàng] [STK]'
        ' [Tên]`',
    )

  if not room_betting_enabled.get(group_id, True):
    return (
        False,
        '🔴 **PHÒNG ĐÃ BỊ KHÓA CƯỢC!**\n\nAdmin đã tắt tính năng đặt cược trong'
        ' nhóm này.\nVui lòng chờ Admin bật lại để tiếp tục chơi!',
    )

  game = group_games.get(group_id)
  if not game or game['status'] != 'betting':
    return (
        False,
        '❌ Hiện tại không có phiên cược nào đang mở! Vui lòng chờ ván tiếp'
        ' theo.',
    )

  balance = get_balance(user_id)
  if balance < amount:
    return (
        False,
        f'❌ Số dư không đủ! Bạn cần `{amount:,}đ` nhưng chỉ có'
        f' `{balance:,}đ`.',
    )

  note = f'Cược {choice.upper()} nhóm - {amount:,}đ'
  if not sub_money(user_id, amount, note):
    return False, '❌ Có lỗi xảy ra khi trừ tiền, vui lòng thử lại!'

  # ===== CỘNG DỒN CƯỢC THEO TỪNG CỬA =====
  bet_key = f'{user_id}_{choice}'

  if bet_key in game['bets']:
    old_amount = game['bets'][bet_key]['amount']
    game['bets'][bet_key]['amount'] = old_amount + amount
    total_bet = game['bets'][bet_key]['amount']
    return True, (
        f'✅ **CỘNG DỒN CƯỢC THÀNH CÔNG!**\n'
        f'🎲 Cửa: `{choice.upper()}`\n'
        f'💰 Cược thêm: `{amount:,}đ`\n'
        f'📊 Tổng cược cửa này: `{total_bet:,}đ`'
    )
  else:
    game['bets'][bet_key] = {
        'user_id': user_id,
        'amount': amount,
        'choice': choice,
        'username': username,
    }
    return True, (
        f'✅ **ĐẶT CƯỢC THÀNH CÔNG!**\n'
        f'🎲 Cửa: `{choice.upper()}`\n'
        f'💰 Số tiền: `{amount:,}đ`'
    )


def get_group_game_status(group_id: int):
  game = group_games.get(group_id)
  if not game:
    return None
  return game['status']


def gen_code():
  return ''.join(
      random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8)
  )


# ===== CONFIG =====
TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

ADMIN_IDS = [5633649201, 7857144049]
BOT_USERNAME = 'zen88uytins1bot'
MIN_WITHDRAW = 50000
LOG_GROUP_ID = -1003663678808

BANK_ID = 'MB'
ACCOUNT_NO = '0003456712345'
ACCOUNT_NAME = 'LY THI CHAM'


def get_deposit_info(user_id):
  qr_url = f'https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-qr_only.png?amount=0&addInfo={user_id}&accountName={ACCOUNT_NAME}'
  caption = (
      '**🏦 THÔNG TIN NẠP TIỀN**\n\n'
      f'🏦 Ngân hàng: **MBBANK**\n'
      f'👤 CTK: **{ACCOUNT_NAME}**\n'
      f'💳 STK: `{ACCOUNT_NO}`\n'
      f'📝 Nội dung: `{user_id}`\n\n'
      '⚠️ *Lưu ý: Quét mã QR để tự động điền nội dung. Hệ thống cộng tiền sau'
      ' 1-3 phút.*'
  )
  return qr_url, caption


# ===== DATABASE SETUP =====
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
    print(f'Database Error: {e}')
    conn.rollback()
  finally:
    cur.close()
    conn.close()
  return res


# ===== KHỞI TẠO CÁC BẢNG =====
query(
    'CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, reward INTEGER,'
    ' uses INTEGER)'
)
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

query(
    'CREATE TABLE IF NOT EXISTS game_rates (id INTEGER PRIMARY KEY, name TEXT,'
    ' rate INTEGER)'
)
query(
    'CREATE TABLE IF NOT EXISTS banned_games (user_id BIGINT, game_id INTEGER,'
    ' PRIMARY KEY (user_id, game_id))'
)
query(
    'CREATE TABLE IF NOT EXISTS banned_features (user_id BIGINT, feature TEXT,'
    ' PRIMARY KEY (user_id, feature))'
)
query(
    'CREATE TABLE IF NOT EXISTS banned_admins (admin_id BIGINT PRIMARY KEY,'
    ' banned_by BIGINT, reason TEXT, banned_at TEXT)'
)
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

# Bảng lưu code tân thủ
query("""
CREATE TABLE IF NOT EXISTS tanthu_code (
    user_id BIGINT PRIMARY KEY,
    code TEXT,
    received_at TEXT,
    used INTEGER DEFAULT 0
)
""")

default_game_names = [
    'TÀI XỈU',
    'XÓC ĐĨA',
    'ĐUA XE',
    'DÒ MÌN',
    'PENALTY',
    'GÕ MÕ',
    'QUAY SỐ',
    'BẦU CUA',
    'XỔ SỐ',
    'VÒNG QUAY MAY MẮN',
    'CAO THẤP',
    'RÚT GỖ',
    'TÔ MÀU',
]

for i, name in enumerate(default_game_names, 1):
  res = query('SELECT 1 FROM game_rates WHERE id=%s', (i,))
  if not res:
    query('INSERT INTO game_rates VALUES(%s, %s, 10)', (i, name))
  else:
    query('UPDATE game_rates SET name=%s WHERE id=%s', (name, i))

try:
  query('ALTER TABLE users ADD COLUMN IF NOT EXISTS total_bet BIGINT DEFAULT 0')
except:
  pass
try:
  query(
      'ALTER TABLE users ADD COLUMN IF NOT EXISTS rate_bonus INTEGER DEFAULT'
      ' NULL'
  )
except:
  pass
try:
  query(
      'ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_linked INTEGER DEFAULT 0'
  )
except:
  pass

query(
    'CREATE TABLE IF NOT EXISTS history (user_id BIGINT, amount BIGINT, note'
    ' TEXT, time TEXT)'
)
query('CREATE TABLE IF NOT EXISTS banned (user_id BIGINT PRIMARY KEY)')
query('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')

maintenance_keys = [
    'mt_taixiu',
    'mt_duaxe',
    'mt_domin',
    'mt_penalty',
    'mt_gomo',
    'mt_nap',
    'mt_rut',
    'mt_xocdia',
    'mt_quayso',
    'mt_baucua',
    'mt_xoso',
    'mt_vongquay',
    'mt_caothap',
    'mt_rutgo',
    'mt_tomau',
]
for k in maintenance_keys:
  res = query('SELECT 1 FROM settings WHERE key=%s', (k,))
  if not res:
    query("INSERT INTO settings VALUES(%s, '0')", (k,))

res_name = query("SELECT 1 FROM settings WHERE key='bot_display_name'")
if not res_name:
  query(
      "INSERT INTO settings(key, value) VALUES('bot_display_name', 'Hệ thống"
      " Game Uy Tín')"
  )

res_system_mt = query("SELECT 1 FROM settings WHERE key='system_maintenance'")
if not res_system_mt:
  query("INSERT INTO settings VALUES('system_maintenance', '0')")

res_tongbao = query("SELECT 1 FROM settings WHERE key='mt_tongbao'")
if not res_tongbao:
  query("INSERT INTO settings VALUES('mt_tongbao', '0')")


# ===== HÀM KIỂM SOÁT TỈ LỆ =====
def get_rate_by_id(game_id, user_id=None):
  if user_id:
    res_user = query(
        'SELECT rate_bonus FROM users WHERE user_id=%s', (user_id,)
    )
    if res_user and res_user[0][0] is not None:
      return res_user[0][0]
  res = query('SELECT rate FROM game_rates WHERE id=%s', (game_id,))
  return res[0][0] if res else 10


def check_win_by_id(game_id, user_id=None):
  rate = get_rate_by_id(game_id, user_id)
  if rate >= 100:
    return True
  if rate <= 0:
    return False
  return random.randint(1, 100) <= rate


def check_mt(key):
  res = query('SELECT value FROM settings WHERE key=%s', (key,))
  if res:
    return res[0][0] == '1'
  query(
      "INSERT INTO settings (key, value) VALUES (%s, '0') ON CONFLICT (key) DO"
      ' NOTHING',
      (key,),
  )
  return False


def get_bot_name():
  res = query("SELECT value FROM settings WHERE key='bot_display_name'")
  return res[0][0] if res else 'Hệ thống Game Uy Tín'


def is_game_banned(uid, gid):
  res = query(
      'SELECT 1 FROM banned_games WHERE user_id=%s AND game_id=%s', (uid, gid)
  )
  return len(res) > 0 if res else False


def is_feature_banned(uid, feature):
  res = query(
      'SELECT 1 FROM banned_features WHERE user_id=%s AND feature=%s',
      (uid, feature),
  )
  return len(res) > 0 if res else False


def get_vip_info(total_bet):
  if total_bet >= 50000000:
    return 'VIP 5 (Kim Cương)', 5000
  if total_bet >= 20000000:
    return 'VIP 4 (Vàng)', 3000
  if total_bet >= 10000000:
    return 'VIP 3 (Bạc)', 1500
  if total_bet >= 5000000:
    return 'VIP 2 (Đồng)', 800
  if total_bet >= 1000000:
    return 'VIP 1', 500
  return 'Thành viên', 300


def get_next_multiplier(current_mult):
  if current_mult < 1.05:
    return 1.05
  elif current_mult < 1.10:
    return 1.10
  elif current_mult < 2.0:
    return round(current_mult + 0.10, 2)
  else:
    return round(current_mult + 0.20, 2)


def get_user(uid):
  res = query('SELECT 1 FROM users WHERE user_id=%s', (uid,))
  if not res:
    query('INSERT INTO users(user_id) VALUES(%s)', (uid,))


def get_balance(uid):
  get_user(uid)
  res = query('SELECT balance FROM users WHERE user_id=%s', (uid,))
  return res[0][0] if res else 0


def is_banned(uid):
  res = query('SELECT 1 FROM banned WHERE user_id=%s', (uid,))
  return len(res) > 0 if res else False


def add_money(uid, amt, note):
  get_user(uid)
  now_str = get_vietnam_datetime_db()
  query('UPDATE users SET balance=balance+%s WHERE user_id=%s', (amt, uid))
  query('INSERT INTO history VALUES(%s,%s,%s,%s)', (uid, amt, note, now_str))


def sub_money(uid, amt, note='withdraw'):
  get_user(uid)
  bal = get_balance(uid)
  if bal < amt:
    return False
  now_str = get_vietnam_datetime_db()
  query('UPDATE users SET balance=balance-%s WHERE user_id=%s', (amt, uid))
  query('INSERT INTO history VALUES(%s,%s,%s,%s)', (uid, -amt, note, now_str))
  if (
      note != 'Rút tiền'
      and note != 'withdraw'
      and 'Admin' not in note
      and 'Chuyển tiền' not in note
  ):
    query('UPDATE users SET total_bet=total_bet+%s WHERE user_id=%s', (amt, uid))
    update_bet_progress(uid, amt, _bot_instance)
  return True


def check_bet_requirement(user_id, bet_amount=0):
  bonus_data = query(
      'SELECT required_bet, current_bet FROM user_bonus WHERE user_id=%s',
      (user_id,),
  )
  if not bonus_data or bonus_data[0][0] == 0:
    return True, 0
  required_bet, current_bet = bonus_data[0]
  if bet_amount > 0:
    new_bet = current_bet + bet_amount
    query(
        'UPDATE user_bonus SET current_bet=%s WHERE user_id=%s',
        (new_bet, user_id),
    )
    current_bet = new_bet
  if current_bet >= required_bet:
    return True, 0
  return False, required_bet - current_bet


def add_bonus_with_requirement(user_id, bonus_amount, required_multiplier=3):
  required_bet = bonus_amount * required_multiplier
  now_str = get_vietnam_datetime_db()
  query('DELETE FROM user_bonus WHERE user_id=%s', (user_id,))
  query(
      'INSERT INTO user_bonus (user_id, bonus_amount, required_bet,'
      ' current_bet, created_at) VALUES (%s, %s, %s, %s, %s)',
      (user_id, bonus_amount, required_bet, 0, now_str),
  )
  add_money(
      user_id,
      bonus_amount,
      f'Khuyến mãi nạp +{bonus_amount:,}đ (yêu cầu cược x{required_multiplier})',
  )

  if _bot_instance:
    asyncio.create_task(
        send_bonus_notification(user_id, bonus_amount, required_bet)
    )

  return required_bet


def get_remaining_bet_required(user_id):
  bonus_data = query(
      'SELECT required_bet, current_bet FROM user_bonus WHERE user_id=%s',
      (user_id,),
  )
  if not bonus_data or bonus_data[0][0] == 0:
    return 0
  required_bet, current_bet = bonus_data[0]
  return max(0, required_bet - current_bet)


async def send_bonus_notification(user_id, bonus_amount, required_bet):
  if _bot_instance:
    message = (
        f'🎁 **NHẬN KHUYẾN MÃI THÀNH CÔNG!** 🎁\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'💰 **Tiền thưởng:** `+{bonus_amount:,}đ`\n'
        f'🎯 **Yêu cầu cược:** `{required_bet:,}đ` (x3 vòng)\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'⚠️ **ĐIỀU KIỆN RÚT TIỀN:**\n'
        f'• Bạn cần cược đủ **{required_bet:,}đ** mới có thể rút tiền\n'
        f'• Mỗi lần cược sẽ được cập nhật tự động\n'
        f'• Dùng lệnh `/checkprogress` để xem tiến độ\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'🎮 **Chúc bạn may mắn và hoàn thành sớm!**'
    )
    try:
      await _bot_instance.send_message(user_id, message, parse_mode='Markdown')
    except:
      pass


async def check_and_notify_bet_completion(
    user_id: int, current_bet: int, required_bet: int
):
  if current_bet >= required_bet:
    bonus_data = query(
        'SELECT bonus_amount, required_bet, current_bet FROM user_bonus WHERE'
        ' user_id=%s',
        (user_id,),
    )
    if bonus_data:
      bonus_amount, req_bet, curr_bet = bonus_data[0]

      message = (
          f'🎉 **CHÚC MỪNG! BẠN ĐÃ HOÀN THÀNH YÊU CẦU CƯỢC!** 🎉\n'
          f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
          f'💰 **Tiền khuyến mãi đã nhận:** `+{bonus_amount:,}đ`\n'
          f'🎯 **Yêu cầu cược:** `{req_bet:,}đ` (x3 vòng)\n'
          f'✅ **Tổng cược đã thực hiện:** `{curr_bet:,}đ`\n'
          f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
          f'🔓 **Bạn đã có thể rút tiền bình thường!**\n\n'
          f'💪 Cảm ơn bạn đã tin tưởng và sử dụng dịch vụ!\n'
          f'🎮 Chúc bạn tiếp tục may mắn!'
      )
      try:
        if _bot_instance:
          await _bot_instance.send_message(
              user_id, message, parse_mode='Markdown'
          )

          log_message = (
              f'✅ **HOÀN THÀNH YÊU CẦU CƯỢC**\n'
              f'👤 **User ID:** `{user_id}`\n'
              f'💰 **Tiền KM:** `+{bonus_amount:,}đ`\n'
              f'🎯 **Yêu cầu:** `{req_bet:,}đ`\n'
              f'✅ **Đã cược:** `{curr_bet:,}đ`\n'
              f'⏰ **Hoàn thành lúc:** {get_vietnam_datetime_db()}'
          )
          for admin_id in ADMIN_IDS:
            try:
              await _bot_instance.send_message(
                  admin_id, log_message, parse_mode='Markdown'
              )
            except:
              pass
      except:
        pass

      query('DELETE FROM user_bonus WHERE user_id=%s', (user_id,))
      return True
  return False


def update_bet_progress(user_id: int, bet_amount: int, bot=None):
  bonus_data = query(
      'SELECT required_bet, current_bet FROM user_bonus WHERE user_id=%s',
      (user_id,),
  )
  if not bonus_data or bonus_data[0][0] == 0:
    return False

  required_bet, current_bet = bonus_data[0]
  new_bet = current_bet + bet_amount
  query(
      'UPDATE user_bonus SET current_bet=%s WHERE user_id=%s', (new_bet, user_id)
  )

  if new_bet >= required_bet:
    asyncio.create_task(
        check_and_notify_bet_completion(user_id, new_bet, required_bet)
    )
    return True
  return False


def get_bet_progress_status(user_id: int):
  bonus_data = query(
      'SELECT bonus_amount, required_bet, current_bet FROM user_bonus WHERE'
      ' user_id=%s',
      (user_id,),
  )
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
      'is_completed': current_bet >= required_bet,
  }


# ===== TƯƠNG TÁC NHÓM =====
async def track_interaction(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  if update.effective_chat.type == 'private':
    return
  uid = update.effective_user.id
  gid = update.effective_chat.id
  today = get_vietnam_date()
  now_str = get_vietnam_datetime_db()

  query(
      """
        INSERT INTO group_interactions (user_id, group_id, interaction_count, last_interaction)
        VALUES (%s, %s, 1, %s)
        ON CONFLICT (user_id, group_id) DO UPDATE SET 
            interaction_count = group_interactions.interaction_count + 1,
            last_interaction = %s
    """,
      (uid, gid, now_str, now_str),
  )

  query(
      """
        INSERT INTO daily_top_interactions (user_id, group_id, interaction_count, date)
        VALUES (%s, %s, 1, %s)
        ON CONFLICT (user_id, group_id, date) DO UPDATE SET 
            interaction_count = daily_top_interactions.interaction_count + 1
    """,
      (uid, gid, today),
  )

  total = query(
      'SELECT interaction_count FROM group_interactions WHERE user_id=%s AND'
      ' group_id=%s',
      (uid, gid),
  )
  if total and total[0][0] >= 200:
    rewarded = query(
        'SELECT 1 FROM daily_top_interactions WHERE user_id=%s AND group_id=%s'
        ' AND rewarded=1 AND interaction_count>=200',
        (uid, gid),
    )
    if not rewarded:
      query(
          'UPDATE group_interactions SET interaction_count = -200 WHERE'
          ' user_id=%s AND group_id=%s',
          (uid, gid),
      )
      await ctx.bot.send_message(
          uid,
          '🎉 **CHÚC MỪNG!** 🎉\n━━━━━━━━━━━━━━━━━━━━━\n🔥 Bạn đã đạt **200 lượt tương'
          ' tác** trong nhóm!\n📞 Hãy liên hệ Admin để nhận thưởng hấp'
          ' dẫn!\n━━━━━━━━━━━━━━━━━━━━━\n📞 **CSKH1:** @sakuri0\n📞 **CSKH2:**'
          ' @echcutodz',
          parse_mode='Markdown',
      )
      query(
          'UPDATE daily_top_interactions SET rewarded=1 WHERE user_id=%s AND'
          ' group_id=%s',
          (uid, gid),
      )


async def send_interaction_reward(ctx: ContextTypes.DEFAULT_TYPE):
  today = get_vietnam_date()
  for gid in GROUP_IDS:
    try:
      top_users = query(
          """
                SELECT user_id, interaction_count 
                FROM daily_top_interactions 
                WHERE group_id=%s AND date=%s AND rewarded=0
                ORDER BY interaction_count DESC 
                LIMIT 5
            """,
          (gid, today),
      )
      if not top_users or len(top_users) < 5:
        continue
      rewards = {1: 22000, 2: 11000, 3: 5000, 4: 5000, 5: 5000}
      codes = []
      for i, (uid, count) in enumerate(top_users[:5], 1):
        if i <= 5:
          code = gen_code()
          reward = rewards.get(i, 5000)
          query(
              'INSERT INTO codes (code, reward, uses) VALUES(%s, %s, %s)',
              (code, reward, 1),
          )
          codes.append(f'Top {i} (ID {uid}): `{code}` - {reward:,}đ')
          query(
              'UPDATE daily_top_interactions SET rank=%s, reward_amount=%s,'
              ' rewarded=1 WHERE user_id=%s AND group_id=%s AND date=%s',
              (i, reward, uid, gid, today),
          )
      if codes:
        msg = (
            '🎁 **CODE TƯƠNG TÁC NHÓM** 🎁\n━━━━━━━━━━━━━━━━━━━━━\n'
            + '\n'.join(codes)
            + f'\n━━━━━━━━━━━━━━━━━━━━━\n📅 Ngày: {today}\n📌 Dùng lệnh `/code'
            ' [mã]` để nhận thưởng!'
        )
        await ctx.bot.send_message(gid, msg, parse_mode='Markdown')
    except Exception as e:
      print(f'Lỗi gửi code tương tác nhóm {gid}: {e}')


# ===== ADMIN COMMANDS =====
@admin_only
async def dashboard_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  today = get_vietnam_date()
  this_month = get_vietnam_time().strftime('/%m/%Y')

  nap_today = (
      query(
          "SELECT SUM(amount) FROM history WHERE amount > 0 AND note ILIKE"
          " '%nạp%' AND time LIKE %s",
          (f'%{today}%',),
      )[0][0]
      or 0
  )
  rut_today = (
      query(
          "SELECT SUM(amount) FROM history WHERE amount < 0 AND note ILIKE"
          " '%Rút%' AND time LIKE %s",
          (f'%{today}%',),
      )[0][0]
      or 0
  )
  nap_month = (
      query(
          "SELECT SUM(amount) FROM history WHERE amount > 0 AND note ILIKE"
          " '%nạp%' AND time LIKE %s",
          (f'%{this_month}%',),
      )[0][0]
      or 0
  )
  rut_month = (
      query(
          "SELECT SUM(amount) FROM history WHERE amount < 0 AND note ILIKE"
          " '%Rút%' AND time LIKE %s",
          (f'%{this_month}%',),
      )[0][0]
      or 0
  )
  total_cuoc = (
      query(
          'SELECT SUM(amount) FROM history WHERE amount < 0 AND note NOT ILIKE'
          " '%Rút%' AND note NOT ILIKE '%trừ tiền%'"
      )[0][0]
      or 0
  )
  total_thang = (
      query(
          'SELECT SUM(amount) FROM history WHERE amount > 0 AND note NOT ILIKE'
          " '%nạp%' AND note NOT ILIKE '%Code%' AND note NOT ILIKE '%Checkin%'"
      )[0][0]
      or 0
  )
  loi_nhuan = abs(total_cuoc) - total_thang

  msg = (
      f'📊 **BẢNG THỐNG KÊ DOANH THU**\n━━━━━━━━━━━━━━━━━━━━━\n'
      f'📅 **Hôm nay ({today}):**\n  📥 Tổng nạp: `+{nap_today:,}đ`\n  📤 Tổng'
      f' rút: `{rut_today:,}đ`\n\n'
      f'📅 **Tháng này ({get_vietnam_time().month}):**\n  📥 Tổng nạp:'
      f' `+{nap_month:,}đ`\n  📤 Tổng rút: `{rut_month:,}đ`\n\n'
      f'📈 **Tổng kết Game (All time):**\n  💰 Lợi nhuận ròng:'
      f' `{loi_nhuan:,}đ`\n━━━━━━━━━━━━━━━━━━━━━'
  )
  await update.message.reply_text(msg, parse_mode='Markdown')


async def bao_hiem_vip(context: ContextTypes.DEFAULT_TYPE):
  yesterday = (get_vietnam_time() - timedelta(days=1)).strftime('%d/%m/%Y')
  users = query(
      'SELECT user_id, SUM(amount) FROM history WHERE time LIKE %s GROUP BY'
      ' user_id',
      (f'%{yesterday}%',),
  )
  for u_id, total in users:
    if total < -1000000:
      res = query('SELECT total_bet FROM users WHERE user_id=%s', (u_id,))
      total_bet = res[0][0] if res else 0
      vip_name, _ = get_vip_info(total_bet)
      if 'VIP' in vip_name:
        percent = 2 if 'VIP 1' in vip_name else 5
        hoan_tien = int(abs(total) * (percent / 100))
        add_money(u_id, hoan_tien, f'Bảo hiểm VIP {yesterday}')
        try:
          await context.bot.send_message(
              u_id,
              f'🛡 **BẢO HIỂM VIP**\n\nHôm qua bạn đã chưa may mắn. Hệ thống'
              f' hoàn lại `{percent}%` tiền thua cược: `+{hoan_tien:,}đ`.',
          )
        except:
          pass


@admin_only
async def tong_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  t_nap = (
      query(
          "SELECT SUM(amount) FROM history WHERE amount > 0 AND note ILIKE"
          " '%nạp%'"
      )[0][0]
      or 0
  )
  t_rut = (
      query(
          "SELECT SUM(amount) FROM history WHERE amount < 0 AND note ILIKE"
          " '%Rút%'"
      )[0][0]
      or 0
  )
  t_cuoc = (
      query(
          'SELECT SUM(amount) FROM history WHERE amount < 0 AND note NOT ILIKE'
          " '%Rút%' AND note NOT ILIKE '%trừ tiền%'"
      )[0][0]
      or 0
  )
  t_thang = (
      query(
          'SELECT SUM(amount) FROM history WHERE amount > 0 AND note NOT ILIKE'
          " '%nạp%' AND note NOT ILIKE '%Code%' AND note NOT ILIKE '%Checkin%'"
      )[0][0]
      or 0
  )
  loi_nhuan = abs(t_cuoc) - t_thang
  msg = (
      f'📈 **TỔNG QUAN TÀI CHÍNH HỆ THỐNG**\n'
      f'━━━━━━━━━━━━━━━━━━━━━\n'
      f'📥 **Tổng Nạp:** `+{t_nap:,}đ`\n'
      f'📤 **Tổng Rút:** `{t_rut:,}đ`\n'
      f'💰 **Lợi Nhuận Thực Tế (Game):** `{loi_nhuan:,}đ`\n'
      f'━━━━━━━━━━━━━━━━━━━━━'
  )
  await update.message.reply_text(msg, parse_mode='Markdown')


@admin_only
async def cam_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  if len(ctx.args) < 2:
    return await update.message.reply_text(
        '❌ Cú pháp: `/cam [id] [game_id/nap/rut]`'
    )
  uid, target = int(ctx.args[0]), ctx.args[1]
  if target.isdigit():
    query(
        'INSERT INTO banned_games VALUES(%s, %s) ON CONFLICT DO NOTHING',
        (uid, int(target)),
    )
    await update.message.reply_text(
        f'🚫 Đã cấm ID `{uid}` chơi game ID `{target}`'
    )
  elif target in ['nap', 'rut']:
    query(
        'INSERT INTO banned_features VALUES(%s, %s) ON CONFLICT DO NOTHING',
        (uid, target),
    )
    await update.message.reply_text(
        f'🚫 Đã cấm ID `{uid}` sử dụng tính năng `{target}`'
    )


@admin_only
async def bocam_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  if len(ctx.args) < 2:
    return await update.message.reply_text(
        '❌ Cú pháp: `/bocam [id] [game_id/nap/rut]`'
    )
  uid, target = int(ctx.args[0]), ctx.args[1]
  if target.isdigit():
    query(
        'DELETE FROM banned_games WHERE user_id=%s AND game_id=%s',
        (uid, int(target)),
    )
    await update.message.reply_text(
        f'✅ Đã gỡ cấm game ID `{target}` cho ID `{uid}`'
    )
  elif target in ['nap', 'rut']:
    query(
        'DELETE FROM banned_features WHERE user_id=%s AND feature=%s',
        (uid, target),
    )
    await update.message.reply_text(
        f'✅ Đã gỡ cấm tính năng `{target}` cho ID `{uid}`'
    )


async def give_money_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  uid = update.effective_user.id
  if is_banned(uid):
    return
  if len(ctx.args) < 2:
    return await update.message.reply_text(
        '❌ Cú pháp: `/give [ID_Người_Nhận] [Số_Tiền]`'
    )
  try:
    target_id = int(ctx.args[0])
    amount = int(ctx.args[1])
    if amount < 10000:
      return await update.message.reply_text(
          '❌ Số tiền chuyển tối thiểu là 10.000đ'
      )
    if sub_money(uid, amount, f'Chuyển tiền tới {target_id}'):
      add_money(target_id, amount, f'Nhận tiền từ {uid}')
      await update.message.reply_text(
          f'✅ Đã chuyển thành công `{amount:,}đ` tới ID `{target_id}`'
      )
      try:
        await ctx.bot.send_message(
            target_id, f'🔔 Bạn nhận được `{amount:,}đ` từ ID `{uid}`'
        )
      except:
        pass
    else:
      await update.message.reply_text('❌ Số dư của bạn không đủ.')
  except:
    await update.message.reply_text('❌ Lỗi định dạng dữ liệu.')


@admin_only
async def set_bot_name_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  if not ctx.args:
    return await update.message.reply_text('❌ Cú pháp: `/setname [Tên mới]`')
  new_name = ' '.join(ctx.args)
  query(
      "UPDATE settings SET value=%s WHERE key='bot_display_name'", (new_name,)
  )
  await update.message.reply_text(
      f'✅ Đã đổi tên hiển thị của Bot thành: **{new_name}**', parse_mode='Markdown'
  )


@admin_only
async def resetsdall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  query('UPDATE users SET balance = 0')
  await update.message.reply_text(
      '✅ Đã xóa toàn bộ số dư của tất cả người dùng về 0!'
  )


@admin_only
async def tileall_set_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  if not ctx.args:
    return await update.message.reply_text('❌ Cú pháp: `/tileall [số]`')
  try:
    new_rate = int(ctx.args[0])
    query('UPDATE game_rates SET rate = %s', (new_rate,))
    await update.message.reply_text(
        f'✅ Đã chỉnh tất cả game về tỉ lệ thắng: `{new_rate}%`',
        parse_mode='Markdown',
    )
  except:
    await update.message.reply_text('❌ Tỉ lệ phải là số nguyên.')


@admin_only
async def tile1_user_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  if len(ctx.args) < 2:
    return await update.message.reply_text(
        '❌ Cú pháp: `/tile1 [ID] [Tỉ_lệ]`\nVD: `/tile1 123456 10` (Chỉnh ID'
        ' 123456 thắng 10%)'
    )
  try:
    uid = int(ctx.args[0])
    rate = int(ctx.args[1])
    query('UPDATE users SET rate_bonus = %s WHERE user_id = %s', (rate, uid))
    await update.message.reply_text(
        f'✅ Đã áp dụng tỉ lệ thắng `{rate}%` riêng cho người dùng `{uid}`',
        parse_mode='Markdown',
    )
  except:
    await update.message.reply_text('❌ Lỗi dữ liệu nhập vào.')


@admin_only
async def soduall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  users = query(
      'SELECT user_id, balance FROM users WHERE balance > 0 ORDER BY balance'
      ' DESC'
  )
  if not users:
    return await update.message.reply_text(
        'Hiện không có ai có số dư lớn hơn 0.'
    )
  text = '💰 **DANH SÁCH SỐ DƯ TẤT CẢ ID:**\n'
  for u in users:
    text += f'ID: `{u[0]}` | Số dư: `{u[1]:,}đ`\n'
  if len(text) > 4000:
    for x in range(0, len(text), 4000):
      await update.message.reply_text(text[x : x + 4000], parse_mode='Markdown')
  else:
    await update.message.reply_text(text, parse_mode='Markdown')


@admin_only
async def xoalsall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  query('DELETE FROM history')
  await update.message.reply_text(
      '✅ Đã xoá toàn bộ lịch sử cược, nạp và rút của hệ thống!'
  )


@admin_only
async def xoals_user_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  if not ctx.args:
    return await update.message.reply_text('❌ Cú pháp: `/xoals [ID]`')
  try:
    uid = int(ctx.args[0])
    query('DELETE FROM history WHERE user_id=%s', (uid,))
    await update.message.reply_text(
        f'✅ Đã xoá sạch lịch sử của người dùng: `{uid}`', parse_mode='Markdown'
    )
  except:
    await update.message.reply_text('❌ ID không hợp lệ.')


async def cam_admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id != 8619503816:
    await update.message.reply_text(
        '❌ Chỉ Admin chính (ID: 8619503816) mới có quyền sử dụng lệnh này!'
    )
    return
  if len(ctx.args) < 1:
    await update.message.reply_text(
        '❌ Cú pháp: `/camadmin [ID_admin] [lý do]`', parse_mode='Markdown'
    )
    return
  try:
    target_admin = int(ctx.args[0])
    reason = ' '.join(ctx.args[1:]) if len(ctx.args) > 1 else 'Không có lý do'
    if target_admin == user_id:
      await update.message.reply_text('❌ Bạn không thể tự cấm chính mình!')
      return
    if target_admin not in ADMIN_IDS:
      await update.message.reply_text(
          f'❌ ID `{target_admin}` không phải là Admin của bot!',
          parse_mode='Markdown',
      )
      return
    now_str = get_vietnam_datetime_db()
    query(
        'INSERT INTO banned_admins VALUES(%s, %s, %s, %s) ON CONFLICT'
        ' (admin_id) DO UPDATE SET banned_by=%s, reason=%s, banned_at=%s',
        (target_admin, user_id, reason, now_str, user_id, reason, now_str),
    )
    await update.message.reply_text(
        f'✅ **ĐÃ CẤM ADMIN**\n\n👤 ID: `{target_admin}`\n📝 Lý do: {reason}\n⏰'
        f' Thời gian: {now_str}',
        parse_mode='Markdown',
    )
  except ValueError:
    await update.message.reply_text('❌ ID không hợp lệ!')


async def unban_admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id != 8619503816:
    await update.message.reply_text(
        '❌ Chỉ Admin chính (ID: 8619503816) mới có quyền sử dụng lệnh này!'
    )
    return
  if len(ctx.args) < 1:
    await update.message.reply_text(
        '❌ Cú pháp: `/unbanadmin [ID_admin]`', parse_mode='Markdown'
    )
    return
  try:
    target_admin = int(ctx.args[0])
    if not is_admin_banned(target_admin):
      await update.message.reply_text(
          f'❌ Admin `{target_admin}` không bị cấm!', parse_mode='Markdown'
      )
      return
    query('DELETE FROM banned_admins WHERE admin_id=%s', (target_admin,))
    await update.message.reply_text(
        f'✅ Đã gỡ cấm cho Admin `{target_admin}`', parse_mode='Markdown'
    )
  except ValueError:
    await update.message.reply_text('❌ ID không hợp lệ!')


async def list_banned_admins_cmd(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE
):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  banned_list = query(
      'SELECT admin_id, banned_by, reason, banned_at FROM banned_admins'
  )
  if not banned_list:
    await update.message.reply_text(
        '📋 Hiện không có Admin nào bị cấm.', parse_mode='Markdown'
    )
    return
  msg = '🚫 **DANH SÁCH ADMIN BỊ CẤM**\n━━━━━━━━━━━━━━━━━━━━━\n'
  for admin_id, banned_by, reason, banned_at in banned_list:
    msg += (
        f'\n👤 ID: `{admin_id}`\n👮 Bởi: `{banned_by}`\n📝 Lý do: {reason}\n⏰'
        f' Lúc: {banned_at}\n━━━━━━━━━━━━━━━━━━━━━\n'
    )
  await update.message.reply_text(msg, parse_mode='Markdown')


async def camadmin1_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id != 8619503816:
    await update.message.reply_text(
        '❌ Chỉ Admin chính (ID: 8619503816) mới có quyền sử dụng lệnh này!'
    )
    return
  if len(ctx.args) < 2:
    await update.message.reply_text(
        '❌ **Cú pháp:** `/camadmin1 [ID_admin] [tên_lệnh]`\n\n📝 **Ví dụ:**'
        ' `/camadmin1 5260138362 tile1`',
        parse_mode='Markdown',
    )
    return
  try:
    target_admin = int(ctx.args[0])
    banned_command = ctx.args[1].lower()
    if target_admin == user_id:
      await update.message.reply_text('❌ Bạn không thể tự cấm chính mình!')
      return
    if target_admin not in ADMIN_IDS:
      await update.message.reply_text(
          f'❌ ID `{target_admin}` không phải là Admin của bot!',
          parse_mode='Markdown',
      )
      return
    now_str = get_vietnam_datetime_db()
    reason = ' '.join(ctx.args[2:]) if len(ctx.args) > 2 else 'Không có lý do'
    query(
        'INSERT INTO banned_admin_commands VALUES(%s, %s, %s, %s, %s) ON'
        ' CONFLICT (admin_id, command) DO NOTHING',
        (target_admin, banned_command, user_id, reason, now_str),
    )
    await update.message.reply_text(
        f'✅ **ĐÃ CẤM LỆNH CHO ADMIN**\n\n👤 ID: `{target_admin}`\n🚫 Lệnh bị'
        f' cấm: `{banned_command}`\n📝 Lý do: {reason}',
        parse_mode='Markdown',
    )
  except ValueError:
    await update.message.reply_text('❌ ID không hợp lệ!')


async def uncamadmin1_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id != 8619503816:
    await update.message.reply_text(
        '❌ Chỉ Admin chính mới có quyền sử dụng lệnh này!'
    )
    return
  if len(ctx.args) < 2:
    await update.message.reply_text(
        '❌ Cú pháp: `/uncamadmin1 [ID_admin] [tên_lệnh]`',
        parse_mode='Markdown',
    )
    return
  try:
    target_admin = int(ctx.args[0])
    banned_command = ctx.args[1].lower()
    query(
        'DELETE FROM banned_admin_commands WHERE admin_id=%s AND command=%s',
        (target_admin, banned_command),
    )
    await update.message.reply_text(
        f'✅ Đã gỡ cấm lệnh `/{banned_command}` cho Admin `{target_admin}`',
        parse_mode='Markdown',
    )
  except ValueError:
    await update.message.reply_text('❌ ID không hợp lệ!')


async def baotri_hethong_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  if len(ctx.args) < 1:
    current_status = (
        '🔴 ĐANG BẢO TRÌ' if is_system_maintenance() else '🟢 HOẠT ĐỘNG'
    )
    await update.message.reply_text(
        f'🛠 **TRẠNG THÁI HỆ THỐNG**\n\n📊 Hiện tại: {current_status}\n\n📝 Cú'
        ' pháp:\n• Bật bảo trì: `/baotriall on`\n• Tắt bảo trì: `/baotriall'
        ' off`',
        parse_mode='Markdown',
    )
    return
  action = ctx.args[0].lower()
  if action == 'on':
    query("UPDATE settings SET value='1' WHERE key='system_maintenance'")
    users = query('SELECT user_id FROM users')
    sent_count = 0
    for user in users:
      try:
        await ctx.bot.send_message(
            user[0],
            '🔧 **THÔNG BÁO BẢO TRÌ**\n\nHệ thống đang được nâng cấp và bảo'
            ' trì.\nBot sẽ tạm thời ngừng hoạt động.\n\n⏰ Vui lòng quay lại'
            ' sau ít phút!\nCảm ơn bạn đã thông cảm.',
            parse_mode='Markdown',
        )
        sent_count += 1
        await asyncio.sleep(0.5)
      except:
        pass
    await update.message.reply_text(
        '🔧 **ĐÃ BẬT BẢO TRÌ TOÀN HỆ THỐNG**\n\n✅ Đã gửi thông báo đến'
        f' {sent_count} người dùng.',
        parse_mode='Markdown',
    )
  elif action == 'off':
    query("UPDATE settings SET value='0' WHERE key='system_maintenance'")
    users = query('SELECT user_id FROM users')
    sent_count = 0
    for user in users:
      try:
        await ctx.bot.send_message(
            user[0],
            '✅ **HỆ THỐNG Đã TRỞ LẠI**\n\nQuá trình bảo trì đã hoàn tất!\nBot'
            ' đã sẵn sàng hoạt động trở lại.\n\n🎮 Chúc bạn chơi game vui vẻ!',
            parse_mode='Markdown',
        )
        sent_count += 1
        await asyncio.sleep(0.5)
      except:
        pass
    await update.message.reply_text(
        '✅ **ĐÃ TẮT BẢO TRÌ TOÀN HỆ THỐNG**\n\n✅ Đã gửi thông báo đến'
        f' {sent_count} người dùng.',
        parse_mode='Markdown',
    )
  else:
    await update.message.reply_text(
        '❌ Sai cú pháp! Dùng `on` hoặc `off`', parse_mode='Markdown'
    )


@admin_only
async def baotri_he_thong_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  maintenance_items = {
      'mt_taixiu': {'name': '🎲 TÀI XỈU 6D', 'type': 'game', 'icon': '🎲'},
      'mt_xocdia': {'name': '💿 XÓC ĐĨA', 'type': 'game', 'icon': '💿'},
      'mt_duaxe': {'name': '🏎️ ĐUA XE', 'type': 'game', 'icon': '🏎️'},
      'mt_domin': {'name': '💣 DÒ MÌN', 'type': 'game', 'icon': '💣'},
      'mt_penalty': {'name': '⚽ PENALTY', 'type': 'game', 'icon': '⚽'},
      'mt_gomo': {'name': '🪵 GÕ MÕ', 'type': 'game', 'icon': '🪵'},
      'mt_quayso': {'name': '🔢 QUAY SỐ', 'type': 'game', 'icon': '🔢'},
      'mt_baucua': {'name': '🦀 BẦU CUA', 'type': 'game', 'icon': '🦀'},
      'mt_xoso': {'name': '📉 XỔ SỐ', 'type': 'game', 'icon': '📉'},
      'mt_vongquay': {'name': '🎡 VÒNG QUAY', 'type': 'game', 'icon': '🎡'},
      'mt_caothap': {'name': '🃏 CAO THẤP', 'type': 'game', 'icon': '🃏'},
      'mt_rutgo': {'name': '🪵 RÚT GỖ', 'type': 'game', 'icon': '🪵'},
      'mt_tomau': {'name': '🎨 TÔ MÀU', 'type': 'game', 'icon': '🎨'},
      'mt_nap': {'name': '💳 NẠP TIỀN', 'type': 'feature', 'icon': '💳'},
      'mt_rut': {'name': '🛒 RÚT TIỀN', 'type': 'feature', 'icon': '🛒'},
  }

  kb = []
  kb.append([InlineKeyboardButton('━━━ 🎮 GAME 🎮 ━━━', callback_data='none')])
  game_items = [
      (k, v) for k, v in maintenance_items.items() if v['type'] == 'game'
  ]
  for i in range(0, len(game_items), 2):
    row = []
    for j in range(2):
      if i + j < len(game_items):
        key, item = game_items[i + j]
        status = '🔴 OFF' if check_mt(key) else '🟢 ON'
        row.append(
            InlineKeyboardButton(
                f"{item['icon']} {item['name']}: {status}",
                callback_data=f'mt_toggle_{key}',
            )
        )
    kb.append(row)

  kb.append(
      [InlineKeyboardButton('━━━ ⚙️ TÍNH NĂNG ⚙️ ━━━', callback_data='none')]
  )
  feature_items = [
      (k, v) for k, v in maintenance_items.items() if v['type'] == 'feature'
  ]
  for i in range(0, len(feature_items), 2):
    row = []
    for j in range(2):
      if i + j < len(feature_items):
        key, item = feature_items[i + j]
        status = '🔴 OFF' if check_mt(key) else '🟢 ON'
        row.append(
            InlineKeyboardButton(
                f"{item['icon']} {item['name']}: {status}",
                callback_data=f'mt_toggle_{key}',
            )
        )
    kb.append(row)

  kb.append([
      InlineKeyboardButton('🔴 TẮT TẤT CẢ', callback_data='mt_turnoff_all'),
      InlineKeyboardButton('🟢 BẬT TẤT CẢ', callback_data='mt_turnon_all'),
  ])
  kb.append([InlineKeyboardButton('❌ ĐÓNG BẢNG', callback_data='close_admin')])

  await update.message.reply_text(
      '🛠 **BẢNG BẢO TRÌ HỆ THỐNG** 🛠\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🟢 **ON** ='
      ' Hoạt động bình thường\n🔴 **OFF** = Đang bảo trì (không thể sử'
      ' dụng)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👇 **Bấm vào từng mục để'
      ' bật/tắt bảo trì:**',
      reply_markup=InlineKeyboardMarkup(kb),
      parse_mode='Markdown',
  )


async def handle_mt_toggle_callback(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE
):
  q = update.callback_query
  uid = q.from_user.id

  if uid not in ADMIN_IDS:
    await q.answer('❌ Bạn không có quyền!', show_alert=True)
    return

  data = q.data

  if data == 'mt_turnoff_all':
    keys = [
        'mt_taixiu',
        'mt_xocdia',
        'mt_duaxe',
        'mt_domin',
        'mt_penalty',
        'mt_gomo',
        'mt_quayso',
        'mt_baucua',
        'mt_xoso',
        'mt_vongquay',
        'mt_caothap',
        'mt_rutgo',
        'mt_tomau',
        'mt_nap',
        'mt_rut',
    ]
    for key in keys:
      query("UPDATE settings SET value='1' WHERE key=%s", (key,))
    await q.answer(
        '✅ Đã tắt BẢO TRÌ tất cả tính năng và game!', show_alert=True
    )
    await baotri_he_thong_cmd(update, ctx)

  elif data == 'mt_turnon_all':
    keys = [
        'mt_taixiu',
        'mt_xocdia',
        'mt_duaxe',
        'mt_domin',
        'mt_penalty',
        'mt_gomo',
        'mt_quayso',
        'mt_baucua',
        'mt_xoso',
        'mt_vongquay',
        'mt_caothap',
        'mt_rutgo',
        'mt_tomau',
        'mt_nap',
        'mt_rut',
    ]
    for key in keys:
      query("UPDATE settings SET value='0' WHERE key=%s", (key,))
    await q.answer(
        '✅ Đã bật HOẠT ĐỘNG tất cả tính năng và game!', show_alert=True
    )
    await baotri_he_thong_cmd(update, ctx)

  elif data.startswith('mt_toggle_'):
    key = data.replace('mt_toggle_', '')
    new_val = '1' if not check_mt(key) else '0'
    query('UPDATE settings SET value=%s WHERE key=%s', (new_val, key))

    names = {
        'mt_taixiu': 'TÀI XỈU',
        'mt_xocdia': 'XÓC ĐĨA',
        'mt_duaxe': 'ĐUA XE',
        'mt_domin': 'DÒ MÌN',
        'mt_penalty': 'PENALTY',
        'mt_gomo': 'GÕ MÕ',
        'mt_quayso': 'QUAY SỐ',
        'mt_baucua': 'BẦU CUA',
        'mt_xoso': 'XỔ SỐ',
        'mt_vongquay': 'VÒNG QUAY',
        'mt_caothap': 'CAO THẤP',
        'mt_rutgo': 'RÚT GỖ',
        'mt_tomau': 'TÔ MÀU',
        'mt_nap': 'NẠP TIỀN',
        'mt_rut': 'RÚT TIỀN',
    }
    name = names.get(key, key)
    status = '🔴 ĐANG BẢO TRÌ' if new_val == '1' else '🟢 HOẠT ĐỘNG'
    await q.answer(f'{name}: {status}', show_alert=True)
    await baotri_he_thong_cmd(update, ctx)


@admin_only
async def baotri_id_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  if len(ctx.args) < 1:
    await update.message.reply_text(
        '❌ **Cú pháp:** `/baotriid [ID_người_dùng]`\n\n📝 **Ví dụ:** `/baotriid'
        ' 12345678`',
        parse_mode='Markdown',
    )
    return

  try:
    target_id = int(ctx.args[0])
  except ValueError:
    await update.message.reply_text('❌ ID không hợp lệ!', parse_mode='Markdown')
    return

  user_check = query('SELECT 1 FROM users WHERE user_id=%s', (target_id,))
  if not user_check:
    await update.message.reply_text(
        f'❌ Không tìm thấy người dùng với ID `{target_id}`!',
        parse_mode='Markdown',
    )
    return

  items = {
      1: {'name': '🎲 TÀI XỈU 6D', 'type': 'game', 'icon': '🎲'},
      2: {'name': '💿 XÓC ĐĨA', 'type': 'game', 'icon': '💿'},
      3: {'name': '🏎️ ĐUA XE', 'type': 'game', 'icon': '🏎️'},
      4: {'name': '💣 DÒ MÌN', 'type': 'game', 'icon': '💣'},
      5: {'name': '⚽ PENALTY', 'type': 'game', 'icon': '⚽'},
      6: {'name': '🪵 GÕ MÕ', 'type': 'game', 'icon': '🪵'},
      7: {'name': '🔢 QUAY SỐ', 'type': 'game', 'icon': '🔢'},
      8: {'name': '🦀 BẦU CUA', 'type': 'game', 'icon': '🦀'},
      9: {'name': '📉 XỔ SỐ', 'type': 'game', 'icon': '📉'},
      10: {'name': '🎡 VÒNG QUAY', 'type': 'game', 'icon': '🎡'},
      11: {'name': '🃏 CAO THẤP', 'type': 'game', 'icon': '🃏'},
      12: {'name': '🪵 RÚT GỖ', 'type': 'game', 'icon': '🪵'},
      13: {'name': '🎨 TÔ MÀU', 'type': 'game', 'icon': '🎨'},
      'nap': {'name': '💳 NẠP TIỀN', 'type': 'feature', 'icon': '💳'},
      'rut': {'name': '🛒 RÚT TIỀN', 'type': 'feature', 'icon': '🛒'},
  }

  kb = []
  kb.append([InlineKeyboardButton('━━━ 🎮 GAME 🎮 ━━━', callback_data='none')])
  game_items = [(k, v) for k, v in items.items() if v['type'] == 'game']
  for i in range(0, len(game_items), 2):
    row = []
    for j in range(2):
      if i + j < len(game_items):
        gid, item = game_items[i + j]
        is_banned = is_game_banned(target_id, gid)
        status = '🔴 CẤM' if is_banned else '🟢 MỞ'
        row.append(
            InlineKeyboardButton(
                f"{item['icon']} {item['name']}: {status}",
                callback_data=f'user_toggle_game_{target_id}_{gid}',
            )
        )
    kb.append(row)

  kb.append(
      [InlineKeyboardButton('━━━ ⚙️ TÍNH NĂNG ⚙️ ━━━', callback_data='none')]
  )
  feature_items = [(k, v) for k, v in items.items() if v['type'] == 'feature']
  for i in range(0, len(feature_items), 2):
    row = []
    for j in range(2):
      if i + j < len(feature_items):
        fkey, item = feature_items[i + j]
        is_banned = is_feature_banned(target_id, fkey)
        status = '🔴 CẤM' if is_banned else '🟢 MỞ'
        row.append(
            InlineKeyboardButton(
                f"{item['icon']} {item['name']}: {status}",
                callback_data=f'user_toggle_feature_{target_id}_{fkey}',
            )
        )
    kb.append(row)

  kb.append([
      InlineKeyboardButton(
          '🔴 CẤM TẤT CẢ', callback_data=f'user_turnoff_all_{target_id}'
      ),
      InlineKeyboardButton(
          '🟢 MỞ TẤT CẢ', callback_data=f'user_turnon_all_{target_id}'
      ),
  ])
  kb.append([
      InlineKeyboardButton(
          '🚫 CẤM TOÀN BỘ USER', callback_data=f'user_ban_full_{target_id}'
      ),
      InlineKeyboardButton(
          '✅ MỞ TOÀN BỘ USER', callback_data=f'user_unban_full_{target_id}'
      ),
  ])
  kb.append([InlineKeyboardButton('❌ ĐÓNG BẢNG', callback_data='close_admin')])

  user_info = query(
      'SELECT balance, total_bet FROM users WHERE user_id=%s', (target_id,)
  )
  balance = user_info[0][0] if user_info else 0
  total_bet = user_info[0][1] if user_info else 0

  await update.message.reply_text(
      f'🛠 **BẢNG BẢO TRÌ NGƯỜI DÙNG** 🛠\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👤'
      f' **ID:** `{target_id}`\n💰 **Số dư:** `{balance:,}đ`\n📊 **Tổng'
      f' cược:** `{total_bet:,}đ`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🟢 **MỞ** ='
      ' Được sử dụng\n🔴 **CẤM** = Bị khóa (không thể sử'
      ' dụng)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👇 **Bấm vào từng mục để'
      ' bật/tắt cấm:**',
      reply_markup=InlineKeyboardMarkup(kb),
      parse_mode='Markdown',
  )


async def handle_user_maintenance_callback(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE
):
  q = update.callback_query
  uid = q.from_user.id

  if uid not in ADMIN_IDS:
    await q.answer('❌ Bạn không có quyền!', show_alert=True)
    return

  data = q.data

  if data.startswith('user_toggle_game_'):
    parts = data.split('_')
    target_id = int(parts[3])
    game_id = int(parts[4])

    if is_game_banned(target_id, game_id):
      query(
          'DELETE FROM banned_games WHERE user_id=%s AND game_id=%s',
          (target_id, game_id),
      )
      await q.answer(
          f'✅ Đã MỞ game ID {game_id} cho user {target_id}', show_alert=True
      )
    else:
      query(
          'INSERT INTO banned_games VALUES(%s, %s) ON CONFLICT DO NOTHING',
          (target_id, game_id),
      )
      await q.answer(
          f'🔴 Đã CẤM game ID {game_id} cho user {target_id}', show_alert=True
      )

    fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
    await baotri_id_cmd(update, fake_ctx)

  elif data.startswith('user_toggle_feature_'):
    parts = data.split('_')
    target_id = int(parts[3])
    feature = parts[4]

    if is_feature_banned(target_id, feature):
      query(
          'DELETE FROM banned_features WHERE user_id=%s AND feature=%s',
          (target_id, feature),
      )
      await q.answer(
          f'✅ Đã MỞ tính năng {feature} cho user {target_id}', show_alert=True
      )
    else:
      query(
          'INSERT INTO banned_features VALUES(%s, %s) ON CONFLICT DO NOTHING',
          (target_id, feature),
      )
      await q.answer(
          f'🔴 Đã CẤM tính năng {feature} cho user {target_id}', show_alert=True
      )

    fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
    await baotri_id_cmd(update, fake_ctx)

  elif data.startswith('user_turnoff_all_'):
    target_id = int(data.split('_')[3])
    for game_id in range(1, 14):
      query(
          'INSERT INTO banned_games VALUES(%s, %s) ON CONFLICT DO NOTHING',
          (target_id, game_id),
      )
    features = ['nap', 'rut']
    for feature in features:
      query(
          'INSERT INTO banned_features VALUES(%s, %s) ON CONFLICT DO NOTHING',
          (target_id, feature),
      )
    await q.answer(
        f'🔴 Đã CẤM TẤT CẢ game và tính năng cho user {target_id}',
        show_alert=True,
    )
    fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
    await baotri_id_cmd(update, fake_ctx)

  elif data.startswith('user_turnon_all_'):
    target_id = int(data.split('_')[3])
    query('DELETE FROM banned_games WHERE user_id=%s', (target_id,))
    query('DELETE FROM banned_features WHERE user_id=%s', (target_id,))
    await q.answer(
        f'🟢 Đã MỞ TẤT CẢ game và tính năng cho user {target_id}',
        show_alert=True,
    )
    fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
    await baotri_id_cmd(update, fake_ctx)

  elif data.startswith('user_ban_full_'):
    target_id = int(data.split('_')[3])
    query(
        'INSERT INTO banned VALUES(%s) ON CONFLICT (user_id) DO NOTHING',
        (target_id,),
    )
    await q.answer(f'🚫 Đã CẤM TOÀN BỘ user {target_id}', show_alert=True)
    fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
    await baotri_id_cmd(update, fake_ctx)

  elif data.startswith('user_unban_full_'):
    target_id = int(data.split('_')[3])
    query('DELETE FROM banned WHERE user_id=%s', (target_id,))
    await q.answer(f'✅ Đã MỞ TOÀN BỘ user {target_id}', show_alert=True)
    fake_ctx = type('obj', (object,), {'args': [str(target_id)]})()
    await baotri_id_cmd(update, fake_ctx)


async def tatroom_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  chat_id = update.effective_chat.id
  if update.effective_chat.type == 'private':
    await update.message.reply_text('❌ Lệnh này chỉ sử dụng được trong NHÓM!')
    return
  if len(ctx.args) < 1:
    current_status = (
        '🔴 ĐÃ TẮT'
        if not room_betting_enabled.get(chat_id, True)
        else '🟢 ĐANG BẬT'
    )
    await update.message.reply_text(
        f'🎮 **TRẠNG THÁI CƯỢC TRONG NHÓM**\n\n📊 Hiện tại: {current_status}\n\n📝 Cú'
        ' pháp:\n• Tắt cược: `/tatroom off`\n• Bật cược: `/tatroom on`',
        parse_mode='Markdown',
    )
    return
  action = ctx.args[0].lower()
  if action == 'off':
    room_betting_enabled[chat_id] = False
    await update.message.reply_text(
        '🔴 **ĐÃ TẮT CƯỢC TRONG NHÓM!**\n\n✅ Các ván cược hiện tại sẽ kết'
        ' thúc.\n⚠️ Người dùng sẽ không thể đặt cược mới.',
        parse_mode='Markdown',
    )
  elif action == 'on':
    room_betting_enabled[chat_id] = True
    await update.message.reply_text(
        '🟢 **ĐÃ BẬT CƯỢC TRONG NHÓM!**\n\n✅ Người dùng có thể đặt cược bình'
        ' thường.',
        parse_mode='Markdown',
    )
  else:
    await update.message.reply_text(
        '❌ Sai cú pháp! Dùng `on` hoặc `off`', parse_mode='Markdown'
    )


async def quanlyadmin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  all_admins = ADMIN_IDS.copy()
  banned_admins = query('SELECT admin_id FROM banned_admins')
  banned_ids = [b[0] for b in banned_admins] if banned_admins else []
  kb = []
  kb.append(
      [InlineKeyboardButton('👤 DANH SÁCH ADMIN', callback_data='admin_list_header')]
  )
  for admin_id in all_admins:
    status = '🚫' if admin_id in banned_ids else '✅'
    btn_text = f'{status} ADMIN {admin_id}'
    if admin_id == 8619503816:
      btn_text = f'👑 {btn_text}'
    kb.append([
        InlineKeyboardButton(
            btn_text, callback_data=f'admin_detail_{admin_id}'
        )
    ])
  kb.append([InlineKeyboardButton('❌ ĐÓNG', callback_data='close_admin')])
  await update.message.reply_text(
      '👑 **BẢNG QUẢN LÝ ADMIN**\n━━━━━━━━━━━━━━━━━━━━━\n🟢 ✅ = Hoạt động | 🔴 🚫 ='
      ' Bị cấm\n👑 = Admin chính (có toàn quyền)\n━━━━━━━━━━━━━━━━━━━━━\n👇 Bấm'
      ' vào Admin để quản lý chi tiết:',
      reply_markup=InlineKeyboardMarkup(kb),
      parse_mode='Markdown',
  )


async def admin_manage_commands_callback(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE
):
  query_data = update.callback_query.data
  q = update.callback_query
  parts = query_data.split('_')
  if len(parts) < 3:
    target_admin_id = int(parts[2]) if len(parts) > 2 else None
    admin_commands = [
        'tile1',
        'tileall',
        'resetall',
        'xoalsall',
        'soduall',
        'tong',
        'thongke',
        'baotri',
        'cam',
        'bocam',
        'add',
        'sub',
        'ban',
        'unban',
        'nap',
        'kmnap',
        'kmnapvc',
        'taocode',
        'setname',
        'resetsdall',
        'xoals',
        'check',
        'info',
        'resetbank',
        'send',
        'rep',
        'tatroom',
        'baotriall',
    ]
    kb = []
    for cmd in admin_commands:
      is_banned = (
          is_admin_command_banned(target_admin_id, cmd)
          if target_admin_id
          else False
      )
      status = '❌ CẤM' if is_banned else '✅ MỞ'
      btn_text = f'{status} /{cmd}'
      kb.append([
          InlineKeyboardButton(
              btn_text,
              callback_data=f'admin_toggle_cmd_{target_admin_id}_{cmd}',
          )
      ])
    kb.append([InlineKeyboardButton('🔙 QUAY LẠI', callback_data='admin_back')])
    await q.edit_message_text(
        f'📋 **QUẢN LÝ LỆNH CHO ADMIN `{target_admin_id}`**\n━━━━━━━━━━━━━━━━━━━━━\n✅'
        ' MỞ: Admin được dùng lệnh\n❌ CẤM: Admin KHÔNG được dùng lệnh\n\n👇 Bấm'
        ' vào lệnh để chuyển trạng thái:',
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode='Markdown',
    )
    return
  action = parts[1]
  if action == 'toggle':
    target_admin_id = int(parts[2])
    cmd_name = '_'.join(parts[3:])
    if is_admin_command_banned(target_admin_id, cmd_name):
      query(
          'DELETE FROM banned_admin_commands WHERE admin_id=%s AND command=%s',
          (target_admin_id, cmd_name),
      )
      await q.answer(
          f'✅ Đã MỞ lệnh /{cmd_name} cho admin {target_admin_id}',
          show_alert=True,
      )
    else:
      now_str = get_vietnam_datetime_db()
      query(
          'INSERT INTO banned_admin_commands VALUES(%s, %s, %s, %s, %s)',
          (
              target_admin_id,
              cmd_name,
              q.from_user.id,
              'Quản lý qua bảng',
              now_str,
          ),
      )
      await q.answer(
          f'❌ Đã CẤM lệnh /{cmd_name} cho admin {target_admin_id}',
          show_alert=True,
      )
    await admin_manage_commands_callback(update, ctx)
    return


async def lsnap_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  if len(ctx.args) < 1:
    await update.message.reply_text(
        '❌ Cú pháp: `/lsnap [ID_người_dùng]`', parse_mode='Markdown'
    )
    return
  try:
    target_id = int(ctx.args[0])
    data = query(
        "SELECT amount, admin_id, time FROM deposit_history WHERE user_id=%s AND"
        " status='success' ORDER BY time DESC LIMIT 20",
        (target_id,),
    )
    if not data:
      await update.message.reply_text(
          f'📋 ID `{target_id}` chưa có lịch sử nạp nào!', parse_mode='Markdown'
      )
      return
    msg = f'📥 **LỊCH SỬ NẠP CỦA ID `{target_id}`**\n━━━━━━━━━━━━━━━━━━━━━\n'
    for row in data:
      msg += (
          f'✅ `+{row[0]:,}đ` | Admin: `{row[1]}`\n   ⏰'
          f' _{row[2]}_\n━━━━━━━━━━━━━━━━━━━━━\n'
      )
    await update.message.reply_text(msg, parse_mode='Markdown')
  except ValueError:
    await update.message.reply_text('❌ ID không hợp lệ!')


async def lsrut_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  if len(ctx.args) < 1:
    await update.message.reply_text(
        '❌ Cú pháp: `/lsrut [ID_người_dùng]`', parse_mode='Markdown'
    )
    return
  try:
    target_id = int(ctx.args[0])
    data = query(
        'SELECT amount, status, admin_id, time FROM withdraw_history WHERE'
        ' user_id=%s ORDER BY time DESC LIMIT 20',
        (target_id,),
    )
    if not data:
      await update.message.reply_text(
          f'📋 ID `{target_id}` chưa có lịch sử rút nào!', parse_mode='Markdown'
      )
      return
    msg = f'📤 **LỊCH SỬ RÚT CỦA ID `{target_id}`**\n━━━━━━━━━━━━━━━━━━━━━\n'
    for row in data:
      status_icon = (
          '✅' if row[1] == 'success' else '❌' if row[1] == 'rejected' else '⏳'
      )
      status_text = (
          'Thành công'
          if row[1] == 'success'
          else 'Bị từ chối'
          if row[1] == 'rejected'
          else 'Chờ duyệt'
      )
      msg += f'{status_icon} `{row[0]:,}đ` | {status_text}\n'
      if row[2]:
        msg += f'   👮 Admin: `{row[2]}`\n'
      msg += f'   ⏰ _{row[3]}_\n━━━━━━━━━━━━━━━━━━━━━\n'
    await update.message.reply_text(msg, parse_mode='Markdown')
  except ValueError:
    await update.message.reply_text('❌ ID không hợp lệ!')


@admin_only
async def lsnapall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  limit = 20
  if ctx.args and ctx.args[0].isdigit():
    limit = min(int(ctx.args[0]), 100)
  data = query(
      'SELECT id, user_id, amount, admin_id, time FROM deposit_history WHERE'
      " status='success' ORDER BY time DESC LIMIT %s",
      (limit,),
  )
  if not data:
    await update.message.reply_text(
        '📋 Chưa có lịch sử nạp nào trong hệ thống!', parse_mode='Markdown'
    )
    return
  total_amount = (
      query(
          "SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE status='success'"
      )[0][0]
      or 0
  )
  msg = (
      '📥 **TẤT CẢ LỊCH SỬ NẠP (Hiển thị'
      f' {len(data)}/{limit})**\n━━━━━━━━━━━━━━━━━━━━━\n💰 **Tổng nạp toàn hệ'
      f' thống:** `{total_amount:,}đ`\n━━━━━━━━━━━━━━━━━━━━━\n\n'
  )
  for row in data:
    msg += (
        f'🆔 #{row[0]} | 👤 ID `{row[1]}` | ✅ `+{row[2]:,}đ` | 👮 Admin'
        f' `{row[3]}`\n   ⏰ _{row[4]}_\n━━━━━━━━━━━━━━━━━━━━━\n'
    )
  if len(msg) > 4000:
    for x in range(0, len(msg), 4000):
      await update.message.reply_text(msg[x : x + 4000], parse_mode='Markdown')
  else:
    await update.message.reply_text(msg, parse_mode='Markdown')


@admin_only
async def lsrutall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  limit = 20
  if ctx.args and ctx.args[0].isdigit():
    limit = min(int(ctx.args[0]), 100)
  data = query(
      'SELECT id, user_id, amount, status, admin_id, time, admin_note FROM'
      ' withdraw_history ORDER BY time DESC LIMIT %s',
      (limit,),
  )
  if not data:
    await update.message.reply_text(
        '📋 Chưa có lịch sử rút nào trong hệ thống!', parse_mode='Markdown'
    )
    return
  total_success = (
      query(
          "SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE status='success'"
      )[0][0]
      or 0
  )
  total_pending = (
      query(
          "SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE status='pending'"
      )[0][0]
      or 0
  )
  total_rejected = (
      query(
          "SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE status='rejected'"
      )[0][0]
      or 0
  )
  msg = (
      '📤 **TẤT CẢ LỊCH SỬ RÚT (Hiển thị'
      f' {len(data)}/{limit})**\n━━━━━━━━━━━━━━━━━━━━━\n✅ **Thành công:**'
      f' `{total_success:,}đ`\n⏳ **Chờ duyệt:** `{total_pending:,}đ`\n❌ **Từ'
      f' chối:** `{total_rejected:,}đ`\n━━━━━━━━━━━━━━━━━━━━━\n\n'
  )
  for row in data:
    status_icon = (
        '✅' if row[3] == 'success' else '❌' if row[3] == 'rejected' else '⏳'
    )
    status_text = (
        'Thành công'
        if row[3] == 'success'
        else 'Bị từ chối'
        if row[3] == 'rejected'
        else 'Chờ duyệt'
    )
    msg += (
        f'🆔 #{row[0]} | 👤 ID `{row[1]}` | {status_icon} `{row[2]:,}đ` |'
        f' {status_text}\n'
    )
    if row[4]:
      msg += f'   👮 Admin: `{row[4]}`\n'
    if row[6]:
      msg += f'   📝 Ghi chú: {row[6]}\n'
    msg += f'   ⏰ _{row[5]}_\n━━━━━━━━━━━━━━━━━━━━━\n'
  if len(msg) > 4000:
    for x in range(0, len(msg), 4000):
      await update.message.reply_text(msg[x : x + 4000], parse_mode='Markdown')
  else:
    await update.message.reply_text(msg, parse_mode='Markdown')


@admin_only
async def thongke_nap_rut_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  filter_type = 'today'
  if ctx.args:
    filter_type = ctx.args[0].lower()
  now = get_vietnam_time()
  today_str = now.strftime('%d/%m/%Y')
  this_month_str = now.strftime('/%m/%Y')
  this_year_str = now.strftime('/%Y')
  if filter_type == 'today' or filter_type == 'ngay':
    nap_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE'
        " status='success' AND time LIKE %s",
        (f'%{today_str}%',),
    )
    rut_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE'
        " status='success' AND time LIKE %s",
        (f'%{today_str}%',),
    )
    title = f'📅 HÔM NAY ({today_str})'
  elif filter_type == 'yesterday' or filter_type == 'homqua':
    yesterday = (now - timedelta(days=1)).strftime('%d/%m/%Y')
    nap_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE'
        " status='success' AND time LIKE %s",
        (f'%{yesterday}%',),
    )
    rut_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE'
        " status='success' AND time LIKE %s",
        (f'%{yesterday}%',),
    )
    title = f'📅 HÔM QUA ({yesterday})'
  elif filter_type == 'week' or filter_type == 'tuần':
    week_ago = (now - timedelta(days=7)).strftime('%d/%m/%Y')
    nap_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE'
        " status='success' AND time >= %s",
        (f'%{week_ago}%',),
    )
    rut_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE'
        " status='success' AND time >= %s",
        (f'%{week_ago}%',),
    )
    title = f'📅 7 NGÀY QUA (từ {week_ago})'
  elif filter_type == 'month' or filter_type == 'tháng':
    nap_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE'
        " status='success' AND time LIKE %s",
        (f'%{this_month_str}%',),
    )
    rut_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE'
        " status='success' AND time LIKE %s",
        (f'%{this_month_str}%',),
    )
    title = f'📅 THÁNG {now.month}/{now.year}'
  elif filter_type == 'year' or filter_type == 'năm':
    nap_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE'
        " status='success' AND time LIKE %s",
        (f'%{this_year_str}%',),
    )
    rut_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE'
        " status='success' AND time LIKE %s",
        (f'%{this_year_str}%',),
    )
    title = f'📅 NĂM {now.year}'
  else:
    nap_data = query(
        "SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE status='success'"
    )
    rut_data = query(
        'SELECT COALESCE(SUM(amount), 0) FROM withdraw_history WHERE'
        " status='success'"
    )
    title = '📊 TOÀN THỜI GIAN'
  total_nap = nap_data[0][0] if nap_data else 0
  total_rut = rut_data[0][0] if rut_data else 0
  loi_nhuan = total_nap - total_rut
  loi_nhuan_color = '📈' if loi_nhuan >= 0 else '📉'
  nap_count = query(
      "SELECT COUNT(*) FROM deposit_history WHERE status='success'"
  )
  rut_count = query(
      "SELECT COUNT(*) FROM withdraw_history WHERE status='success'"
  )
  nap_count = nap_count[0][0] if nap_count else 0
  rut_count = rut_count[0][0] if rut_count else 0
  avg_nap = total_nap // nap_count if nap_count > 0 else 0
  avg_rut = total_rut // rut_count if rut_count > 0 else 0
  msg = f"""
💰 **THỐNG KÊ NẠP - RÚT** 💰
━━━━━━━━━━━━━━━━━━━━━
📌 **{title}**
━━━━━━━━━━━━━━━━━━━━━
📥 **TỔNG NẠP:** `{total_nap:,}đ`
   └─ Số giao dịch: `{nap_count}` lần
   └─ Trung bình: `{avg_nap:,}đ`/lần

📤 **TỔNG RÚT:** `{total_rut:,}đ`
   └─ Số giao dịch: `{rut_count}` lần
   └─ Trung bình: `{avg_rut:,}đ`/lần

━━━━━━━━━━━━━━━━━━━━━
{loi_nhuan_color} **LỢI NHUẬN RÒNG:** `{loi_nhuan:,}đ`
━━━━━━━━━━━━━━━━━━━━━
📅 {now.strftime('%H:%M:%S - %d/%m/%Y')}
"""
  await update.message.reply_text(msg, parse_mode='Markdown')


async def baotri_tong_cong_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id != 8619503816:
    await update.message.reply_text(
        '❌ Chỉ Admin chính (ID: 8619503816) mới có quyền sử dụng lệnh này!'
    )
    return
  if len(ctx.args) < 1:
    current_status = (
        '🔴 ĐANG BẢO TRÌ TOÀN BỘ'
        if is_total_maintenance()
        else '🟢 HOẠT ĐỘNG BÌNH THƯỜNG'
    )
    await update.message.reply_text(
        '🛠 **BẢO TRÌ TOÀN BỘ HỆ THỐNG** 🛠\n━━━━━━━━━━━━━━━━━━━━━\n📊 **Trạng thái'
        f' hiện tại:** {current_status}\n\n📝 **Cú pháp:**\n• Bật bảo trì:'
        ' `/baotritc on`\n• Tắt bảo trì: `/baotritc off`',
        parse_mode='Markdown',
    )
    return
  action = ctx.args[0].lower()
  if action == 'on':
    query("UPDATE settings SET value='1' WHERE key='mt_tongbao'")
    users = query('SELECT user_id FROM users')
    sent_count = 0
    for user in users:
      try:
        await ctx.bot.send_message(
            user[0],
            '🔧 **THÔNG BÁO BẢO TRÌ TOÀN BỘ** 🔧\n━━━━━━━━━━━━━━━━━━━━━\n🚨 **HỆ'
            ' THỐNG ĐANG BẢO TRÌ TOÀN BỘ!**\n\n❌ Tất cả các tính năng đều tạm'
            ' thời ngừng hoạt động!\n\n⏰ Vui lòng quay lại sau!\nCảm ơn bạn'
            ' đã thông cảm! 🙏',
            parse_mode='Markdown',
        )
        sent_count += 1
        await asyncio.sleep(0.3)
      except:
        pass
    await update.message.reply_text(
        '🔧 **ĐÃ BẬT BẢO TRÌ TOÀN BỘ HỆ THỐNG** 🔧\n━━━━━━━━━━━━━━━━━━━━━\n✅ Đã gửi'
        f' thông báo đến `{sent_count}` người dùng',
        parse_mode='Markdown',
    )
  elif action == 'off':
    query("UPDATE settings SET value='0' WHERE key='mt_tongbao'")
    users = query('SELECT user_id FROM users')
    sent_count = 0
    for user in users:
      try:
        await ctx.bot.send_message(
            user[0],
            '✅ **HỆ THỐNG ĐÃ TRỞ LẠI!** ✅\n━━━━━━━━━━━━━━━━━━━━━\n🎉 **Bảo trì'
            ' hoàn tất!**\n\n🟢 Tất cả các tính năng đã hoạt động trở lại!\n\n🎮'
            ' Chúc bạn chơi game vui vẻ và may mắn!',
            parse_mode='Markdown',
        )
        sent_count += 1
        await asyncio.sleep(0.3)
      except:
        pass
    await update.message.reply_text(
        '✅ **ĐÃ TẮT BẢO TRÌ TOÀN BỘ HỆ THỐNG** ✅\n━━━━━━━━━━━━━━━━━━━━━\n✅ Đã gửi'
        f' thông báo đến `{sent_count}` người dùng',
        parse_mode='Markdown',
    )
  else:
    await update.message.reply_text(
        '❌ Sai cú pháp! Dùng `on` hoặc `off`', parse_mode='Markdown'
    )


async def tile1all_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  if len(ctx.args) < 2:
    await update.message.reply_text(
        '❌ **Cú pháp:** `/tile1all [id] [tỉ_lệ]`\n\n📝 **Ví dụ:** `/tile1all'
        ' 123456 30`',
        parse_mode='Markdown',
    )
    return
  try:
    target_id = int(ctx.args[0])
    rate = int(ctx.args[1])
    if rate < 0 or rate > 100:
      await update.message.reply_text(
          '❌ Tỉ lệ thắng phải từ 0% đến 100%!', parse_mode='Markdown'
      )
      return
    query('UPDATE users SET rate_bonus = %s WHERE user_id = %s', (rate, target_id))
    await update.message.reply_text(
        '✅ **CẬP NHẬT TỈ LỆ THẮNG THÀNH CÔNG!**\n\n👤 **ID:**'
        f' `{target_id}`\n📊 **Tỉ lệ thắng mới:** `{rate}%`',
        parse_mode='Markdown',
    )
  except ValueError:
    await update.message.reply_text('❌ ID hoặc tỉ lệ không hợp lệ!')


async def taocodeall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  if len(ctx.args) < 2:
    await update.message.reply_text(
        '❌ **Cú pháp:** `/taocodeall [số_tiền] [số_lượng]`\n\n📝 **Ví dụ:**'
        ' `/taocodeall 50000 10`',
        parse_mode='Markdown',
    )
    return
  try:
    reward = int(ctx.args[0])
    quantity = int(ctx.args[1])
    if quantity < 1 or quantity > 100:
      await update.message.reply_text(
          '❌ Số lượng code phải từ 1 đến 100!', parse_mode='Markdown'
      )
      return
    if reward < 1000:
      await update.message.reply_text(
          '❌ Số tiền thưởng tối thiểu là 1,000đ!', parse_mode='Markdown'
      )
      return
    codes = []
    for i in range(quantity):
      code = gen_code()
      query(
          'INSERT INTO codes (code, reward, uses) VALUES(%s, %s, %s)',
          (code, reward, 1),
      )
      codes.append(code)
    msg = (
        f'🎫 **TẠO {quantity} CODE THÀNH CÔNG!**\n━━━━━━━━━━━━━━━━━━━━━\n💰 Mỗi code:'
        f' `{reward:,}đ`\n\n'
    )
    for i, code in enumerate(codes, 1):
      msg += f'{i}. `{code}`\n'
    msg += '\n━━━━━━━━━━━━━━━━━━━━━\n📌 Dùng lệnh `/code [mã]` để nhận thưởng!'
    if len(msg) > 4000:
      await update.message.reply_document(
          document=('codes.txt', '\n'.join(codes)),
          caption=f'🎫 {quantity} code mỗi code {reward:,}đ',
      )
    else:
      await update.message.reply_text(msg, parse_mode='Markdown')
  except ValueError:
    await update.message.reply_text('❌ Số tiền hoặc số lượng không hợp lệ!')


async def xoacode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  if len(ctx.args) < 1:
    await update.message.reply_text(
        '❌ **Cú pháp:** `/xoacode [mã_code]`', parse_mode='Markdown'
    )
    return
  code_str = ctx.args[0].strip().upper()
  data = query('SELECT reward, uses FROM codes WHERE code=%s', (code_str,))
  if not data:
    await update.message.reply_text(
        f'❌ Code `{code_str}` không tồn tại trong hệ thống!',
        parse_mode='Markdown',
    )
    return
  reward, uses = data[0]
  query('DELETE FROM codes WHERE code=%s', (code_str,))
  await update.message.reply_text(
      '✅ **ĐÃ XÓA CODE THÀNH CÔNG!**\n\n🎫 **Mã:** `{code_str}`\n💰 **Giá'
      f' trị:** `{reward:,}đ`',
      parse_mode='Markdown',
  )


async def set_xoso_result_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  if len(ctx.args) < 2:
    await update.message.reply_text(
        '❌ **Cú pháp:** `/setxoso [id] [kết_quả_2_số]`\n\n📝 **Ví dụ:** `/setxoso'
        ' 123456 68`',
        parse_mode='Markdown',
    )
    return
  try:
    target_id = int(ctx.args[0])
    forced_result = ctx.args[1].zfill(2)
    if (
        not forced_result.isdigit()
        or int(forced_result) < 0
        or int(forced_result) > 99
    ):
      await update.message.reply_text(
          '❌ Kết quả phải là số từ 00 đến 99!', parse_mode='Markdown'
      )
      return
    if not hasattr(ctx.bot, 'forced_xoso_results'):
      ctx.bot.forced_xoso_results = {}
    ctx.bot.forced_xoso_results[target_id] = forced_result
    await update.message.reply_text(
        '✅ **ĐÃ CHỈNH KẾT QUẢ XỔ SỐ CHO ID `{target_id}`**\n\n🎯 **Kết quả cố'
        f' định:** `{forced_result}`',
        parse_mode='Markdown',
    )
  except ValueError:
    await update.message.reply_text('❌ ID không hợp lệ!')


async def set_vongquay_result_cmd(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE
):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    await update.message.reply_text('❌ Bạn không có quyền sử dụng lệnh này!')
    return
  if len(ctx.args) < 2:
    await update.message.reply_text(
        '❌ **Cú pháp:** `/setvongquay [id] [tiền_thưởng]`\n\n📝 **Ví dụ:**'
        ' `/setvongquay 123456 50000`',
        parse_mode='Markdown',
    )
    return
  try:
    target_id = int(ctx.args[0])
    forced_prize = int(ctx.args[1])
    if forced_prize < 0:
      await update.message.reply_text(
          '❌ Tiền thưởng không thể âm!', parse_mode='Markdown'
      )
      return
    if not hasattr(ctx.bot, 'forced_vongquay_results'):
      ctx.bot.forced_vongquay_results = {}
    ctx.bot.forced_vongquay_results[target_id] = forced_prize
    await update.message.reply_text(
        '✅ **ĐÃ CHỈNH KẾT QUẢ VÒNG QUAY CHO ID `{target_id}`**\n\n🎡 **Tiền'
        f' thưởng cố định:** `{forced_prize:,}đ`',
        parse_mode='Markdown',
    )
  except ValueError:
    await update.message.reply_text('❌ ID hoặc số tiền không hợp lệ!')


# ===== LỆNH ADMIN =====
@admin_only
async def top_thang_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  data = query(
      'SELECT user_id, SUM(amount) as total_win FROM history WHERE amount > 0'
      " AND note NOT ILIKE '%nạp%' AND note NOT ILIKE '%Code%' AND note NOT"
      " ILIKE '%Checkin%' GROUP BY user_id ORDER BY total_win DESC LIMIT 10"
  )
  if not data:
    await update.message.reply_text('📊 Chưa có dữ liệu thắng cược!')
    return
  msg = '🏆 **TOP 10 NGƯỜI THẮNG NHIỀU NHẤT** 🏆\n━━━━━━━━━━━━━━━━━━━━━\n'
  for i, (uid, total) in enumerate(data, 1):
    medal = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else f'{i}.'
    msg += f'{medal} ID `{uid}` — `+{total:,}đ`\n'
  await update.message.reply_text(msg, parse_mode='Markdown')


@admin_only
async def gift_all_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  if len(ctx.args) < 1:
    await update.message.reply_text(
        '❌ **Cú pháp:** `/giftall [số_tiền] [lý_do]`', parse_mode='Markdown'
    )
    return
  try:
    amount = int(ctx.args[0])
    reason = ' '.join(ctx.args[1:]) if len(ctx.args) > 1 else 'Quà tặng từ Admin'
    if amount < 1000:
      await update.message.reply_text(
          '❌ Số tiền tặng tối thiểu là 1,000đ!', parse_mode='Markdown'
      )
      return
    users = query('SELECT user_id FROM users')
    total_users = len(users) if users else 0
    if total_users == 0:
      await update.message.reply_text('❌ Không có người dùng nào để tặng!')
      return
    confirm_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            '✅ XÁC NHẬN',
            callback_data=(
                f'confirm_giftall_{amount}_{reason}_{total_users}'
            ),
        ),
        InlineKeyboardButton('❌ HỦY', callback_data='close_admin'),
    ]])
    await update.message.reply_text(
        '🎁 **XÁC NHẬN TẶNG QUÀ** 🎁\n━━━━━━━━━━━━━━━━━━━━━\n💰 **Số tiền:**'
        f' `{amount:,}đ/người`\n👥 **Số người:** `{total_users}`\n💵 **Tổng'
        f' chi:** `{amount * total_users:,}đ`\n📝 **Lý do:**'
        ' {reason}\n━━━━━━━━━━━━━━━━━━━━━\n⚠️ Bạn có chắc chắn muốn tặng quà cho tất'
        ' cả?',
        reply_markup=confirm_kb,
        parse_mode='Markdown',
    )
  except ValueError:
    await update.message.reply_text('❌ Số tiền không hợp lệ!')


@admin_only
async def lock_game_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  if len(ctx.args) < 3:
    await update.message.reply_text(
        '❌ **Cú pháp:** `/lockgame [id] [game_id] [lock/unlock]`',
        parse_mode='Markdown',
    )
    return
  try:
    target_id = int(ctx.args[0])
    game_id = int(ctx.args[1])
    action = ctx.args[2].lower()
    if action == 'lock':
      query(
          'INSERT INTO banned_games VALUES(%s, %s) ON CONFLICT DO NOTHING',
          (target_id, game_id),
      )
      await update.message.reply_text(
          f'🔒 **ĐÃ KHÓA GAME**\n👤 ID: `{target_id}`\n🎮 Game ID: `{game_id}`',
          parse_mode='Markdown',
      )
    elif action == 'unlock':
      query(
          'DELETE FROM banned_games WHERE user_id=%s AND game_id=%s',
          (target_id, game_id),
      )
      await update.message.reply_text(
          f'🔓 **ĐÃ MỞ KHÓA GAME**\n👤 ID: `{target_id}`\n🎮 Game ID:'
          f' `{game_id}`',
          parse_mode='Markdown',
      )
    else:
      await update.message.reply_text('❌ Action chỉ là `lock` hoặc `unlock`!')
  except ValueError:
    await update.message.reply_text('❌ ID hoặc game_id không hợp lệ!')


@admin_only
async def bonus_vip_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  users = query('SELECT user_id, total_bet FROM users')
  if not users:
    await update.message.reply_text('❌ Không có người dùng nào!')
    return
  confirm_kb = InlineKeyboardMarkup([[
      InlineKeyboardButton('✅ XÁC NHẬN', callback_data='confirm_bonus_vip'),
      InlineKeyboardButton('❌ HỦY', callback_data='close_admin'),
  ]])
  total_bonus = 0
  bonus_details = []
  for uid, total_bet in users:
    if total_bet >= 50000000:
      bonus = 5000
    elif total_bet >= 20000000:
      bonus = 3000
    elif total_bet >= 10000000:
      bonus = 1500
    elif total_bet >= 5000000:
      bonus = 800
    elif total_bet >= 1000000:
      bonus = 500
    else:
      bonus = 0
    total_bonus += bonus
    if bonus > 0:
      bonus_details.append(f'ID {uid}: +{bonus:,}đ')
  await update.message.reply_text(
      '👑 **THƯỞNG VIP HÀNG THÁNG** 👑\n━━━━━━━━━━━━━━━━━━━━━\n💰 **Tổng thưởng:**'
      f' `{total_bonus:,}đ`\n👥 **Số người được thưởng:**'
      f' `{len(bonus_details)}`\n━━━━━━━━━━━━━━━━━━━━━\n⚠️ Bạn có chắc chắn muốn'
      ' thưởng VIP cho tất cả?',
      reply_markup=confirm_kb,
      parse_mode='Markdown',
  )


@admin_only
async def export_db_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  users = query(
      'SELECT user_id, balance, total_bet, refs FROM users ORDER BY balance'
      ' DESC'
  )
  if not users:
    await update.message.reply_text('❌ Không có dữ liệu để xuất!')
    return
  output = BytesIO()
  output.write('\ufeff'.encode('utf-8'))
  writer = csv.writer(output, delimiter=',')
  writer.writerow(['User ID', 'Số dư (VNĐ)', 'Tổng cược (VNĐ)', 'Số người mời'])
  for user in users:
    writer.writerow([user[0], f'{user[1]:,}', f'{user[2]:,}', user[3]])
  output.seek(0)
  await update.message.reply_document(
      document=output,
      filename=(
          f"users_export_{get_vietnam_time().strftime('%Y%m%d_%H%M%S')}.csv"
      ),
      caption=(
          '📊 **DỮ LIỆU NGƯỜI DÙNG**\n📅 Ngày xuất:'
          f' {get_vietnam_datetime_db()}\n👥 Tổng số user: {len(users)}'
      ),
      parse_mode='Markdown',
  )


@admin_only
async def chinhkq_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
  rates = query('SELECT id, name, rate FROM game_rates ORDER BY id ASC')
  kb = []
  for game_id, name, rate in rates:
    short_name = name[:15] + '..' if len(name) > 15 else name
    kb.append([
        InlineKeyboardButton(
            f'🎮 {short_name} | {rate}%', callback_data=f'rate_show_{game_id}'
        )
    ])
    kb.append([
        InlineKeyboardButton('🔻 -10%', callback_data=f'rate_dec_{game_id}'),
        InlineKeyboardButton('🔺 +10%', callback_data=f'rate_inc_{game_id}'),
    ])
  kb.append([InlineKeyboardButton('❌ ĐÓNG', callback_data='close_admin')])
  msg = (
      '📊 **BẢNG CHỈNH TỈ LỆ THẮNG**\n━━━━━━━━━━━━━━━━━━━━━\nChọn game bên dưới để'
      ' thay đổi tỉ lệ:'
  )
  await update.message.reply_text(
      msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown'
  )
