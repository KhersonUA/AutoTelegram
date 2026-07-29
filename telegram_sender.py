import html
import os
from io import BytesIO

import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


def safe_text(value, default="Не указано"):
    if value is None:
        return default
    value = str(value).strip()
    return html.escape(value) if value else default


def build_message(title, url, price, year, mileage, fuel, gearbox,
                  source=None, location=None):
    safe_title = safe_text(title, "Название не указано")
    safe_url = html.escape(url, quote=True)
    source_line = f"🌐 {safe_text(source)}\n" if source else ""
    location_line = (
        f"📍 {safe_text(location)}\n"
        if location else "📍 Gorzów Wielkopolski\n"
    )
    return (
        f"🚗 <b>{safe_title}</b>\n\n"
        f"{source_line}"
        f"💰 {safe_text(price, 'Цена не указана')}\n"
        f"📅 {safe_text(year)}\n"
        f"🛣️ {safe_text(mileage)}\n"
        f"⛽ {safe_text(fuel)}\n"
        f"⚙️ {safe_text(gearbox)}\n"
        f"{location_line}\n"
        f'<a href="{safe_url}">🔗 Открыть объявление</a>'
    )


def send_text_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    try:
        result = response.json()
    except ValueError:
        print("Telegram вернул неправильный ответ.")
        print(response.text)
        return False
    if result.get("ok"):
        return True
    print("Ошибка Telegram при отправке сообщения:")
    print(result)
    return False


def download_image(image_url):
    if not image_url or not image_url.startswith(("http://", "https://")):
        return None
    try:
        response = requests.get(
            image_url,
            headers={"User-Agent": "Mozilla/5.0 Chrome/120.0"},
            timeout=30,
        )
        response.raise_for_status()
        if "image" not in response.headers.get("Content-Type", "").lower():
            return None
        if not response.content:
            return None
        image = BytesIO(response.content)
        image.name = "car.jpg"
        return image
    except requests.RequestException as error:
        print(f"Не удалось скачать фото: {error}")
        return None


def send_photo_message(message, image_url):
    image = download_image(image_url)
    if image is None:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "caption": message,
                "parse_mode": "HTML",
            },
            files={"photo": (image.name, image, "image/jpeg")},
            timeout=60,
        )
        result = response.json()
        if result.get("ok"):
            return True
        print("Ошибка Telegram при отправке фото:")
        print(result)
        return False
    except requests.RequestException as error:
        print(f"Ошибка отправки фотографии: {error}")
        return False
    finally:
        image.close()


def send_advert(title, url, price="Цена не указана", image_url=None,
                year=None, mileage=None, fuel=None, gearbox=None,
                source=None, location=None):
    if not BOT_TOKEN:
        print("Ошибка: BOT_TOKEN не найден в переменных окружения.")
        return False
    if not CHAT_ID:
        print("Ошибка: CHAT_ID не найден в переменных окружения.")
        return False

    message = build_message(
        title, url, price, year, mileage, fuel, gearbox,
        source=source, location=location,
    )

    if len(message) <= 950 and image_url:
        if send_photo_message(message, image_url):
            print(f"Отправлено с фотографией: {title}")
            return True
        print("Фотография не отправилась. Пробую обычное сообщение.")

    if send_text_message(message):
        print(f"Отправлено без фотографии: {title}")
        return True
    return False
