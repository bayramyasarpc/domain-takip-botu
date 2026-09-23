import os
import requests
import urllib3

# SSL sertifika uyarılarını konsolda gizlemek için
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram ayarları eksik!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        print(f"Telegram API Yanıt Durumu: {response.status_code}")
        
        if response.ok:
            print("✅ Telegram mesajı başarıyla gönderildi.")
            return

        print(f"❌ Telegram Hatası: {response.status_code} - {response.text}")

        # Mesaj Telegram sınırını aşarsa parçalayarak gönder
        if len(message) > 4000:
            payload["text"] = message[:4000]
            requests.post(url, json=payload, timeout=15)

    except Exception as exc:
        print(f"❌ Telegram Bağlantı Hatası: {exc}")


def check_domain(domain):
    domain = domain.strip()
    if not domain:
        return "EMPTY"

    if domain.startswith(("http://", "https://")):
        urls = [domain]
    else:
        urls = [f"https://{domain}", f"http://{domain}"]

    # WAF ve Bot engellerini aşmak için Chrome tarayıcı başlıkları
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }

    session = requests.Session()

    for url in urls:
        # 1. Aşama: GET isteği ile doğrulama
        try:
            response = session.get(
                url,
                timeout=10,
                headers=headers,
                allow_redirects=True,
                verify=False
            )
            return str(response.status_code)
        except requests.RequestException:
            pass

        # 2. Aşama: Alternatif olarak HEAD isteği
        try:
            response = session.head(
                url,
                timeout=10,
                headers=headers,
                allow_redirects=True,
                verify=False
            )
            return str(response.status_code)
        except requests.RequestException:
            continue

    return "ERROR"


def main():
    print("🚀 Domain kontrol botu başlatılıyor...")

    if not os.path.exists("domains.txt"):
        print("❌ domains.txt dosyası bulunamadı!")
        send_telegram_message("❌ domains.txt dosyası bulunamadı.")
        return

    try:
        with open("domains.txt", "r", encoding="utf-8") as file:
            domains = [
                line.strip()
                for line in file
                if line.strip() and not line.strip().startswith("#")
            ]
    except Exception as exc:
        print(f"❌ domains.txt okuma hatası: {exc}")
        send_telegram_message(f"❌ domains.txt okunamadı: {exc}")
        return

    if not domains:
        print("⚠️ domains.txt dosyası boş!")
        send_telegram_message("⚠️ domains.txt dosyası boş.")
        return

    results = []
    accessible_count = 0
    total_count = len(domains)

    for domain in domains:
        print(f"🔍 Kontrol ediliyor: {domain}")
        status = check_domain(domain)
        print(f"➡️ Durum Kodu: {status}")
        
        # Tam URL'i koru, kesme veya kısaltma yapma
        full_url = domain if domain.startswith(("http://", "https://")) else f"https://{domain}/"
        results.append(f"{full_url} -> HTTP: {status}")

        if status in ["200", "301", "302"]:
            accessible_count += 1

    # Rapor çıktısını birleştir
    output_message = "\n".join(results)
    output_message += f"\n\nÖZET: Taranan {total_count} domainden {accessible_count} tanesi erişilebilir durumdadır."

    print("📤 Mesaj Telegram'a gönderiliyor...")
    send_telegram_message(output_message)

    print("🏁 İşlem başarıyla tamamlandı.")


if __name__ == "__main__":
    main()
