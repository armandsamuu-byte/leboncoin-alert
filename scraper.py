import os
import time
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

PRIX_MAX = 660
CHECK_INTERVAL = 300
SEEN_FILE = "seen_ads.json"

def now():
    return datetime.now().strftime("%H:%M:%S")

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"[{now()}] ✅ Telegram envoyé")
        else:
            print(f"[{now()}] ❌ Telegram {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"[{now()}] ❌ Telegram: {e}")

# ─────────────────────────────────────────
#  PAP.FR — Flux RSS officiel
# ─────────────────────────────────────────
def scrape_pap():
    ads = []
    try:
        url = f"https://www.pap.fr/annonce/locations-studio-nice-g694-a-{PRIX_MAX}e.rss"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; RSS reader)"}
        r = requests.get(url, headers=headers, timeout=20)
        print(f"[{now()}] PAP RSS status: {r.status_code}")
        if r.status_code != 200:
            return []

        root = ET.fromstring(r.content)
        ns = {'content': 'http://purl.org/rss/1.0/modules/content/'}

        for item in root.findall('.//item'):
            try:
                title = item.findtext('title', '').strip()
                link = item.findtext('link', '').strip()
                desc = item.findtext('description', '')
                guid = item.findtext('guid', link)

                # Extraire le prix depuis le titre ou la description
                import re
                prix_match = re.search(r'(\d+)\s*€', title + desc)
                if not prix_match:
                    continue
                prix = int(prix_match.group(1))
                if prix > PRIX_MAX:
                    continue

                ad_id = "pap_" + guid.split('/')[-1]
                ads.append({"id": ad_id, "titre": title, "prix": prix, "source": "PAP", "url": link})
            except:
                continue

        print(f"[{now()}] PAP: {len(ads)} annonces")
    except Exception as e:
        print(f"[{now()}] ❌ PAP: {e}")
    return ads

# ─────────────────────────────────────────
#  LEBONCOIN — Flux RSS officiel
# ─────────────────────────────────────────
def scrape_leboncoin():
    ads = []
    try:
        url = (
            "https://www.leboncoin.fr/rss/ventes_immobilieres.htm"
            "?location=Nice"
            "&real_estate_type=2"
            "&price=max-660"
            "&rooms=1"
        )
        # Essai avec l'API de recherche RSS alternative
        url2 = "https://www.leboncoin.fr/recherche.rss?category=10&locations=Nice&price=max-660&real_estate_type=2&rooms=1"
        
        headers = {"User-Agent": "Mozilla/5.0 (compatible; RSS reader; +http://www.example.com)"}
        
        for rss_url in [url, url2]:
            r = requests.get(rss_url, headers=headers, timeout=20)
            print(f"[{now()}] LBC RSS status: {r.status_code} — {rss_url[:60]}")
            if r.status_code == 200:
                try:
                    import re
                    root = ET.fromstring(r.content)
                    for item in root.findall('.//item'):
                        title = item.findtext('title', '').strip()
                        link = item.findtext('link', '').strip()
                        desc = item.findtext('description', '')
                        guid = item.findtext('guid', link)

                        prix_match = re.search(r'(\d+)\s*€', title + desc)
                        if not prix_match:
                            continue
                        prix = int(prix_match.group(1))
                        if prix > PRIX_MAX or prix < 100:
                            continue

                        ad_id = "lbc_" + guid.split('/')[-1].split('.')[0]
                        ads.append({"id": ad_id, "titre": title, "prix": prix, "source": "LeBonCoin", "url": link})
                    break
                except Exception as e:
                    print(f"[{now()}] LBC parse error: {e}")
                    continue

        print(f"[{now()}] LBC: {len(ads)} annonces")
    except Exception as e:
        print(f"[{now()}] ❌ LBC: {e}")
    return ads

# ─────────────────────────────────────────
#  SELOGER — Flux RSS officiel
# ─────────────────────────────────────────
def scrape_seloger():
    ads = []
    try:
        # SeLoger RSS pour Nice, location, studio, max 660€
        url = "https://www.seloger.com/search/real-estate/rss.htm?types=1&natures=1&places=[{ci:060880}]&price=NaN/660&rooms=1"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; RSS reader)"}
        r = requests.get(url, headers=headers, timeout=20)
        print(f"[{now()}] SeLoger RSS status: {r.status_code}")
        if r.status_code != 200:
            return []

        import re
        root = ET.fromstring(r.content)
        for item in root.findall('.//item'):
            try:
                title = item.findtext('title', '').strip()
                link = item.findtext('link', '').strip()
                desc = item.findtext('description', '')
                guid = item.findtext('guid', link)

                prix_match = re.search(r'(\d+)\s*€', title + desc)
                if not prix_match:
                    continue
                prix = int(prix_match.group(1))
                if prix > PRIX_MAX or prix < 100:
                    continue

                ad_id = "sl_" + guid.split('/')[-1].split('.')[0]
                ads.append({"id": ad_id, "titre": title, "prix": prix, "source": "SeLoger", "url": link})
            except:
                continue

        print(f"[{now()}] SeLoger: {len(ads)} annonces")
    except Exception as e:
        print(f"[{now()}] ❌ SeLoger: {e}")
    return ads

# ─────────────────────────────────────────
#  FORMAT MESSAGE
# ─────────────────────────────────────────
def format_alert(ad):
    emoji = {"PAP": "🔵", "SeLoger": "🏠", "LeBonCoin": "🔶"}.get(ad["source"], "📢")
    msg = f"🔔 <b>NOUVELLE ANNONCE — {ad['source']}</b>\n\n"
    msg += f"{emoji} <b>{ad['titre']}</b>\n"
    msg += f"💶 <b>{ad['prix']}€/mois</b>\n"
    msg += f"📍 Nice\n"
    msg += f"\n👉 <a href='{ad['url']}'>Voir l'annonce</a>"
    return msg

# ─────────────────────────────────────────
#  BOUCLE PRINCIPALE
# ─────────────────────────────────────────
def main():
    print("=" * 50)
    print("🏠 Alert Multi-Plateformes — Nice Studio")
    print(f"   Budget max : {PRIX_MAX}€")
    print(f"   Sources : LeBonCoin + PAP + SeLoger (RSS)")
    print(f"   Vérification toutes les {CHECK_INTERVAL//60} min")
    print("=" * 50)

    send_telegram(
        f"✅ <b>Bot démarré (v3 RSS) !</b>\n\n"
        f"Surveillance active sur :\n"
        f"🔶 LeBonCoin\n🔵 PAP.fr\n🏠 SeLoger\n\n"
        f"Budget max : {PRIX_MAX}€/mois — Nice 🔍"
    )

    seen = load_seen()
    first_run = len(seen) == 0

    while True:
        print(f"\n[{now()}] Vérification en cours...")
        all_ads = scrape_pap() + scrape_seloger() + scrape_leboncoin()

        new_count = 0
        for ad in all_ads:
            if ad["id"] not in seen:
                seen.add(ad["id"])
                if not first_run:
                    send_telegram(format_alert(ad))
                    new_count += 1
                    time.sleep(1)

        if first_run:
            print(f"[{now()}] Première exécution : {len(seen)} annonces indexées")
            send_telegram(
                f"📋 <b>{len(seen)} annonces existantes indexées.</b>\n"
                f"Je t'alerterai pour les <b>nouvelles uniquement</b> ✅"
            )
            first_run = False
        elif new_count == 0:
            print(f"[{now()}] Aucune nouvelle annonce")
        else:
            print(f"[{now()}] {new_count} nouvelle(s) annonce(s) !")

        save_seen(seen)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
