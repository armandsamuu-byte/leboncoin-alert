import os
import time
import json
import hashlib
import requests
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIG — Modifie ces valeurs
# ─────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "TON_TOKEN_ICI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "TON_CHAT_ID_ICI")

# Critères de recherche
VILLE = "Nice"
PRIX_MAX = 660
SURFACE_MIN = 15  # m²
CHECK_INTERVAL = 300  # secondes entre chaque vérification (5 min)

# Fichier pour stocker les annonces déjà vues
SEEN_FILE = "seen_ads.json"

# ─────────────────────────────────────────
#  HEADERS pour simuler un vrai navigateur
# ─────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://www.leboncoin.fr/",
}

# ─────────────────────────────────────────
#  URL API LeBonCoin
# ─────────────────────────────────────────
def build_url():
    return (
        "https://api.leboncoin.fr/finder/search"
    )

def build_payload():
    return {
        "filters": {
            "category": {"id": "10"},  # Locations
            "enums": {
                "ad_type": ["offer"],
                "real_estate_type": ["2"],  # Appartement
                "rooms": ["1"],  # Studio / T1
            },
            "location": {
                "area": {
                    "lat": 43.7102,
                    "lng": 7.2620,
                    "radius": 10000  # 10km autour de Nice
                }
            },
            "ranges": {
                "price": {"max": PRIX_MAX},
                "square": {"min": SURFACE_MIN}
            }
        },
        "limit": 35,
        "limit_alu": 3,
        "offset": 0,
        "owner": {"type": "all"}
    }

# ─────────────────────────────────────────
#  CHARGEMENT / SAUVEGARDE des annonces vues
# ─────────────────────────────────────────
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

# ─────────────────────────────────────────
#  ENVOI TELEGRAM
# ─────────────────────────────────────────
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
        r.raise_for_status()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Alerte envoyée")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Erreur Telegram : {e}")

def format_alert(ad):
    prix = ad.get("price", [None])[0]
    titre = ad.get("subject", "Sans titre")
    location = ad.get("location", {})
    ville = location.get("city", "?")
    cp = location.get("zipcode", "")
    surface = None
    charges = None

    # Extraire surface et charges depuis les attributs
    for attr in ad.get("attributes", []):
        if attr.get("key") == "square":
            surface = attr.get("value_label", "?")
        if attr.get("key") == "charges_included":
            charges = attr.get("value_label")

    url = f"https://www.leboncoin.fr/annonces/{ad.get('list_id')}"
    date = ad.get("first_publication_date", "")[:16].replace("T", " ")

    msg = f"🔔 <b>NOUVELLE ANNONCE</b>\n\n"
    msg += f"🏠 <b>{titre}</b>\n"
    msg += f"💶 <b>{prix}€/mois</b>"
    if charges:
        msg += f" ({charges})"
    msg += "\n"
    if surface:
        msg += f"📐 {surface}\n"
    msg += f"📍 {ville} {cp}\n"
    msg += f"🕐 Publiée le {date}\n\n"
    msg += f"👉 <a href='{url}'>Voir l'annonce</a>"

    return msg

# ─────────────────────────────────────────
#  SCRAPING PRINCIPAL
# ─────────────────────────────────────────
def check_leboncoin(seen):
    new_ads = []
    try:
        r = requests.post(
            build_url(),
            json=build_payload(),
            headers=HEADERS,
            timeout=15
        )
        r.raise_for_status()
        data = r.json()
        ads = data.get("ads", [])

        print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(ads)} annonces trouvées")

        for ad in ads:
            ad_id = str(ad.get("list_id"))
            if ad_id not in seen:
                seen.add(ad_id)
                new_ads.append(ad)
                msg = format_alert(ad)
                send_telegram(msg)
                time.sleep(1)  # Anti-spam

    except requests.exceptions.HTTPError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Erreur HTTP : {e}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Erreur : {e}")

    return seen, len(new_ads)

# ─────────────────────────────────────────
#  BOUCLE PRINCIPALE
# ─────────────────────────────────────────
def main():
    print("=" * 50)
    print("🏠 LeBonCoin Alert — Nice Studio")
    print(f"   Budget max : {PRIX_MAX}€")
    print(f"   Surface min : {SURFACE_MIN}m²")
    print(f"   Vérification toutes les {CHECK_INTERVAL//60} min")
    print("=" * 50)

    # Message de démarrage
    send_telegram(
        f"✅ <b>Bot démarré !</b>\n\n"
        f"Je surveille les studios à Nice jusqu'à {PRIX_MAX}€/mois.\n"
        f"Tu recevras une alerte dès qu'une nouvelle annonce apparaît 🔍"
    )

    seen = load_seen()
    print(f"[INFO] {len(seen)} annonces déjà connues chargées")

    # Première passe : charger les annonces existantes sans alerter
    if len(seen) == 0:
        print("[INFO] Première exécution — chargement des annonces existantes...")
        seen, _ = check_leboncoin(seen)
        # On ne veut pas d'alertes au premier lancement, juste charger
        # Donc on recharge proprement sans envoyer
        send_telegram("📋 Annonces existantes indexées. Je t'alerterai pour les <b>nouvelles</b> uniquement.")
        save_seen(seen)

    # Boucle de surveillance
    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Vérification en cours...")
        seen, nb_new = check_leboncoin(seen)
        save_seen(seen)

        if nb_new == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Aucune nouvelle annonce")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {nb_new} nouvelle(s) annonce(s) envoyée(s) !")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
