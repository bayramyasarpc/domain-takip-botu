import os
import time
import requests

from google import genai

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")

client = genai.Client(api_key=GEMINI_API_KEY)

# Hizli ve hafif model listesi
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]


def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram ayarları eksik.")
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
            print("Telegram mesajı başarıyla gönderildi.")
            return

        if len(message) > 4000:
            payload["text"] = message[:4000]
            requests.post(url, json=payload, timeout=15)

    except Exception as exc:
        print(f"Telegram gönderme hatası: {exc}")


def check_domain(domain):
    domain = domain.strip()
    if not domain:
        return "EMPTY"

    urls = [domain] if domain.startswith(("http://", "https://")) else [f"https://{domain}", f"http://{domain}"]

    for url in urls:
        try:
            # HEAD isteği atarak sayfa içeriğini indirmeden sadece başlıkları/status kodunu alıyoruz (Çok hızlıdır)
            response = requests.head(
                url,
                timeout=5,
                headers={"User-Agent": "Mozilla/5.0"},
                allow_redirects=True
            )
            return response.status_code
        except requests.RequestException:
            # HEAD isteğini engelleyen siteler olursa fallback olarak GET deneyelim
            try:
                response = requests.get(
                    url,
                    timeout=5,
                    headers={"User-Agent": "Mozilla/5.0"},
                    allow_redirects=True,
                    stream=True  # İçeriği indirmeden bağlantıyı kapatır
                )
                return response.status_code
            except requests.RequestException:
                continue

    return "ERROR"


def analyze_with_ai(domain_results):
    prompt = (
        "Sen bir Telegram bildirim botusun. Görevin sana verilen domain durum kodlarını "
        "SADECE verilen tablo şablonuna uygun olarak Türkçe raporlamaktır.\n\n"
        "KESİN KURALLAR:\n"
        "1. Yanıtına asla giriş, selamlama, kod bloğu açıklaması veya fazladan cümle EKLEME.\n"
        "2. Doğrudan 📊 emoji simgesi ile başla.\n"
        "3. HTTP Durum koduna göre 'Ulaşılıyor (200 OK)', 'Yönlendirildi (301/302)', 'Sunucu Hatası (500/502)' veya 'Erişilemez (ERROR)' şeklinde durum yaz.\n\n"
        "ÇIKTI ŞABLONU:\n"
        "📊 **DOMAIN ERİŞİM RAPORU**\n\n"
        "```\n"
        "DOMAIN                 | HTTP KODU | DURUM\n"
        "-----------------------|-----------|-------------\n"
        "[domain_adi]           | [kod]     | [Erişilebilir/Erişilemez]\n"
        "```\n\n"
        "💡 **ÖZET:** [Kaç domainden kaç tanesine erişildiğini belirten tek cümle]\n\n"
        "Veriler:\n" + str(domain_results)
    )

    for model_name in MODELS:
        print(f"Model deneniyor: {model_name}")

        for attempt in range(3):
            try:
                print(f"Deneme {attempt + 1}/3 ({model_name})")

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                if response and hasattr(response, "text") and response.text:
                    return response.text

            except Exception as exc:
                print(f"⚠️ {model_name} hatası yakalandı: {exc}")
                wait_time = (attempt + 1) * 5
                time.sleep(wait_time)

    return None


def main():
    print("Domain takip botu başlatıldı.")

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
        send_telegram_message(f"❌ `domains.txt` okunamadı: {exc}")
        return

    if not domains:
        send_telegram_message("⚠️ `domains.txt` dosyası boş.")
        return

    results = []
    for domain in domains:
        print(f"Kontrol ediliyor: {domain}")
        status = check_domain(domain)
        results.append(f"{domain} -> HTTP: {status}")

    all_data = "\n".join(results)

    report = analyze_with_ai(all_data)

    if report:
        send_telegram_message(report)
    else:
        # AI yanıt vermezse sadeleştirilmiş ham durum tablosu
        summary_text = "⚠️ **AI Raporu Oluşturulamadı (Ham Sonuçlar):**\n\n```\n" + all_data + "\n```"
        send_telegram_message(summary_text)

    print("İşlem tamamlandı.")


if __name__ == "__main__":
    main()
