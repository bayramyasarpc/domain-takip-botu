import os
import time
import requests
import urllib3

from google import genai

# SSL sertifika uyarılarını konsolda gizlemek için
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")

client = genai.Client(api_key=GEMINI_API_KEY)

# Denenecek yapay zeka modelleri
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]


def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram ayarları eksik!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        print(f"Telegram API Yanıt Durumu: {response.status_code}")
        
        if response.ok:
            print("✅ Telegram mesajı başarıyla gönderildi.")
            return

        print(f"❌ Telegram Hatası: {response.status_code} - {response.text}")

        # Mesaj Telegram karakter sınırını (4000) aşarsa kırpıp tekrar dene
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


def create_fallback_table(results_dict):
    """AI yanıt vermezse Python'ın üreteceği yedek tablo"""
    lines = [
        "📊 **HAFTALIK DOMAIN DURUM RAPORU**\n",
        "```",
        f"{'DOMAIN':<30} | {'HTTP':<6} | {'DURUM':<12}",
        "-" * 30 + "-|-" + "-" * 6 + "-|-" + "-" * 12
    ]
    
    for domain, status in results_dict.items():
        durum_text = "Erişilebilir" if status in ["200", "301", "302"] else "Erişilemez"
        lines.append(f"{domain:<30} | {status:<6} | {durum_text:<12}")
        
    lines.append("```")
    lines.append("\n💡 **ÖZET:** Otomatik alan adı erişim taraması tamamlandı.")
    return "\n".join(lines)


def analyze_with_ai(domain_results):
    prompt = (
        "Aşağıdaki domain kontrol verilerini analiz et ve SADECE aşağıdaki Markdown tablo formatında Türkçe yanıt üret.\n\n"
        "ŞABLON (Asla bu formatın dışına çıkma, giriş/çıkış açıklaması yapma):\n\n"
        "📊 **HAFTALIK DOMAIN DURUM RAPORU**\n\n"
        "```\n"
        "DOMAIN                         | HTTP   | DURUM\n"
        "-------------------------------|--------|-------------\n"
        "example1.com                   | 200    | Erişilebilir\n"
        "example2.com                   | ERROR  | Erişilemez\n"
        "```\n\n"
        "💡 **ÖZET:** [1 cümlelik genel durum özeti]\n\n"
        f"Veriler:\n{domain_results}"
    )

    for model_name in MODELS:
        print(f"🤖 Yapay Zeka Modeli Deneniyor: {model_name}")
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and hasattr(response, "text") and response.text:
                    print("✅ AI raporu başarıyla oluşturuldu.")
                    return response.text
            except Exception as exc:
                print(f"⚠️ AI Modeli Hatası ({model_name}): {exc}")
                time.sleep(3)

    return None


def main():
    print("🚀 Domain kontrol botu başlatılıyor...")

    if not os.path.exists("domains.txt"):
        print("❌ domains.txt dosyası bulunamadı!")
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
        print(f"❌ domains.txt okuma hatası: {exc}")
        send_telegram_message(f"❌ `domains.txt` okunamadı: {exc}")
        return

    if not domains:
        print("⚠️ domains.txt dosyası boş!")
        send_telegram_message("⚠️ `domains.txt` dosyası boş.")
        return

    results_dict = {}
    formatted_results = []

    for domain in domains:
        print(f"🔍 Kontrol ediliyor: {domain}")
        status = check_domain(domain)
        print(f"➡️ Durum Kodu: {status}")
        
        clean_display = domain.replace("https://", "").replace("http://", "").strip("/")
        if len(clean_display) > 30:
            clean_display = clean_display[:27] + "..."

        results_dict[clean_display] = status
        formatted_results.append(f"{domain} -> HTTP: {status}")

    all_data = "\n".join(formatted_results)

    print("🤖 Veriler Gemini AI modeline gönderiliyor...")
    report = analyze_with_ai(all_data)

    if report:
        print("📤 AI raporu Telegram'a gönderiliyor...")
        send_telegram_message(report)
    else:
        print("⚠️ AI yanıt veremedi, yedek tablo oluşturulup Telegram'a gönderiliyor...")
        fallback_table = create_fallback_table(results_dict)
        send_telegram_message(fallback_table)

    print("🏁 İşlem başarıyla tamamlandı.")


if __name__ == "__main__":
    main()
