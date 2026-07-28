import re
from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright


SEARCH_URL = (
    "https://www.olx.pl/motoryzacja/samochody/gorzow/"
    "?search%5Border%5D=created_at:desc"
)

COOKIE_BUTTONS = [
    "Akceptuję",
    "Akceptuj wszystkie",
    "Zgadzam się",
]


# ============================================================
# ОБЩИЕ ФУНКЦИИ
# ============================================================

def normalize_text(value):
    if value is None:
        return None

    value = re.sub(r"\s+", " ", str(value)).strip()

    return value or None


def valid_http_url(url):
    if not url:
        return None

    url = str(url).strip()

    if url.startswith("//"):
        url = "https:" + url

    parts = urlsplit(url)

    if parts.scheme not in ("http", "https"):
        return None

    if not parts.netloc:
        return None

    return url


def clean_url(url):
    if not url:
        return None

    absolute_url = urljoin(
        "https://www.olx.pl",
        url,
    )

    parts = urlsplit(absolute_url)

    if parts.scheme not in ("http", "https"):
        return None

    if not parts.netloc:
        return None

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            "",
            "",
        )
    )


def safe_inner_text(locator, default=None):
    try:
        if locator.count() == 0:
            return default

        text = locator.first.inner_text(
            timeout=3000,
        )

        return normalize_text(text) or default

    except Exception:
        return default


def close_cookies(page):
    for button_text in COOKIE_BUTTONS:
        try:
            page.get_by_role(
                "button",
                name=re.compile(
                    re.escape(button_text),
                    re.IGNORECASE,
                ),
            ).first.click(timeout=1500)

            print("Окно cookies закрыто.")
            return

        except Exception:
            pass


def get_meta_content(page, selector):
    try:
        return page.locator(
            selector
        ).first.get_attribute(
            "content",
            timeout=3000,
        )

    except Exception:
        return None


# ============================================================
# СПИСОК ОБЪЯВЛЕНИЙ
# ============================================================

def extract_price(card):
    selectors = [
        '[data-testid="ad-price"]',
        "p:has-text('zł')",
        "span:has-text('zł')",
    ]

    for selector in selectors:
        text = safe_inner_text(
            card.locator(selector)
        )

        if not text:
            continue

        match = re.search(
            r"\d[\d\s.,]*\s*zł",
            text,
            re.IGNORECASE,
        )

        if match:
            return normalize_text(
                match.group(0)
            )

    return "Цена не указана"


def extract_image_url(card, page_url):
    try:
        images = card.locator("img")
        image_count = min(images.count(), 5)

        for index in range(image_count):
            image = images.nth(index)

            candidates = [
                image.get_attribute("src"),
                image.get_attribute("data-src"),
                image.get_attribute("data-original"),
            ]

            srcset = image.get_attribute("srcset")

            if srcset:
                srcset_items = srcset.split(",")

                for item in reversed(srcset_items):
                    candidate = (
                        item.strip()
                        .split(" ")[0]
                        .strip()
                    )

                    if candidate:
                        candidates.append(candidate)

            for candidate in candidates:
                if not candidate:
                    continue

                if candidate.startswith("data:"):
                    continue

                absolute_url = urljoin(
                    page_url,
                    candidate,
                )

                absolute_url = valid_http_url(
                    absolute_url
                )

                if absolute_url:
                    return absolute_url

    except Exception:
        pass

    return None


def collect_adverts():
    adverts = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
        )

        context = browser.new_context(
            locale="pl-PL",
            viewport={
                "width": 1400,
                "height": 900,
            },
        )

        page = context.new_page()

        print(
            "Открываю объявления "
            "по Gorzów Wielkopolski..."
        )

        page.goto(
            SEARCH_URL,
            wait_until="domcontentloaded",
            timeout=30_000,
        )

        page.wait_for_timeout(4000)
        close_cookies(page)

        cards = page.locator(
            '[data-cy="l-card"]'
        )

        count = cards.count()

        print(f"Найдено карточек: {count}")

        used_urls = set()

        for index in range(count):
            card = cards.nth(index)

            title = safe_inner_text(
                card.locator("h4"),
                default="Название не найдено",
            )

            try:
                raw_url = (
                    card.locator("a")
                    .first
                    .get_attribute("href")
                )
            except Exception:
                raw_url = None

            url = clean_url(raw_url)

            if not url:
                continue

            if url in used_urls:
                continue

            used_urls.add(url)

            advert = {
                "title": title,
                "url": url,
                "price": extract_price(card),
                "image_url": extract_image_url(
                    card,
                    page.url,
                ),
                "year": None,
                "mileage": None,
                "fuel": None,
                "gearbox": None,
            }

            adverts.append(advert)

        browser.close()

    print(
        f"Получено объявлений: "
        f"{len(adverts)}"
    )

    return adverts


# ============================================================
# OTOMOTO
# ============================================================

def wait_for_otomoto_summary(page):
    """
    Ждём появления блока характеристик под фотографиями.
    """

    labels = [
        "Przebieg",
        "Rodzaj paliwa",
        "Skrzynia biegów",
    ]

    for label in labels:
        try:
            locator = page.get_by_text(
                label,
                exact=True,
            ).first

            locator.wait_for(
                state="attached",
                timeout=7000,
            )

            locator.scroll_into_view_if_needed(
                timeout=3000,
            )

            page.wait_for_timeout(500)
            return True

        except Exception:
            continue

    return False


def get_otomoto_value(page, label):
    """
    Реальная структура Otomoto:

    <div class="flex w-full flex-col">
        <p>Przebieg</p>
        <p>122 258 km</p>
    </div>

    Берём родительский div подписи и вторую строку.
    """

    try:
        label_element = page.get_by_text(
            label,
            exact=True,
        ).first

        if label_element.count() == 0:
            return None

        label_element.wait_for(
            state="attached",
            timeout=5000,
        )

        parent = label_element.locator(
            "xpath=.."
        )

        paragraphs = parent.locator("p")

        if paragraphs.count() < 2:
            return None

        for index in range(paragraphs.count()):
            paragraph = paragraphs.nth(index)

            text = safe_inner_text(paragraph)

            if not text:
                continue

            if text.lower() == label.lower():
                continue

            return text

    except Exception:
        return None

    return None


def extract_year_from_text(text):
    if not text:
        return None

    current_year = datetime.now().year + 1

    matches = re.findall(
        r"\b(19\d{2}|20\d{2})\b",
        text,
    )

    for year in matches:
        year_number = int(year)

        if 1900 <= year_number <= current_year:
            return year

    return None


def extract_otomoto_year(page):
    """
    Год часто указан:
    - в title страницы;
    - в og:title;
    - в description;
    - в названии объявления.
    """

    sources = []

    try:
        sources.append(page.title())
    except Exception:
        pass

    selectors = [
        'meta[property="og:title"]',
        'meta[name="description"]',
        'meta[property="og:description"]',
    ]

    for selector in selectors:
        content = get_meta_content(
            page,
            selector,
        )

        if content:
            sources.append(content)

    try:
        heading = page.locator(
            "h1"
        ).first.inner_text(
            timeout=3000,
        )

        sources.append(heading)
    except Exception:
        pass

    for source in sources:
        year = extract_year_from_text(source)

        if year:
            return year

    return None


def extract_otomoto_details(page):
    found = wait_for_otomoto_summary(page)

    if not found:
        print(
            "Блок характеристик Otomoto "
            "не появился."
        )

    page.wait_for_timeout(1000)

    mileage = get_otomoto_value(
        page,
        "Przebieg",
    )

    fuel = get_otomoto_value(
        page,
        "Rodzaj paliwa",
    )

    gearbox = get_otomoto_value(
        page,
        "Skrzynia biegów",
    )

    year = extract_otomoto_year(page)

    details = {
        "year": year,
        "mileage": mileage,
        "fuel": fuel,
        "gearbox": gearbox,
    }

    print("Данные Otomoto:")
    print(f"  Год: {year}")
    print(f"  Пробег: {mileage}")
    print(f"  Топливо: {fuel}")
    print(f"  Коробка: {gearbox}")

    return details


# ============================================================
# OLX
# ============================================================

def get_olx_body_text(page):
    try:
        return page.locator(
            "body"
        ).inner_text(
            timeout=8000,
        )

    except Exception:
        return ""


def extract_olx_regex(text, pattern):
    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return None

    return normalize_text(
        match.group(1)
    )


def extract_olx_details(page):
    body = get_olx_body_text(page)

    year = extract_olx_regex(
        body,
        r"Rok produkcji\s*:?\s*(19\d{2}|20\d{2})",
    )

    mileage = extract_olx_regex(
        body,
        r"Przebieg\s*:?\s*([\d\s.,]+\s*km)",
    )

    fuel = extract_olx_regex(
        body,
        (
            r"Paliwo\s*:?\s*(.+?)"
            r"(?=\s+(?:Typ nadwozia|Kolor|"
            r"Poj\. silnika|Stan techniczny|"
            r"Skrzynia biegów|Przebieg|"
            r"Kraj pochodzenia|Moc silnika|"
            r"Napęd|Kierownica)\s*:)"
        ),
    )

    gearbox = extract_olx_regex(
        body,
        (
            r"Skrzynia biegów\s*:?\s*(.+?)"
            r"(?=\s+(?:Kraj pochodzenia|"
            r"Moc silnika|Przebieg|Napęd|"
            r"Kierownica|Typ nadwozia|"
            r"Kolor|Poj\. silnika)\s*:)"
        ),
    )

    details = {
        "year": year,
        "mileage": mileage,
        "fuel": fuel,
        "gearbox": gearbox,
    }

    print("Данные OLX:")
    print(f"  Год: {year}")
    print(f"  Пробег: {mileage}")
    print(f"  Топливо: {fuel}")
    print(f"  Коробка: {gearbox}")

    return details


# ============================================================
# ЗАГРУЗКА СТРАНИЦЫ ОБЪЯВЛЕНИЯ
# ============================================================

def update_advert_image(page, advert):
    image_url = get_meta_content(
        page,
        'meta[property="og:image"]',
    )

    image_url = valid_http_url(image_url)

    if image_url:
        advert["image_url"] = image_url


def get_advert_details(page, advert):
    url = advert["url"]

    try:
        print(f"Открываю объявление: {url}")

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=25_000,
        )

        page.wait_for_timeout(1500)
        close_cookies(page)

        if "otomoto.pl" in url:
            details = extract_otomoto_details(
                page
            )
        else:
            details = extract_olx_details(
                page
            )

        advert.update(details)
        update_advert_image(
            page,
            advert,
        )

    except Exception as error:
        print(
            f"Ошибка чтения объявления: "
            f"{error}"
        )

    return advert


def load_adverts_details(adverts):
    if not adverts:
        return adverts

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
        )

        context = browser.new_context(
            locale="pl-PL",
            viewport={
                "width": 1400,
                "height": 900,
            },
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        for index, advert in enumerate(
            adverts,
            start=1,
        ):
            print(
                f"Характеристики объявления "
                f"{index}/{len(adverts)}"
            )

            get_advert_details(
                page,
                advert,
            )

        browser.close()

    return adverts


# ============================================================
# ТЕСТ
# ============================================================

if __name__ == "__main__":
    adverts = collect_adverts()

    otomoto_advert = None

    for advert in adverts:
        if "otomoto.pl" in advert["url"]:
            otomoto_advert = advert
            break

    if not otomoto_advert:
        print(
            "В текущей выдаче не найдено "
            "объявление Otomoto."
        )
    else:
        print("-" * 60)
        print("Проверяю первое объявление Otomoto.")

        load_adverts_details(
            [otomoto_advert]
        )

        print("-" * 60)
        print(
            f"Название: "
            f"{otomoto_advert['title']}"
        )
        print(
            f"Цена: "
            f"{otomoto_advert['price']}"
        )
        print(
            f"Год: "
            f"{otomoto_advert.get('year')}"
        )
        print(
            f"Пробег: "
            f"{otomoto_advert.get('mileage')}"
        )
        print(
            f"Топливо: "
            f"{otomoto_advert.get('fuel')}"
        )
        print(
            f"Коробка: "
            f"{otomoto_advert.get('gearbox')}"
        )
        print(
            f"Фото: "
            f"{otomoto_advert.get('image_url')}"
        )
        print(
            f"Ссылка: "
            f"{otomoto_advert['url']}"
        )
        print("-" * 60)
