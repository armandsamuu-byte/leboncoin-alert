import os
import time
import json
import requests
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

PRIX_MAX = 660
CHECK_INTERVAL = 300
SEEN_FILE = "seen_ads.json"

SEARCH_URL = (
    "https://www.leboncoin.fr/recherche"
    "?category=10"
    "&locations=Nice_06000__43.7101728_7.261953_10000_200000"
    "&real_estate_type=2"
    "&price=max-660"
    "&rooms=1"
    "&owner_type=all"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def now():
    return datetime.now().strftime("%H:%M:%S")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"[{now()}] ✅ Message Telegram envoyé")
        else:
            print(f"[{now()}] ❌ Telegram erreur {r.status_code}: {r.text}")
    except Exception as e:
        print(f"[{now()}] ❌ Telegram exception: {e}")

def scrape_leboncoin():
    ads = []
    try:
        session = requests.Session()
        r = session.get(SEARCH_URL, headers=HEADERS, timeout=20)
        print(f"[{now()}] LeBonCoin status: {r.status_code}")

        if r.status_code != 200:
            print(f"[{now()}] ⚠️ Erreur {r.status_code} — retry dans 5 min")
            return []

        html = r.text
        marker = '"ads":'
        idx = html.find(marker)
        if idx == -1:
            print(f"[{now()}] ⚠️ Structure HTML non reconnue")
            return []

        start = html.find('[', idx)
        if start == -1:
            return []

        depth = 0
        end = start
        for i, ch in enumerate(html[start:], start):
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        raw_ads = json.loads(html[start:end])

        for ad in raw_ads[:20]:
            try:
                ad_id = str(ad.get("list_id", ""))
                titre = ad.get("subject", "Sans titre")
                prix_list = ad.get("price", [])
                prix = prix_list[0] if prix_list else None
                location = ad.get("location", {})
                ville = location.get("city", "?")
                cp = location.get("zipcode", "")
                url = f"https://www.leboncoin.fr/annonces/{ad_id}"
                date = ad.get("first_publication_date", "")[:16].replace("T", " ")

                if prix and prix <= PRIX_MAX:
                    ads.append({"id": ad_id, "titre": titre, "prix": prix,
                                "ville": ville, "cp": cp, "url": url, "date": date})
            except:
                continue

        print(f"[{now()}] {len(ads)} annonces dans le budget")

    except Exception as e:
        print(f"[{now()}] ❌ Erreur scraping: {e}")

    return ads

def format_alert(ad):
    msg = f"🔔 <b>NOUVELLE ANNONCE — Nice</b>\n\n"
    msg += f"🏠 <b>{ad['titre']}</b>\n"
    msg += f"💶 <b>{ad['prix']}€/mois</b>\n"
    msg += f"📍 {ad['ville']} {ad['cp']}\n"
    if ad['date']:
        msg += f"🕐 Publiée le {ad['date']}\n"
    msg += f"\n👉 <a href='{ad['url']}'>Voir l'annonce</a>"
    return msg

def main():
    print("=" * 50)
    print("🏠 LeBonCoin Alert — Nice Studio")
    print(f"   Budget max : {PRIX_MAX}€")
    print(f"   Vérification toutes les {CHECK_INTERVAL//60} min")
    print("=" * 50)

    send_telegram(
        f"✅ <b>Bot démarré !</b>\n\n"
        f"Je surveille les studios à Nice jusqu'à {PRIX_MAX}€/mois.\n"
        f"Tu recevras une alerte dès qu'une nouvelle annonce apparaît 🔍"
    )

    seen = load_seen()
    first_run = len(seen) == 0

    while True:
        print(f"\n[{now()}] Vérification en cours...")
        ads = scrape_leboncoin()

        new_count = 0
        for ad in ads:
            if ad["id"] not in seen:
                seen.add(ad["id"])
                if not first_run:
                    send_telegram(format_alert(ad))
                    new_count += 1
                    time.sleep(1)

        if first_run:
            print(f"[{now()}] Première exécution : {len(seen)} annonces indexées")
            send_telegram(f"📋 {len(seen)} annonces existantes indexées.\nJe t'alerterai pour les <b>nouvelles uniquement</b> ✅")
            first_run = False
        elif new_count == 0:
            print(f"[{now()}] Aucune nouvelle annonce")
        else:
            print(f"[{now()}] {new_count} nouvelle(s) annonce(s) !")

        save_seen(seen)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
