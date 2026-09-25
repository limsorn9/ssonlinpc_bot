import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, ReplyKeyboardRemove
import requests
import os
import time
import sqlite3
import threading
from flask import Flask, request

# ================= ការកំណត់ទូទៅ =================
TELEGRAM_BOT_TOKEN = os.environ.get('BOT_TOKEN', '') # ត្រូវកំណត់ក្នុង Render 
API_TOKEN = os.environ.get('API_TOKEN', '') # ត្រូវកំណត់ក្នុង Render
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', os.environ.get('RENDER_EXTERNAL_URL', ''))
BASE_URL = "https://www.mspidpro.com/api"

ADMIN_ID = 240224709 

# កំណត់ប្រាក់ចំណេញ (Markup Price) ជាការគុណ
PROFIT_MULTIPLIER = 2.0 

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

# ================= ប្រព័ន្ធទិន្នន័យ (Database) =================
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    user_id INTEGER, 
                    type TEXT, 
                    amount REAL, 
                    description TEXT, 
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def log_transaction(user_id, trans_type, amount, description):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)", (user_id, trans_type, amount, description))
    conn.commit()
    conn.close()

def get_user_balance(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0]
    return 0.0

def add_user_balance(user_id, amount):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?", (user_id, amount, amount))
    conn.commit()
    conn.close()
    log_transaction(user_id, "TOPUP", amount, "បញ្ចូលលុយដោយ Admin")

def deduct_user_balance(user_id, amount, reason="ដកលុយ"):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?", (amount, user_id, amount))
    success = c.rowcount > 0
    conn.commit()
    conn.close()
    if success:
        log_transaction(user_id, "DEDUCT", amount, reason)
    return success

init_db()

# ================= អនុគមន៍ជំនួយ (Helpers) =================
def delete_message_later(chat_id, message_id, delay=60):
    def task():
        time.sleep(delay)
        try:
            bot.delete_message(chat_id, message_id)
        except Exception:
            pass
    threading.Thread(target=task).start()

# ================= Webhook & Commands Setup =================
@app.route('/')
def index():
    return "Bot is running fine on Render!"

@app.route('/' + TELEGRAM_BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

def set_bot_commands():
    commands = [
        BotCommand("start", "ចាប់ផ្តើម / Start"),
        BotCommand("info", "ព័ត៌មានរបស់អ្នក & កាបូបលុយ"),
        BotCommand("pay", "បញ្ចូលលុយ (Add Balance)"),
        BotCommand("1", "Office Online Key & 365 Account"),
        BotCommand("2", "Office Bind Key & 365 Key"),
        BotCommand("3", "Office Phone Key"),
        BotCommand("4", "Windows Online Key"),
        BotCommand("5", "Windows Phone Key"),
        BotCommand("6", "Visio/Project Online Key"),
        BotCommand("7", "Visio/Project Phone Key"),
        BotCommand("8", "Server Online Key"),
        BotCommand("9", "SQL & Visual Studio Key"),
        BotCommand("get_cid", "Get Confirmation ID"),
        BotCommand("check", "Check Key"),
        BotCommand("redeem", "Redeem Key")
    ]
    bot.set_my_commands(commands)

# ================= មុខងារកាបូបលុយ & អាយឌី =================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = ReplyKeyboardRemove()
    bot.send_message(message.chat.id, "👋 សួស្តី! សូមចុចប៊ូតុង Menu នៅផ្នែកខាងឆ្វេងខាងក្រោម ដើម្បីជ្រើសរើសសេវាកម្ម។", reply_markup=markup)

@bot.message_handler(commands=['info'])
def show_info(message):
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID:
        try:
            url = f"{BASE_URL}/balance?token={API_TOKEN}"
            response = requests.get(url, timeout=15)
            data = response.json()
            balance = data.get('balance', 0.0) if data.get('success') else 0.0
        except:
            balance = 0.0
        msg = (f"👑 **ព័ត៌មាន Admin:**\n\n"
               f"🆔 **Telegram ID:** `{user_id}`\n"
               f"🏦 **លុយក្នុងកុង API ពិតប្រាកដ:** `${balance:.2f}`")
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")
        return

    balance = get_user_balance(user_id)
    msg = (f"👤 **ព័ត៌មានរបស់អ្នក:**\n\n"
           f"🆔 **Telegram ID:** `{user_id}`\n"
           f"👛 **កាបូបលុយ (Wallet):** `${balance:.2f}`\n\n"
           f"📌 បើចង់បញ្ចូលលុយ សូមវាយបញ្ជា `/pay`។")
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['pay'])
def pay_info(message):
    msg = (f"🟡 **បង់ប្រាក់តាមរយៈ Binance Pay (USDT)** 🟡\n\n"
           f"📌 **Binance Pay ID:** `832944944`\n"
           f"👤 **Name:** ssonlinestore\n\n"
           f"📥 **របៀបបញ្ចូលលុយ៖**\n"
           f"1. ផ្ញើប្រាក់តាម Binance ខាងលើ ឬស្កេន QR កូដ\n"
           f"2. ផ្ញើវិក័យប័ត្រទៅកាន់ Admin រួមជាមួយ Telegram ID របស់អ្នក (`{message.from_user.id}`)។\n\n"
           f"💵 **ជម្រើសផ្សេងទៀត (គ្មាន Binance)៖**\n"
           f"បើមិនអាចបញ្ចូលលុយតាម Binance ទេ អ្នកអាចឆាតទៅកាន់ Admin ដោយផ្ទាល់ ដើម្បីឲ្យគាត់បញ្ចូលលុយឲ្យតាមរយៈ ABA ឫធនាគារផ្សេងៗបាន!\n"
           f"✅ **ឫក៏អាចឆាតទិញពីអេដមីនផ្ទាល់ក៏បាន!**")
    
    try:
        with open('qr_binance.png', 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=msg, parse_mode="Markdown")
    except Exception:
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
def admin_menu(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = (f"👑 **ផ្ទាំងបញ្ជាសម្រាប់ Super Admin** 👑\n\n"
           f"👉 វាយបញ្ជាខាងក្រោមដើម្បីគ្រប់គ្រងអតិថិជន៖\n"
           f"1. បញ្ចូលលុយ ៖ `/addmoney [ID] [លុយ]`\n"
           f"2. ដកលុយវិញ ៖ `/removemoney [ID] [លុយ]`\n"
           f"3. ឆែកលុយភ្ញៀវ៖ `/checkuser [ID]`\n"
           f"4. ឆែកប្រវត្តិទិញ៖ `/history [ID]`\n"
           f"5. ឆែកលុយកុងពិត៖ `/apibalance`\n\n"
           f"*(ឧទាហរណ៍: /addmoney 123456 10.5)*")
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['addmoney'])
def add_money(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ អ្នកមិនមានសិទ្ធិបញ្ចូលលុយទេ!")
        return
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        amount = float(parts[2])
        
        if user_id == ADMIN_ID:
            bot.reply_to(message, "❌ អ្នកមិនអាចបញ្ចូលលុយឲ្យខ្លួនឯងក្នុងកាបូបនេះបានទេ ព្រោះលុយអ្នកគឺភ្ជាប់ផ្ទាល់ជាមួយ API ពិតប្រាកដរួចហើយ!")
            return
            
        add_user_balance(user_id, amount)
        bot.reply_to(message, f"✅ បានបញ្ចូលលុយ `${amount:.2f}` ទៅឲ្យ ID: `{user_id}` ដោយជោគជ័យ!")
        try:
            bot.send_message(user_id, f"🎉 Admin បានបញ្ចូលលុយ `${amount:.2f}` ទៅក្នុងគណនីរបស់អ្នកហើយ!")
        except:
            pass
    except:
        bot.reply_to(message, "⚠️ ទម្រង់ខុស! ឧទាហរណ៍: `/addmoney 123456789 10.5`")

@bot.message_handler(commands=['removemoney'])
def remove_money(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        amount = float(parts[2])
        
        current_balance = get_user_balance(user_id)
        if current_balance < amount:
            bot.reply_to(message, f"❌ ភ្ញៀវនេះមានលុយតែ `${current_balance:.2f}` ទេ មិនអាចដក `${amount:.2f}` បានឡើយ!")
            return
            
        if deduct_user_balance(user_id, amount, "ដកលុយដោយ Admin"):
            bot.reply_to(message, f"✅ បានដកលុយ `${amount:.2f}` ពី ID: `{user_id}` វិញដោយជោគជ័យ!")
        else:
            bot.reply_to(message, "❌ មានបញ្ហាក្នុងការដកប្រាក់!")
    except:
        bot.reply_to(message, "⚠️ ទម្រង់ខុស! ឧទាហរណ៍: `/removemoney 123456789 10.5`")

@bot.message_handler(commands=['history'])
def check_history(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT type, amount, description, timestamp FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            bot.reply_to(message, f"អត់មានប្រវត្តិទិញ ឫបញ្ចូលលុយសម្រាប់ ID: `{user_id}` ទេ!")
            return
            
        history_msg = f"📜 **ប្រវត្តិប្រតិបត្តិការចុងក្រោយ (ID: `{user_id}`)**\n\n"
        for row in rows:
            t_type, amt, desc, t_time = row
            icon = "🟢" if t_type == "TOPUP" else "🔴"
            history_msg += f"{icon} `{t_time}`\n"
            history_msg += f"   ប្រភេទ: {t_type}\n"
            history_msg += f"   ចំនួន: **${amt:.2f}**\n"
            history_msg += f"   កំណត់ចំណាំ: {desc}\n\n"
            
        bot.reply_to(message, history_msg, parse_mode="Markdown")
    except:
        bot.reply_to(message, "⚠️ ទម្រង់ខុស! ឧទាហរណ៍: `/history 123456789`")

@bot.message_handler(commands=['checkuser'])
def check_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        balance = get_user_balance(user_id)
        bot.reply_to(message, f"👤 **ព័ត៌មានភ្ញៀវ ID `{user_id}`:**\n👛 លុយនៅសល់: `${balance:.2f}`", parse_mode="Markdown")
    except:
        bot.reply_to(message, "⚠️ ទម្រង់ខុស! ឧទាហរណ៍: `/checkuser 123456789`")

@bot.message_handler(commands=['apibalance'])
def check_api_balance(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, "កំពុងឆែកលុយក្នុងកុង mspidpro... ⏳")
    try:
        url = f"{BASE_URL}/balance?token={API_TOKEN}"
        response = requests.get(url, timeout=15)
        data = response.json()
        if data.get('success'):
            real_balance = data.get('balance', 0.0)
            bot.send_message(message.chat.id, f"🏦 **លុយពិតប្រាកដក្នុងកុង mspidpro.com របស់អ្នក:**\n\n💰 សរុបនៅសល់៖ **${real_balance:.2f}**", parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "❌ មិនអាចឆែកលុយបានទេ សូមពិនិត្យមើល API Token របស់អ្នកឡើងវិញ។")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ មានបញ្ហាប្រព័ន្ធ៖ {e}")

# ----------------- មុខងារ Menu ផលិតផល (Shop) -----------------
@bot.message_handler(commands=['1', '2', '3', '4', '5', '6', '7', '8', '9'])
def handle_shop_commands(message):
    category_map = {
        "/1": "Office Online Key",
        "/2": "Office Bind Key",
        "/3": "Office Retail Phone Key",
        "/4": "Windows Key by Online",
        "/5": "Windows Key by Phone",
        "/6": "Visio/Project Retail Online Key",
        "/7": "Visio/Project Retail Phone Key",
        "/8": "Server Retail Key",
        "/9": "SQL & Visual Studio Key"
    }
    
    selected_cat = category_map.get(message.text)
    if not selected_cat:
        return 
        
    bot.send_message(message.chat.id, f"កំពុងទាញយកទំនិញ... ⏳")
    
    try:
        url = f"{BASE_URL}/key-products?token={API_TOKEN}"
        response = requests.get(url, timeout=15)
        data = response.json()
        categories = data.get('categories', [])
        
        found = False
        for category in categories:
            cat_name = category.get('name', '')
            if selected_cat.lower() in cat_name.lower():
                found = True
                products = category.get('products', [])
                bot.send_message(message.chat.id, f"📂 **ប្រភេទ:** {cat_name}", parse_mode="Markdown")
                
                # បង្ហាញទំនិញនីមួយៗ និងមានប៊ូតុងទិញនៅខាងក្រោម (Max 15)
                for item in products[:15]: 
                    product_code = item.get('code')
                    name = item.get('name')
                    
                    original_price = float(item.get('price', 0))
                    stock = item.get('stock')
                    
                    markup = InlineKeyboardMarkup()
                    
                    if original_price < 5:
                        final_price = original_price * 3.0
                        caption = f"📦 {name}\n💵 តម្លៃ: ${final_price:.2f} | 📦 ស្តុកមាន: {stock}"
                        markup.add(InlineKeyboardButton(f"🛒 ទិញឥឡូវនេះ (${final_price:.2f})", callback_data=f"buy_{product_code}_{final_price:.2f}"))
                    elif 5 <= original_price <= 10:
                        final_price = original_price * 2.5
                        caption = f"📦 {name}\n💵 តម្លៃ: ${final_price:.2f} | 📦 ស្តុកមាន: {stock}"
                        markup.add(InlineKeyboardButton(f"🛒 ទិញឥឡូវនេះ (${final_price:.2f})", callback_data=f"buy_{product_code}_{final_price:.2f}"))
                    elif 10 < original_price <= 50:
                        base_price = original_price * 2.0
                        final_price = base_price * 0.9 # បញ្ចុះ 10%
                        caption = (f"📦 {name}\n"
                                   f"💵 តម្លៃពេញ: ~${base_price:.2f}~\n"
                                   f"🎉 **បញ្ចុះតម្លៃ 10% សល់ត្រឹម: ${final_price:.2f}** | 📦 ស្តុកមាន: {stock}")
                        markup.add(InlineKeyboardButton(f"🛒 ទិញឥឡូវនេះ (${final_price:.2f})", callback_data=f"buy_{product_code}_{final_price:.2f}"))
                    else: # > 50
                        base_price = original_price * 2.0
                        final_price = base_price * 0.8 # បញ្ចុះ 20%
                        caption = (f"📦 {name}\n"
                                   f"💵 តម្លៃពេញ: ~${base_price:.2f}~\n"
                                   f"🎉 **បញ្ចុះតម្លៃ 20% សល់ត្រឹម: ${final_price:.2f}** | 📦 ស្តុកមាន: {stock}")
                        markup.add(InlineKeyboardButton(f"🛒 ទិញឥឡូវនេះ (${final_price:.2f})", callback_data=f"buy_{product_code}_{final_price:.2f}"))
                    
                    sent_msg = bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")
                    delete_message_later(message.chat.id, sent_msg.message_id, 60) # លុបសារក្រោយ 1 នាទី
                break
                
        if not found:
            bot.send_message(message.chat.id, f"មិនមានទំនិញក្នុងប្រភេទនេះទេនៅពេលនេះ។")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"មានបញ្ហាពេលទាញទិន្នន័យ៖ {e}")

# ----------------- មុខងារទិញ Key -----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def callback_query(call):
    data_parts = call.data.split('_')
    product_code = data_parts[1]
    sell_price = float(data_parts[2]) 
    user_id = call.from_user.id
    
    if user_id == ADMIN_ID:
        bot.answer_callback_query(call.id, "កំពុងដំណើរការទិញ (សិទ្ធិ Admin)... សូមរង់ចាំ!")
    else:
        user_balance = get_user_balance(user_id)
        if user_balance < sell_price:
            bot.answer_callback_query(call.id, f"❌ លុយរបស់អ្នកមិនគ្រប់គ្រាន់ទេ! (មានតែ ${user_balance:.2f})", show_alert=True)
            return
            
        bot.answer_callback_query(call.id, "កំពុងដំណើរការទិញ... សូមរង់ចាំ!")
        
        if not deduct_user_balance(user_id, sell_price, f"ទិញទំនិញ: {product_code}"):
            bot.send_message(call.message.chat.id, "❌ មានបញ្ហាក្នុងការកាត់ប្រាក់!")
            return
            
        bot.send_message(call.message.chat.id, f"⏳ កំពុងទិញទំនិញ... ទឹកប្រាក់ `${sell_price:.2f}` ត្រូវបានកាត់ចេញពីកាបូបរបស់អ្នក។", parse_mode="Markdown")
    
    timestamp_ms = int(time.time() * 1000)
    order_id = f"KP{timestamp_ms}"
    quantity = 1
    
    try:
        url = f"{BASE_URL}/buy-key?code={product_code}&quantity={quantity}&orderId={order_id}&token={API_TOKEN}"
        response = requests.get(url, timeout=30)
        data = response.json()
        
        if data.get('success'):
            keys = data.get('keys', [])
            keys_str = "\n".join([f"`{k}`" for k in keys])
            
            if user_id == ADMIN_ID:
                msg = (f"✅ **ការបញ្ជាទិញជោគជ័យ (Admin)!**\n\n"
                       f"📦 ទំនិញ: {data.get('name')}\n"
                       f"🔑 **Keys របស់អ្នក:**\n{keys_str}")
            else:
                msg = (f"✅ **ការបញ្ជាទិញជោគជ័យ!**\n\n"
                       f"📦 ទំនិញ: {data.get('name')}\n"
                       f"🔑 **Keys របស់អ្នក:**\n{keys_str}\n\n"
                       f"💰 លុយនៅសល់: `${get_user_balance(user_id):.2f}`")
            bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")
        else:
            if user_id != ADMIN_ID:
                add_user_balance(user_id, sell_price)
            err_msg = (f"❌ **បរាជ័យក្នុងការទិញ!**\n"
                       f"ប្រព័ន្ធកំពុងមានបញ្ហាបច្ចេកទេសបន្តិចបន្តួច (បានបង្វិលលុយសងវិញហើយ)។\n\n"
                       f"💬 សូមទាក់ទងទៅកាន់ Admin ផ្ទាល់ដើម្បីដោះស្រាយបញ្ហានេះ!")
            bot.send_message(call.message.chat.id, err_msg, parse_mode="Markdown")
    except Exception as e:
        if user_id != ADMIN_ID:
            add_user_balance(user_id, sell_price)
        err_msg = (f"❌ **មានបញ្ហាប្រព័ន្ធពេលកំពុងទិញ!**\n"
                   f"(បានបង្វិលលុយសងវិញហើយ)។\n\n"
                   f"💬 សូមទាក់ទងទៅកាន់ Admin ផ្ទាល់ដើម្បីដោះស្រាយបញ្ហានេះ!")
        bot.send_message(call.message.chat.id, err_msg, parse_mode="Markdown")

# ----------------- មុខងារផ្សេងៗ -----------------
@bot.message_handler(commands=['get_cid', 'getcid'])
def get_cid(message):
    try:
        iid = message.text.split(' ', 1)[1].strip()
    except IndexError:
        bot.reply_to(message, "⚠️ សូមបញ្ចូល IID! ឧទាហរណ៍៖ `/get_cid 452919...`\n\n💰 **តម្លៃសេវា:** $4.00", parse_mode="Markdown")
        return
        
    user_id = message.from_user.id
    cost = 4.0
    
    if user_id != ADMIN_ID:
        if get_user_balance(user_id) < cost:
            bot.reply_to(message, f"❌ លុយរបស់អ្នកមិនគ្រប់គ្រាន់ទេ! (សេវាកម្មនេះតម្លៃ ${cost:.2f})")
            return
            
        if not deduct_user_balance(user_id, cost, f"GET CID: {iid[:10]}..."):
            bot.reply_to(message, "❌ មានបញ្ហាក្នុងការកាត់ប្រាក់!")
            return
            
        bot.reply_to(message, f"កំពុងស្វែងរក CID... (កាត់លុយ ${cost:.2f}) ⏳", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"កំពុងស្វែងរក CID... (សិទ្ធិ Admin) ⏳", parse_mode="Markdown")
    
    try:
        url = f"{BASE_URL}/get-cid?token={API_TOKEN}&iid={iid}"
        response = requests.get(url, timeout=30)
        data = response.json()
        if data.get('success'):
            if user_id == ADMIN_ID:
                msg = f"✅ **ជោគជ័យ!**\n\n📌 **IID:** `{data.get('formattedIid', iid)}`\n🔑 **CID:** `{data.get('data')}`"
            else:
                msg = f"✅ **ជោគជ័យ!**\n\n📌 **IID:** `{data.get('formattedIid', iid)}`\n🔑 **CID:** `{data.get('data')}`\n💰 លុយនៅសល់: `${get_user_balance(user_id):.2f}`"
            bot.send_message(message.chat.id, msg, parse_mode="Markdown")
        else:
            if user_id != ADMIN_ID:
                add_user_balance(user_id, cost)
            bot.send_message(message.chat.id, f"❌ បរាជ័យ: {data.get('message')}\n(បានបង្វិលលុយសងវិញ)")
    except Exception as e:
        if user_id != ADMIN_ID:
            add_user_balance(user_id, cost)
        bot.send_message(message.chat.id, f"មានបញ្ហា៖ ប្រព័ន្ធដំណើរការមិនបានល្អ\n(បានបង្វិលលុយសងវិញ)")

@bot.message_handler(commands=['check'])
def check_keys(message):
    try:
        key = message.text.split(' ', 1)[1].strip()
    except IndexError:
        bot.reply_to(message, "⚠️ សូមបញ្ចូល Key! ឧទាហរណ៍៖ `/check VK7JG-...`", parse_mode="Markdown")
        return
    bot.reply_to(message, f"កំពុងពិនិត្យមើល Key ⏳...", parse_mode="Markdown")
    try:
        url = f"{BASE_URL}/check-keys?token={API_TOKEN}&keys={key}"
        response = requests.get(url, timeout=30)
        data = response.json()
        if data.get('success'):
            bot.send_message(message.chat.id, f"📝 **លទ្ធផលការពិនិត្យ:**\n\n{data.get('data')}")
        else:
            bot.send_message(message.chat.id, f"❌ បរាជ័យ: {data.get('message')}")
    except Exception as e:
        bot.send_message(message.chat.id, f"មានបញ្ហា៖ {e}")

@bot.message_handler(commands=['redeem'])
def redeem_keys(message):
    try:
        key = message.text.split(' ', 1)[1].strip()
    except IndexError:
        bot.reply_to(message, "⚠️ សូមបញ្ចូល Key! ឧទាហរណ៍៖ `/redeem J9YRQ-...`", parse_mode="Markdown")
        return
    bot.reply_to(message, f"កំពុង Redeem Key ⏳...", parse_mode="Markdown")
    try:
        url = f"{BASE_URL}/redeem-keys?token={API_TOKEN}&keys={key}"
        response = requests.get(url, timeout=30)
        data = response.json()
        if data.get('success'):
            bot.send_message(message.chat.id, f"📝 **លទ្ធផលការ Redeem:**\n\n{data.get('data')}")
        else:
            bot.send_message(message.chat.id, f"❌ បរាជ័យ: {data.get('message')}")
    except Exception as e:
        bot.send_message(message.chat.id, f"មានបញ្ហា៖ {e}")

if __name__ == '__main__':
    bot.remove_webhook()
    set_bot_commands() # Add commands to Telegram Menu
    bot.set_webhook(url=WEBHOOK_URL + '/' + TELEGRAM_BOT_TOKEN)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
