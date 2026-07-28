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

    if not value:
        return default

    return html.escape(value)


def build_message(
    title,
    url,
    price,
    year,
    mileage,
    fuel,
    gearbox,
):
    safe_title = safe_text(
        title,
        "Название не указано",
    )

    safe_url = html.escape(
        url,
        quote=True,
    )

    return (
        f"🚗 <b>{safe_title}</b>\n\n"
        f"💰 {safe_text(price, 'Цена не указана')}\n"
        f"📅 {safe_text(year)}\n"
        f"🛣️ {safe_text(mileage)}\n"
        f"⛽ {safe_text(fuel)}\n"
        f"⚙️ {safe_text(gearbox)}\n"
        f"📍 Gorzów Wielkopolski\n\n"
        f'🔗 <a href="{safe_url}">'
        f"Открыть объявление</a>"
    )


def send_text_message(message):
    telegram_url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        telegram_url,
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
    if not image_url:
        return None

    if not image_url.startswith(
        ("http://", "https://")
    ):
        return None

    try:
        response = requests.get(
            image_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            },
            timeout=30,
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            "",
        ).lower()

        if "image" not in content_type:
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

    telegram_url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendPhoto"
    )

    try:
        response = requests.post(
            telegram_url,
            data={
                "chat_id": CHAT_ID,
                "caption": message,
                "parse_mode": "HTML",
            },
            files={
                "photo": (
                    image.name,
                    image,
                    "image/jpeg",
                )
            },
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


def send_advert(
    title,
    url,
    price="Цена не указана",
    image_url=None,
    year=None,
    mileage=None,
    fuel=None,
    gearbox=None,
):
    if not BOT_TOKEN:
        print("Ошибка: BOT_TOKEN не найден в .env")
        return False

    if not CHAT_ID:
        print("Ошибка: CHAT_ID не найден в .env")
        return False

    message = build_message(
        title=title,
        url=url,
        price=price,
        year=year,
        mileage=mileage,
        fuel=fuel,
        gearbox=gearbox,
    )

    # Подпись к фото Telegram ограничена.
    # Наше сообщение короткое, но оставляем страховку.
    if len(message) <= 950 and image_url:
        if send_photo_message(
            message,
            image_url,
        ):
            print(f"Отправлено с фотографией: {title}")
            return True

        print("Фотография не отправилась.")
        print("Пробую отправить обычное сообщение.")

    if send_text_message(message):
        print(f"Отправлено без фотографии: {title}")
        return True

    return False


if __name__ == "__main__":
    send_advert(
        title="Тест автомобиля",
        url="https://www.olx.pl/",
        price="25 000 zł",
        year="2022",
        mileage="126 000 km",
        fuel="Hybryda",
        gearbox="Automatyczna",
        image_url=None,
    )