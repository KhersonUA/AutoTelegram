import os
import re
from urllib.parse import quote

import requests
from dotenv import load_dotenv


load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
FACEBOOK_TASK_ID = os.getenv("FACEBOOK_TASK_ID")
APIFY_API = "https://api.apify.com/v2"


def headers():
    return {
        "Authorization": f"Bearer {APIFY_TOKEN}",
        "Content-Type": "application/json",
    }


def ensure_configuration():
    if not APIFY_TOKEN:
        raise RuntimeError(
            "APIFY_TOKEN не найден в переменных окружения."
        )

    if not FACEBOOK_TASK_ID:
        raise RuntimeError(
            "FACEBOOK_TASK_ID не найден в переменных окружения."
        )


def run_task_and_get_items():
    task_id = quote(FACEBOOK_TASK_ID, safe="~")

    url = (
        f"{APIFY_API}/actor-tasks/{task_id}/"
        "run-sync-get-dataset-items"
        "?format=json"
        "&clean=true"
    )

    print(
        "Запускаю Facebook Marketplace Task "
        "и жду готовый Dataset..."
    )

    response = requests.post(
        url,
        headers=headers(),
        json={},
        timeout=720,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        print(
            "Apify вернул ошибку при запуске "
            "Facebook Task."
        )
        print(f"HTTP status: {response.status_code}")
        print(response.text[:2000])
        raise RuntimeError(
            "Не удалось запустить Facebook Task "
            "или получить Dataset."
        ) from error

    try:
        items = response.json()
    except ValueError as error:
        print("Apify вернул ответ не в формате JSON.")
        print(response.text[:2000])
        raise RuntimeError(
            "Facebook Dataset имеет неправильный формат."
        ) from error

    if not isinstance(items, list):
        print(f"Неожиданный ответ Apify: {items}")
        raise RuntimeError(
            "Facebook Dataset имеет неожиданный формат."
        )

    print(
        "Из Facebook Dataset получено: "
        f"{len(items)}"
    )

    return items


def nested(data, *keys):
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def text(value, default=None):
    if value is None:
        return default

    value = str(value).strip()

    return value if value else default


def format_price(item):
    amount = nested(
        item,
        "listing_price",
        "amount",
    )
    currency = nested(
        item,
        "listing_price",
        "currency",
    )

    if amount:
        try:
            number = float(amount)

            shown = (
                f"{int(number):,}"
                if number.is_integer()
                else f"{number:,.2f}"
            ).replace(",", " ")

            return (
                f"{shown} {currency}"
                if currency
                else shown
            )

        except (TypeError, ValueError):
            pass

    return text(
        nested(
            item,
            "formatted_price",
            "text",
        ),
        "Цена не указана",
    )


def extract_year(item, title):
    if item.get("vehicle_year"):
        return str(item["vehicle_year"])

    match = re.search(
        r"\b(19\d{2}|20\d{2})\b",
        title or "",
    )

    return match.group(1) if match else None


def translate_fuel(value):
    return {
        "GASOLINE": "Бензин",
        "DIESEL": "Дизель",
        "ELECTRIC": "Электро",
        "HYBRID": "Гибрид",
        "FLEX": "Flex fuel",
        "OTHER": "Другое",
    }.get(value, value)


def translate_gearbox(value):
    return {
        "MANUAL": "Механическая",
        "AUTOMATIC": "Автоматическая",
        "OTHER": "Другая",
    }.get(value, value)


def normalize_item(item):
    title = text(
        item.get("marketplace_listing_title"),
        text(
            item.get("custom_title"),
            "Название не указано",
        ),
    )

    listing_id = text(item.get("id"))

    url = text(
        item.get("listingUrl"),
        text(item.get("share_uri")),
    )

    if not url and listing_id:
        url = (
            "https://www.facebook.com/"
            f"marketplace/item/{listing_id}"
        )

    if not url:
        return None

    mileage_value = nested(
        item,
        "vehicle_odometer_data",
        "value",
    )
    mileage_unit = nested(
        item,
        "vehicle_odometer_data",
        "unit",
    )

    mileage = None

    if mileage_value is not None:
        try:
            mileage = (
                f"{int(float(mileage_value)):,}"
                .replace(",", " ")
            )

            if mileage_unit == "KILOMETERS":
                mileage += " km"
            elif mileage_unit:
                mileage += f" {mileage_unit}"

        except (TypeError, ValueError):
            mileage = str(mileage_value)

    return {
        "title": title,
        "url": url,
        "price": format_price(item),
        "image_url": text(
            item.get("primary_listing_photo_url"),
            nested(
                item,
                "primary_listing_photo",
                "image",
                "uri",
            ),
        ),
        "year": extract_year(item, title),
        "mileage": mileage,
        "fuel": translate_fuel(
            text(item.get("vehicle_fuel_type"))
        ),
        "gearbox": translate_gearbox(
            text(
                item.get(
                    "vehicle_transmission_type"
                )
            )
        ),
        "location": text(
            nested(
                item,
                "location_text",
                "text",
            ),
            "Gorzów Wielkopolski",
        ),
        "source": "Facebook Marketplace",
        "creation_time": (
            item.get("creation_time") or 0
        ),
    }


def collect_facebook_adverts():
    ensure_configuration()

    items = run_task_and_get_items()

    adverts = []

    for item in items:
        if not isinstance(item, dict):
            continue

        if (
            item.get("is_live") is False
            or item.get("is_sold") is True
        ):
            continue

        advert = normalize_item(item)

        if advert:
            adverts.append(advert)

    adverts.sort(
        key=lambda advert: advert.get(
            "creation_time",
            0,
        ),
        reverse=True,
    )

    print(
        "Подготовлено объявлений Facebook: "
        f"{len(adverts)}"
    )

    return adverts
