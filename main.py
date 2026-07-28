from database import (
    advert_exists,
    create_database,
    database_is_empty,
    save_advert,
)
from parser import (
    collect_adverts,
    load_adverts_details,
)
from telegram_sender import send_advert


def save_initial_adverts(adverts):
    print("Первый запуск.")
    print(
        "Сохраняю текущие объявления "
        "без отправки в Telegram."
    )

    saved_count = 0

    for advert in adverts:
        save_advert(
            advert["title"],
            advert["url"],
        )

        saved_count += 1

    print(f"Сохранено объявлений: {saved_count}")
    print(
        "На следующих запусках будут "
        "отправляться только новые."
    )


def find_new_adverts(adverts):
    new_adverts = []

    for advert in adverts:
        if not advert_exists(advert["url"]):
            new_adverts.append(advert)

    return new_adverts


def send_new_adverts(adverts):
    sent_count = 0

    # Старые из новых отправляются первыми.
    for advert in reversed(adverts):
        print("-" * 60)
        print(f"Новое объявление: {advert['title']}")
        print(f"Цена: {advert.get('price')}")
        print(f"Год: {advert.get('year')}")
        print(f"Пробег: {advert.get('mileage')}")
        print(f"Топливо: {advert.get('fuel')}")
        print(f"Коробка: {advert.get('gearbox')}")

        sent = send_advert(
            title=advert["title"],
            url=advert["url"],
            price=advert.get("price"),
            image_url=advert.get("image_url"),
            year=advert.get("year"),
            mileage=advert.get("mileage"),
            fuel=advert.get("fuel"),
            gearbox=advert.get("gearbox"),
        )

        if not sent:
            print(
                "Объявление не сохранено: "
                "отправка не удалась."
            )
            continue

        save_advert(
            advert["title"],
            advert["url"],
        )

        sent_count += 1

    return sent_count


def main():
    print("Запуск AutoTelegram")
    print("-" * 60)

    create_database()

    adverts = collect_adverts()

    if not adverts:
        print("Объявления не найдены.")
        return

    if database_is_empty():
        save_initial_adverts(adverts)
        return

    new_adverts = find_new_adverts(adverts)

    print(
        f"Найдено новых объявлений: "
        f"{len(new_adverts)}"
    )

    if not new_adverts:
        print("Новых объявлений нет.")
        return

    # Открываем страницы только новых объявлений.
    load_adverts_details(new_adverts)

    sent_count = send_new_adverts(new_adverts)

    print("-" * 60)
    print(
        f"Новых объявлений отправлено: "
        f"{sent_count}"
    )


if __name__ == "__main__":
    main()