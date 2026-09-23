import os
import time
import requests

from google import genai
from google.genai import errors

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")

client = genai.Client(api_key=GEMINI_API_KEY)

MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram settings are missing.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Markdown formatında gönderim açıldı
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=15)

        if response.ok:
            print("Telegram message sent.")
            return

        print(
            f"Telegram error: {response.status_code} "
            f"{response.text}"
        )

        if len(message) > 4000:
            message = message[:4000]

        response = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            },
            timeout=15
        )

        if not response.ok:
            print(
                f"Telegram retry error: "
                f"{response.status_code} {response.text}"
            )

    except requests.RequestException as exc:
        print(f"Telegram connection error: {exc}")


def check_domain(domain):
    domain = domain.strip()

    if not domain:
        return "EMPTY", "", ""

    if domain.startswith("http://") or domain.startswith("https://"):
        urls = [domain]
    else:
        urls = [
            f"https://{domain}",
            f"http://{domain}"
        ]

    last_error = ""

    for url in urls:
        try:
            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
                allow_redirects=True
            )

            return (
                response.status_code,
                response.text[:3000],
                response.url
            )

        except requests.RequestException as exc:
            last_error = str(exc)

    return "ERROR", last_error, ""


def analyze_with_ai(domain_results):
    # Prompt tablo ve liste formatına göre tamamen yenilendi
    prompt = f"""
Aşağıdaki domain tarama verilerini analiz et ve Telegram'da yayınlanacak son derece okunabilir, temiz bir özet rapor hazırla.

Sadece Türkçe yanıt ver. Uzun paragraflar yazma, doğrudan tablo ve maddeler kullan.

Çıktıyı aynen aşağıdaki şablonda oluştur:

📊 **HAFTALIK DOMAIN DURUM RAPORU**
