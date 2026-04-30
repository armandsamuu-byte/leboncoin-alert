import os
import time
import json
import requests
import re
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
#  PAP.FR
# ─────────────────────────────────────────
def scrape_pap():
    ads = []
    try:
        url = f"https://www.pap.fr/annonce/locations-studio-nice-g694-a-{PRIX_MAX}e"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }
        r = requests.get(url, headers=headers, timeout=20)
        print(f"[{now()}] PAP status: {r.status_code}")
        if r.status_code != 200:
            return []

        html = r.text
        # Extraction des annonces PAP via balises
        pattern = r'href="(/annonces/location/[^"]+)"[^>]*>.*?<span[^>]*class="[^"]*price[^"]*"[^>]*>([^<]*)<'
        matches = re.findall(pattern, html, re.DOTALL)

        # Méthode alternative: chercher les blocs d'annonces
        blocks = re.findall(r'<article[^>]*class="[^"]*search-list-item[^"]*"[^>]*>(.*?)</article>', html, re.DOTALL)
        
        for block in blocks[:20]:
            try:
                # ID
                id_match = re.search(r'/annonces/location/[^/]+/(\d+)', block)
                if not id_match:
                    continue
                ad_id = "pap_" + id_match.group(1)
                
                # Prix
                prix_match = re.search(r'(\d+)\s*€', block)
                if not prix_match:
                    continue
                prix = int(prix_match.group(1))
                if prix > PRIX_MAX:
                    continue

                # Titre
                titre_match = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
                titre = re.sub(r'<[^>]+>', '', titre_match.group(1)).strip() if titre_match else "Annonce PAP"

                # URL
                url_match = re.search(r'href="(/annonces/location/[^"]+)"', block)
                ad_url = "https://www.pap.fr" + url_match.group(1) if url_match else "https://www.pap.fr"

                ads.append({"id": ad_id, "titre": titre, "prix": prix, "ville": "Nice", "source": "PAP", "url": ad_url})
            except:
                continue

        print(f"[{now()}] PAP: {len(ads)} annonces")
    except Exception as e:
        print(f"[{now()}] ❌ PAP: {e}")
    return ads

# ─────────────────────────────────────────
#  SELOGER
# ─────────────────────────────────────────
def scrape_seloger():
    ads = []
    try:
        url = "https://www.seloger.com/list.htm?types=1&natures=1&places=[{ci:060880}]&price=NaN/660&rooms=1&bedrooms=0"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }
        r = requests.get(url, headers=headers, timeout=20)
        print(f"[{now()}] SeLoger status: {r.status_code}")
        if r.status_code != 200:
            return []

        html = r.text
        
        # SeLoger embarque les données dans un JSON __NEXT_DATA__
        match = re.search(r'"listings"\s*:\s*(\[.*?\])', html, re.DOTALL)
        if not match:
            # Essai avec une autre clé
            match = re.search(r'"cards"\s*:\s*(\[.*?\])', html, re.DOTALL)
        
        if match:
            try:
                items = json.loads(match.group(1))
                for item in items[:20]:
                    try:
                        ad_id = "sl_" + str(item.get("id", ""))
                        prix = item.get("pricing", {}).get("price") or item.get("price")
                        if not prix or int(prix) > PRIX_MAX:
                            continue
                        titre = item.get("title", "Annonce SeLoger")
                        ad_url = item.get("classifiedURL") or item.get("url", "https://www.seloger.com")
                        ads.append({"id": ad_id, "titre": titre, "prix": int(prix), "ville": "Nice", "source": "SeLoger", "url": ad_url})
                    except:
                        continue
            except:
                pass

        # Fallback: extraction regex
        if not ads:
            id_matches = re.findall(r'"id"\s*:\s*"?(\d+)"?', html)
            prix_matches = re.findall(r'"price"\s*:\s*(\d+)', html)
            for i, (ad_id, prix) in enumerate(zip(id_matches[:20], prix_matches[:20])):
                try:
                    if int(prix) <= PRIX_MAX and int(prix) > 100:
                        ads.append({
                            "id": "sl_" + ad_id,
                            "titre": f"Studio Nice — {prix}€/mois",
                            "prix": int(prix),
                            "ville": "Nice",
                            "source": "SeLoger",
                            "url": f"https://www.seloger.com/annonces/locations/{ad_id}.htm"
                        })
                except:
                    continue

        print(f"[{now()}] SeLoger: {len(ads)} annonces")
    except Exception as e:
        print(f"[{now()}] ❌ SeLoger: {e}")
    return ads

# ─────────────────────────────────────────
#  LEBONCOIN (via RSS alternatif)
# ─────────────────────────────────────────
def scrape_leboncoin():
    ads = []
    try:
        # LeBonCoin bloque les IPs US — on essaie quand même avec rotation de headers
        url = (
            "https://www.leboncoin.fr/recherche"
            "?category=10"
            "&locations=Nice_06000__43.7101728_7.261953_10000_200000"
            "&real_estate_type=2"
            "&price=max-660"
            "&rooms=1"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        session = requests.Session()
        r = session.get(url, headers=headers, timeout=20)
        print(f"[{now()}] LBC status: {r.status_code}")

        if r.status_code == 200:
            html = r.text
            idx = html.find('"ads":')
            if idx != -1:
                start = html.find('[', idx)
                if start != -1:
                    depth, end = 0, start
                    for i, ch in enumerate(html[start:], start):
                        if ch == '[': depth += 1
                        elif ch == ']':
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    try:
                        raw_ads = json.loads(html[start:end])
                        for ad in raw_ads[:20]:
                            ad_id = "lbc_" + str(ad.get("list_id", ""))
                            prix_list = ad.get("price", [])
                            prix = prix_list[0] if prix_list else None
                            if prix and prix <= PRIX_MAX:
                                ads.append({
                                    "id": ad_id,
                                    "titre": ad.get("subject", "Annonce LeBonCoin"),
                                    "prix": prix,
                                    "ville": ad.get("location", {}).get("city", "Nice"),
                                    "source": "LeBonCoin",
                                    "url": f"https://www.leboncoin.fr/annonces/{ad.get('list_id')}"
                                })
                    except:
                        pass

        print(f"[{now()}] LBC: {len(ads)} annonces")
    except Exception as e:
        print(f"[{now()}] ❌ LBC: {e}")
    return ads

# ─────────────────────────────────────────
#  FORMAT MESSAGE
# ─────────────────────────────────────────
def format_alert(ad):
    source_emoji = {"PAP": "🔵", "SeLoger": "🏠", "LeBonCoin": "🔶"}.get(ad["source"], "📢")
    msg = f"🔔 <b>NOUVELLE ANNONCE — {ad['source']}</b>\n\n"
    msg += f"{source_emoji} <b>{ad['titre']}</b>\n"
    msg += f"💶 <b>{ad['prix']}€/mois</b>\n"
    msg += f"📍 {ad['ville']}\n"
    msg += f"\n👉 <a href='{ad['url']}'>Voir l'annonce</a>"
    return msg

# ─────────────────────────────────────────
#  BOUCLE PRINCIPALE
# ─────────────────────────────────────────
def main():
    print("=" * 50)
    print("🏠 Alert Multi-Plateformes — Nice Studio")
    print(f"   Budget max : {PRIX_MAX}€")
    print(f"   Sources : LeBonCoin + PAP + SeLoger")
    print(f"   Vérification toutes les {CHECK_INTERVAL//60} min")
    print("=" * 50)

    send_telegram(
        f"✅ <b>Bot démarré !</b>\n\n"
        f"Surveillance active sur :\n"
        f"🔶 LeBonCoin\n🔵 PAP.fr\n🏠 SeLoger\n\n"
        f"Budget max : {PRIX_MAX}€/mois — Nice 🔍"
    )

    seen = load_seen()
    first_run = len(seen) == 0

    while True:
        print(f"\n[{now()}] Vérification en cours...")
        all_ads = []
        all_ads += scrape_pap()
        all_ads += scrape_seloger()
        all_ads += scrape_leboncoin()

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
            print(f"[{now()}] {new_count} nouvelle(s) annonce(s) envoyée(s) !")

        save_seen(seen)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
