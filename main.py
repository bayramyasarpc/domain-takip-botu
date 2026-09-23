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

# Yoğunluk durumunda sırasıyla denenecek modeller
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram settings are missing.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

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

        print(f"Telegram error: {response.status_code} {response.text}")

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
            print(f"Telegram retry error: {response.status_code} {response.text}")

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

            # İçeriği 1500 karaktere süzerek AI'a binen yükü hafifletiyoruz
            return (
                response.status_code,
                response.text[:1500],
                response.url
            )

        except requests.RequestException as exc:
            last_error = str(exc)

    return "ERROR", last_error, ""


def analyze_with_ai(domain_results):
    prompt = (
        "Aşağıdaki domain tarama verilerini analiz et ve Telegram'da yayınlanacak "
        "son derece okunabilir, temiz bir özet rapor hazırla.\n\n"
        "Sadece Türkçe yanıt ver. Uzun paragraflar yazma, doğrudan tablo ve maddeler kullan.\n\n"
        "Çıktıyı aynen aşağıdaki şablonda oluştur:\n\n"
        "📊 **HAFTALIK DOMAIN DURUM RAPORU**\n\n"
        "```\n"
        "DOMAIN            | DURUM       | HTTP | SATIŞTA MI?\n"
        "------------------|-------------|------|------------\n"
        "example1.com      | Aktif Site  | 200  | ❌ Hayır\n"
        "example2.com      | Park Edilmiş| 200  | ⚠️ Evet (Sedo)\n"
        "example3.com      | Erişilemez  | 500  | ❌ Hayır\n"
        "```\n\n"
        "📌 **DETAYLAR & TESPİTLER:**\n"
        "• **domain.com:** Açıklama (örn: El değiştirmiş olabilir veya GoDaddy park sayfasında).\n\n"
        "💡 **GENEL ÖZET:**\n"
        "[1-2 cümlelik kısa genel durum değerlendirmesi]\n\n"
        "Veriler:\n" + str(domain_results)
    )

    for model_name in MODELS:
        print(f"Trying model: {model_name}")

        for attempt in range(3):
            try:
                print(f"Attempt {attempt + 1}/3 for {model_name}")

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                if response is None:
                    raise RuntimeError("Empty Gemini response")

                text = getattr(response, "text", None)

                if not text:
                    raise RuntimeError("Empty Gemini response text")

                return text

            except errors.APIError as exc:
                print(f"Gemini API error ({model_name}): {exc}")

                status_code = getattr(exc, "code", None)

                retryable_codes = {408, 429, 500, 502, 503, 504}

                if status_code not in retryable_codes:
                    break

                # Yoğunluk durumunda sunucuya zaman tanımak için 10, 20 sn bekleme
                wait_time = (attempt + 1) * 10
                print(f"Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)

            except Exception as exc:
                print(f"Gemini error ({model_name}): {exc}")
                time.sleep(10)

    return None


def main():
    print("Starting domain monitor")

    if not os.path.exists("domains.txt"):
        send_telegram_message("❌ `domains.txt` dosyası bulunamadı.")
        return

    try:
        with open("domains.txt", "r", encoding="utf-8") as file:
            domains = [
                line.strip()
                for line in file
                if line.strip() and not line.strip().startswith("#")
            ]

    except Exception as exc:
        print(f"Could not read domains.txt: {exc}")
        send_telegram_message(f"❌ `domains.txt` okunamadı: {exc}")
        return

    if not domains:
        send_telegram_message("⚠️ `domains.txt` dosyası boş.")
        return

    results = []

    for domain in domains:
        print(f"Checking: {domain}")

        status, content, final_url = check_domain(domain)

        result = (
            f"Domain: {domain}\n"
            f"HTTP Status: {status}\n"
            f"Final URL: {final_url}\n"
            f"Content:\n{content[:1000]}\n"
            f"{'-' * 50}"
        )

        results.append(result)

    all_data = "\n\n".join(results)

    report = analyze_with_ai(all_data)

    if report:
        message = report
    else:
        message = (
            "⚠️ **AI Raporu Oluşturulamadı** (Sunucu Yoğunluğu)\n\n"
            "**Ham Tarama Sonuçları:**\n\n"
            f"```\n{all_data[:3000]}\n```"
        )

    send_telegram_message(message)

    print("Domain monitor finished")


if __name__ == "__main__":
    main()
