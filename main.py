import logging
import os
from typing import Any

import pandas as pd
import requests
import wikipedia
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telethon import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest

# Cấu hình logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Cấu hình từ biến môi trường
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "").strip()
API_ID = os.getenv("TELETHON_API_ID", "").strip()
API_HASH = os.getenv("TELETHON_API_HASH", "").strip()
GROUP_USERNAME = os.getenv("TARGET_GROUP_USERNAME", "whocansayss").strip()
EXCEL_FILE = os.getenv("MEMBERS_EXCEL_FILE", "members.xlsx").strip()
SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "session_name").strip()

PHOTO_URL = "https://www.w3.org/html/logo/downloads/HTML5_Logo_256.png"
DOCUMENT_URL = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"

wikipedia.set_lang("vi")


async def start(update: Update, context: CallbackContext) -> None:
    if not update.message:
        return
    keyboard = [
        [InlineKeyboardButton("Xem thời tiết", callback_data="weather")],
        [InlineKeyboardButton("Tìm kiếm Wikipedia", callback_data="wiki")],
        [InlineKeyboardButton("Xem trợ giúp", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Chào bạn! Tôi là bot Telegram.\nHãy chọn chức năng:",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: CallbackContext) -> None:
    if not update.message:
        return
    message = (
        "Các lệnh hỗ trợ:\n"
        "/start - Mở menu chức năng\n"
        "/help - Xem trợ giúp\n"
        "/weather <thành phố> - Xem thời tiết\n"
        "/wiki <từ khóa> - Tra cứu Wikipedia\n"
        "/remind <giây> <nội dung> - Đặt nhắc nhở\n"
        "/sendphoto - Gửi ảnh mẫu\n"
        "/senddoc - Gửi tài liệu mẫu\n"
        "/addmembers - Thêm thành viên từ file Excel (yêu cầu cấu hình Telethon)"
    )
    await update.message.reply_text(message)


async def echo(update: Update, context: CallbackContext) -> None:
    if update.message and update.message.text:
        await update.message.reply_text(update.message.text)


async def remind(update: Update, context: CallbackContext) -> None:
    """Lệnh /remind <thời gian> <nội dung> để đặt nhắc nhở."""
    if not update.message:
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Cách dùng: /remind <thời gian (giây)> <nội dung>")
        return

    try:
        seconds = int(args[0])
        if seconds <= 0:
            await update.message.reply_text("Thời gian phải lớn hơn 0 giây.")
            return
        text = " ".join(args[1:])
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id is None:
            await update.message.reply_text("Không xác định được chat để nhắc nhở.")
            return

        context.job_queue.run_once(
            send_reminder_job,
            when=seconds,
            data={"chat_id": chat_id, "text": text},
            name=f"reminder_{chat_id}_{update.message.message_id}",
        )

        await update.message.reply_text(f"Đã đặt nhắc nhở: {text} sau {seconds} giây.")
    except ValueError:
        await update.message.reply_text("Thời gian phải là số nguyên.")


async def send_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data or {}
    chat_id = data.get("chat_id")
    text = data.get("text", "(không có nội dung)")
    if chat_id is not None:
        await context.bot.send_message(chat_id=chat_id, text=f"🔔 Nhắc nhở: {text}")


def _fetch_weather(city: str, api_key: str) -> dict[str, Any]:
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={api_key}&units=metric&lang=vi"
    )
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


async def weather(update: Update, context: CallbackContext) -> None:
    """Lệnh /weather <thành phố> để xem thời tiết."""
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Cách dùng: /weather <thành phố>")
        return
    if not WEATHER_API_KEY:
        await update.message.reply_text(
            "Chưa cấu hình API thời tiết. Hãy đặt biến môi trường OPENWEATHER_API_KEY."
        )
        return

    city = " ".join(context.args)
    try:
        response = await context.application.run_in_executor(
            None,
            _fetch_weather,
            city,
            WEATHER_API_KEY,
        )
    except requests.HTTPError:
        await update.message.reply_text("Không tìm thấy thành phố hoặc API key không hợp lệ.")
        return
    except requests.RequestException as exc:
        logger.error("Lỗi gọi API thời tiết: %s", exc)
        await update.message.reply_text("Không thể lấy dữ liệu thời tiết lúc này. Vui lòng thử lại.")
        return

    if str(response.get("cod")) != "200":
        await update.message.reply_text("Không tìm thấy thành phố!")
        return

    weather_desc = response["weather"][0]["description"]
    temp = response["main"]["temp"]
    humidity = response["main"]["humidity"]
    wind_speed = response["wind"]["speed"]

    reply = (
        f"🌤 Thời tiết tại {city}:\n"
        f"- {weather_desc.capitalize()}\n"
        f"- Nhiệt độ: {temp}°C\n"
        f"- Độ ẩm: {humidity}%\n"
        f"- Gió: {wind_speed}m/s"
    )
    await update.message.reply_text(reply)


def _wiki_summary(query: str) -> str:
    return wikipedia.summary(query, sentences=2)


async def wiki(update: Update, context: CallbackContext) -> None:
    """Lệnh /wiki <từ khóa> để tra cứu Wikipedia."""
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Cách dùng: /wiki <từ khóa>")
        return
    query = " ".join(context.args)
    try:
        summary = await context.application.run_in_executor(None, _wiki_summary, query)
        await update.message.reply_text(f"📖 {summary}")
    except wikipedia.exceptions.PageError:
        await update.message.reply_text("Không tìm thấy kết quả.")
    except wikipedia.exceptions.DisambiguationError as exc:
        options = ", ".join(exc.options[:5])
        await update.message.reply_text(
            f"Từ khóa quá chung, bạn có thể thử một trong các mục: {options}"
        )
    except Exception as exc:
        logger.error("Lỗi khi tra cứu Wikipedia: %s", exc)
        await update.message.reply_text("Không thể tra cứu Wikipedia lúc này.")


async def button_handler(update: Update, context: CallbackContext) -> None:
    """Xử lý các nút bấm."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if query.data == "weather":
        await query.message.reply_text("Hãy nhập lệnh /weather <thành phố> để xem thời tiết!")
    elif query.data == "wiki":
        await query.message.reply_text("Hãy nhập lệnh /wiki <từ khóa> để tra cứu Wikipedia!")
    elif query.data == "help":
        await query.message.reply_text("Gõ /help để xem toàn bộ lệnh hiện có.")


async def send_photo(update: Update, context: CallbackContext) -> None:
    """Gửi ảnh khi người dùng yêu cầu."""
    if update.message:
        await update.message.reply_photo(
            photo=PHOTO_URL,
            caption="Đây là logo HTML5!",
        )


async def send_document(update: Update, context: CallbackContext) -> None:
    """Gửi tài liệu khi người dùng yêu cầu."""
    if update.message:
        await update.message.reply_document(
            document=DOCUMENT_URL,
            caption="Đây là tài liệu mẫu!",
        )


def load_phone_numbers(excel_file: str) -> list[str]:
    if not os.path.exists(excel_file):
        logger.warning("Không tìm thấy file danh sách thành viên: %s", excel_file)
        return []
    try:
        df = pd.read_excel(excel_file)
    except Exception as exc:
        logger.error("Không thể đọc file Excel: %s", exc)
        return []
    if "phone_number" not in df.columns:
        logger.error("Thiếu cột 'phone_number' trong file Excel.")
        return []
    return [phone for phone in df["phone_number"].astype("string").tolist() if phone]


async def add_members_to_group() -> tuple[int, int]:
    if not API_ID or not API_HASH:
        raise ValueError("Thiếu TELETHON_API_ID hoặc TELETHON_API_HASH.")

    phone_numbers = load_phone_numbers(EXCEL_FILE)
    if not phone_numbers:
        return 0, 0

    success_count = 0
    fail_count = 0

    async with TelegramClient(SESSION_NAME, int(API_ID), API_HASH) as client:
        group = await client.get_entity(GROUP_USERNAME)

        for phone in phone_numbers:
            try:
                user = await client.get_entity(phone)
                await client(InviteToChannelRequest(group, [user]))
                success_count += 1
                logger.info("Đã thêm %s vào nhóm.", phone)
            except Exception as exc:
                fail_count += 1
                logger.warning("Không thể thêm %s: %s", phone, exc)

    return success_count, fail_count


async def add_members_command(update: Update, context: CallbackContext) -> None:
    if not update.message:
        return
    await update.message.reply_text("Đang xử lý thêm thành viên, vui lòng đợi...")
    try:
        success_count, fail_count = await add_members_to_group()
        await update.message.reply_text(
            f"Hoàn tất thêm thành viên.\n- Thành công: {success_count}\n- Thất bại: {fail_count}"
        )
    except ValueError as exc:
        await update.message.reply_text(str(exc))
    except Exception as exc:
        logger.exception("Lỗi khi thêm thành viên: %s", exc)
        await update.message.reply_text(
            "Không thể thêm thành viên lúc này. Kiểm tra lại session và thông tin cấu hình."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception: %s", context.error)


def validate_config() -> None:
    if not TOKEN:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN. Hãy đặt biến môi trường trước khi chạy bot.")


def main() -> None:
    validate_config()
    app = Application.builder().token(TOKEN).build()

    # Thêm các handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("wiki", wiki))
    app.add_handler(CommandHandler("sendphoto", send_photo))
    app.add_handler(CommandHandler("senddoc", send_document))
    app.add_handler(CommandHandler("addmembers", add_members_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    # Bắt đầu bot
    logger.info("Bot đang khởi động...")
    app.run_polling()


if __name__ == "__main__":
    main()
