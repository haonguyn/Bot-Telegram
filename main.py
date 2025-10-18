from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
import logging
import requests
import wikipedia
import asyncio
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.sync import TelegramClient
import pandas as pd
# Cấu hình logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Token của bot Telegram
TOKEN = "7525966717:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Danh sách nhắc nhở
reminders = {}

async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Xem thời tiết", callback_data="weather")],
        [InlineKeyboardButton("Tìm kiếm Wikipedia", callback_data="wiki")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Chào bạn! Tôi là bot Telegram.\nHãy chọn chức năng:", reply_markup=reply_markup)

async def echo(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(update.message.text)

async def remind(update: Update, context: CallbackContext) -> None:
    """Lệnh /remind <thời gian> <nội dung> để đặt nhắc nhở"""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Cách dùng: /remind <thời gian (giây)> <nội dung>")
        return
    try:
        time = int(args[0])
        text = " ".join(args[1:])
        user_id = update.message.chat_id

        if user_id not in reminders:
            reminders[user_id] = []
        reminders[user_id].append((time, text))

        await update.message.reply_text(f"Đã đặt nhắc nhở: {text} sau {time} giây.")
        await asyncio.sleep(time)
        await context.bot.send_message(chat_id=user_id, text=f"🔔 Nhắc nhở: {text}")
    except ValueError:
        await update.message.reply_text("Thời gian phải là số nguyên.")

async def weather(update: Update, context: CallbackContext) -> None:
    """Lệnh /weather <thành phố> để xem thời tiết"""
    if not context.args:
        await update.message.reply_text("Cách dùng: /weather <thành phố>")
        return
    city = " ".join(context.args)
    api_key = "0a4ab9bee9944f6b70f9686341396c28"
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=vi"

    response = requests.get(url).json()
    if response.get("cod") != 200:
        await update.message.reply_text("Không tìm thấy thành phố!")
        return
    
    weather_desc = response["weather"][0]["description"]
    temp = response["main"]["temp"]
    humidity = response["main"]["humidity"]
    wind_speed = response["wind"]["speed"]
    
    reply = f"🌤 Thời tiết tại {city}:\n- {weather_desc.capitalize()}\n- Nhiệt độ: {temp}°C\n- Độ ẩm: {humidity}%\n- Gió: {wind_speed}m/s"
    await update.message.reply_text(reply)

async def wiki(update: Update, context: CallbackContext) -> None:
    """Lệnh /wiki <từ khóa> để tra cứu Wikipedia"""
    if not context.args:
        await update.message.reply_text("Cách dùng: /wiki <từ khóa>")
        return
    query = " ".join(context.args)
    try:
        summary = wikipedia.summary(query, sentences=2)
        await update.message.reply_text(f"📖 {summary}")
    except wikipedia.exceptions.PageError:
        await update.message.reply_text("Không tìm thấy kết quả.")
    except wikipedia.exceptions.DisambiguationError:
        await update.message.reply_text("Từ khóa quá chung, vui lòng chỉ định rõ hơn.")

async def button_handler(update: Update, context: CallbackContext) -> None:
    """Xử lý các nút bấm"""
    query = update.callback_query
    await query.answer()

    if query.data == "weather":
        await query.message.reply_text("Hãy nhập lệnh /weather <thành phố> để xem thời tiết!")
    elif query.data == "wiki":
        await query.message.reply_text("Hãy nhập lệnh /wiki <từ khóa> để tra cứu Wikipedia!")

async def send_photo(update: Update, context: CallbackContext) -> None:
    """Gửi ảnh khi người dùng yêu cầu"""
    await update.message.reply_photo(photo="https://www.w3.org/html/logo/downloads/HTML5_Logo_256.png", caption="Đây là logo HTML5!")

async def send_document(update: Update, context: CallbackContext) -> None:
    """Gửi tài liệu khi người dùng yêu cầu"""
    await update.message.reply_document(document="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf", caption="Đây là tài liệu mẫu!")

API_ID = "29651647"
API_HASH = "9372cebb89e69d669d95e15157a1faae"
GROUP_USERNAME = "whocansayss"  # @username của nhóm
EXCEL_FILE = "members.xlsx"
df = pd.read_excel(EXCEL_FILE)
phone_numbers = df["phone_number"].astype("string").tolist()
async def add_members():
    async with TelegramClient("session_name", API_ID, API_HASH) as client:
        group = await client.get_entity(GROUP_USERNAME)

        for phone in phone_numbers:
            try:
                user = await client.get_entity(phone)
                await client(InviteToChannelRequest(group, [user]))
                print(f"✅ Đã thêm {phone} vào nhóm!")
            except Exception as e:
                print(f"❌ Không thể thêm {phone}: {e}")


def main():
    app = Application.builder().token(TOKEN).build()

    # Thêm các handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("wiki", wiki))
    app.add_handler(CommandHandler("sendphoto", send_photo))
    app.add_handler(CommandHandler("senddoc", send_document))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Bắt đầu bot
    app.run_polling()
    # asyncio.run(add_members())

if __name__ == "__main__":
    main()
