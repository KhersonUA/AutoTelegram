from database import (
    advert_exists,
    create_database,
    database_is_empty,
    get_setting,
    save_advert,
    set_setting,
)
from facebook_parser import collect_facebook_adverts
from parser import collect_adverts, load_adverts_details
from telegram_sender import send_advert

FACEBOOK_INITIALIZED_KEY = "facebook_initialized"


def save_initial_adverts(adverts):
    print("Первый запуск OLX/Otomoto.")
    print("Сохраняю текущие объявления без отправки в Telegram.")
    for advert in adverts:
        save_advert(advert["title"], advert["url"])
    print(f"Сохранено объявлений: {len(adverts)}")


def initialize_facebook(adverts):
    print("Первое подключение Facebook.")
    print("Сохраняю найденные объявления без массовой отправки.")
    saved_count = 0
    for advert in adverts:
        if advert_exists(advert["url"]):
            continue
        save_advert(advert["title"], advert["url"])
        saved_count += 1
    set_setting(FACEBOOK_INITIALIZED_KEY, "1")
    print(f"Первичная база Facebook подготовлена. Сохранено: {saved_count}")
    print("Со следующего запуска будут приходить только новые Facebook-объявления.")


def find_new_adverts(adverts):
    return [advert for advert in adverts if not advert_exists(advert["url"])]


def send_new_adverts(adverts):
    sent_count = 0
    for advert in reversed(adverts):
        print("-" * 60)
        print(f"Новое объявление: {advert['title']}")
        print(f"Источник: {advert.get('source')}")
        sent = send_advert(
            title=advert["title"],
            url=advert["url"],
            price=advert.get("price"),
            image_url=advert.get("image_url"),
            year=advert.get("year"),
            mileage=advert.get("mileage"),
            fuel=advert.get("fuel"),
            gearbox=advert.get("gearbox"),
            source=advert.get("source"),
            location=advert.get("location"),
        )
        if not sent:
            print("Объявление не сохранено: отправка не удалась.")
            continue
        save_advert(advert["title"], advert["url"])
        sent_count += 1
    return sent_count


def process_olx_and_otomoto():
    print("=" * 60)
    print("OLX / Otomoto")
    print("=" * 60)
    try:
        adverts = collect_adverts()
    except Exception as error:
        print(f"Ошибка OLX/Otomoto: {error}")
        return 0
    if not adverts:
        print("Объявления OLX/Otomoto не найдены.")
        return 0
    if database_is_empty():
        save_initial_adverts(adverts)
        return 0
    new_adverts = find_new_adverts(adverts)
    print(f"Найдено новых OLX/Otomoto: {len(new_adverts)}")
    if not new_adverts:
        return 0
    load_adverts_details(new_adverts)
    for advert in new_adverts:
        advert.setdefault("source", "OLX / Otomoto")
        advert.setdefault("location", "Gorzów Wielkopolski")
    return send_new_adverts(new_adverts)


def process_facebook():
    print("=" * 60)
    print("Facebook Marketplace")
    print("=" * 60)
    try:
        adverts = collect_facebook_adverts()
    except Exception as error:
        print(f"Ошибка Facebook Marketplace: {error}")
        return 0
    if not adverts:
        print("Объявления Facebook не найдены.")
        return 0
    if get_setting(FACEBOOK_INITIALIZED_KEY) != "1":
        initialize_facebook(adverts)
        return 0
    new_adverts = find_new_adverts(adverts)
    print(f"Найдено новых Facebook: {len(new_adverts)}")
    if not new_adverts:
        return 0
    return send_new_adverts(new_adverts)


def main():
    print("Запуск AutoTelegram")
    print("-" * 60)
    create_database()
    olx_sent = process_olx_and_otomoto()
    facebook_sent = process_facebook()
    print("=" * 60)
    print(
        f"Итог: OLX/Otomoto — {olx_sent}, Facebook — {facebook_sent}"
    )


if __name__ == "__main__":
    main()
