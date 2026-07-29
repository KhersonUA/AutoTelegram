import os
import re
import time
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
FACEBOOK_TASK_ID = os.getenv("FACEBOOK_TASK_ID")
APIFY_API = "https://api.apify.com/v2"
FINISHED_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


def headers():
    return {
        "Authorization": f"Bearer {APIFY_TOKEN}",
        "Content-Type": "application/json",
    }


def ensure_configuration():
    if not APIFY_TOKEN:
        raise RuntimeError("APIFY_TOKEN не найден в переменных окружения.")
    if not FACEBOOK_TASK_ID:
        raise RuntimeError("FACEBOOK_TASK_ID не найден в переменных окружения.")


def start_task():
    task_id = quote(FACEBOOK_TASK_ID, safe="~")
    url = (
        f"{APIFY_API}/actor-tasks/{task_id}/runs"
        "?maxItems=100&maxTotalChargeUsd=2"
    )
    print("Запускаю Facebook Marketplace Task...")
    response = requests.post(url, headers=headers(), json={}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    run_id = (payload.get("data") or {}).get("id")
    if not run_id:
        raise RuntimeError(f"Apify не вернул ID запуска: {payload}")
    print(f"Facebook Task запущен. Run ID: {run_id}")
    return run_id


def wait_for_run(run_id, max_wait_seconds=720):
    deadline = time.monotonic() + max_wait_seconds
    while time.monotonic() < deadline:
        response = requests.get(
            f"{APIFY_API}/actor-runs/{run_id}?waitForFinish=60",
            headers=headers(),
            timeout=75,
        )
        response.raise_for_status()
        run = (response.json().get("data") or {})
        status = run.get("status")
        print(f"Статус Facebook Task: {status}")
        if status in FINISHED_STATUSES:
            if status != "SUCCEEDED":
                raise RuntimeError(
                    f"Facebook Task завершился со статусом {status}: "
                    f"{run.get('statusMessage')}"
                )
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                raise RuntimeError("Apify не вернул defaultDatasetId.")
            return dataset_id
        time.sleep(2)
    raise TimeoutError("Facebook Task не завершился за 12 минут.")


def get_dataset_items(dataset_id):
    response = requests.get(
        f"{APIFY_API}/datasets/{dataset_id}/items"
        "?format=json&clean=true&limit=100",
        headers=headers(),
        timeout=90,
    )
    response.raise_for_status()
    items = response.json()
    if not isinstance(items, list):
        raise RuntimeError("Dataset имеет неожиданный формат.")
    print(f"Из Facebook Dataset получено: {len(items)}")
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
    amount = nested(item, "listing_price", "amount")
    currency = nested(item, "listing_price", "currency")
    if amount:
        try:
            number = float(amount)
            shown = (
                f"{int(number):,}" if number.is_integer()
                else f"{number:,.2f}"
            ).replace(",", " ")
            return f"{shown} {currency}" if currency else shown
        except (TypeError, ValueError):
            pass
    return text(nested(item, "formatted_price", "text"), "Цена не указана")


def extract_year(item, title):
    if item.get("vehicle_year"):
        return str(item["vehicle_year"])
    match = re.search(r"\b(19\d{2}|20\d{2})\b", title or "")
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
        text(item.get("custom_title"), "Название не указано"),
    )
    listing_id = text(item.get("id"))
    url = text(item.get("listingUrl"), text(item.get("share_uri")))
    if not url and listing_id:
        url = f"https://www.facebook.com/marketplace/item/{listing_id}"
    if not url:
        return None

    mileage_value = nested(item, "vehicle_odometer_data", "value")
    mileage_unit = nested(item, "vehicle_odometer_data", "unit")
    mileage = None
    if mileage_value is not None:
        try:
            mileage = f"{int(float(mileage_value)):,}".replace(",", " ")
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
            nested(item, "primary_listing_photo", "image", "uri"),
        ),
        "year": extract_year(item, title),
        "mileage": mileage,
        "fuel": translate_fuel(text(item.get("vehicle_fuel_type"))),
        "gearbox": translate_gearbox(text(item.get("vehicle_transmission_type"))),
        "location": text(
            nested(item, "location_text", "text"),
            "Gorzów Wielkopolski",
        ),
        "source": "Facebook Marketplace",
        "creation_time": item.get("creation_time") or 0,
    }


def collect_facebook_adverts():
    ensure_configuration()
    run_id = start_task()
    dataset_id = wait_for_run(run_id)
    items = get_dataset_items(dataset_id)

    adverts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("is_live") is False or item.get("is_sold") is True:
            continue
        advert = normalize_item(item)
        if advert:
            adverts.append(advert)

    adverts.sort(key=lambda x: x.get("creation_time", 0), reverse=True)
    print(f"Подготовлено объявлений Facebook: {len(adverts)}")
    return adverts
