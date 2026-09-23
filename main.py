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
            print("Telegram mesajı gönderildi.")
            return

        if len(message) > 4000:
            payload["text"] = message[:4000]
            requests.post(url, json=payload, timeout=15)

    except Exception as exc:
        print(f"Telegram hatası: {exc}")


def check_domain(domain):
    domain = domain.strip()
    if not domain:
        return "EMPTY"

    urls = [domain] if domain.startswith(("http://", "https://")) else [f"https://{domain}", f"http://{domain}"]

    for url in urls:
        try:
            response = requests.head(
                url,
                timeout=5,
                headers={"User-Agent": "Mozilla/5.0"},
                allow_redirects=True
            )
            return str(response.status_code)
        except requests.RequestException:
            try:
                response = requests.get(
                    url,
                    timeout=5,
                    headers={"User-Agent": "Mozilla/5.0"},
                    allow_redirects=True,
                    stream=True
                )
                return str(response.status_code)
            except requests.RequestException:
                continue

    return "ERROR"


def create_fallback_table(results_dict):
    """AI yanıt vermezse Python'ın kendi oluşturacağı nizami tablo"""
    lines = [
        "📊 **HAFTALIK DOMAIN DURUM RAPORU**\n",
        "```",
        f"{'DOMAIN':<25} | {'HTTP':<6} | {'DURUM':<12}",
        "-" * 25 + "-|-" + "-" * 6 + "-|-" + "-" * 12
    ]
    
    for domain, status in results_dict.items():
        durum_text = "Erişilebilir" if status == "200" else ("Yönlendirildi" if status in ["301", "302"] else "Erişilemez")
        lines.append(f"{domain:<25} | {status:<6} | {durum_text:<12}")
        
    lines.append("```")
    lines.append("\n💡 **ÖZET:** Sistem taraması otomatik olarak tamamlandı.")
    return "\n".join(lines)


def analyze_with_ai(domain_results):
    prompt = (
        "Aşağıdaki domain kontrol verilerini analiz et ve SADECE aşağıdaki Markdown tablo formatında Türkçe yanıt üret.\n\n"
        "ŞABLON (Asla bu formatın dışına çıkma, giriş/çıkış açıklaması yapma):\n\n"
        "📊 **HAFTALIK DOMAIN DURUM RAPORU**\n\n"
        "```\n"
        "DOMAIN                    | HTTP   | DURUM\n"
        "--------------------------|--------|-------------\n"
        "example1.com              | 200    | Erişilebilir\n"
        "example2.com              | ERROR  | Erişilemez\n"
        "```\n\n"
        "💡 **ÖZET:** [1 cümlelik genel durum özeti]\n\n"
        f"Veriler:\n{domain_results}"
    )

    for model_name in MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and hasattr(response, "text") and response.text:
                    return response.text
            except Exception:
                time.sleep(3)

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

    results_dict = {}
    formatted_results = []

    for domain in domains:
        print(f"Kontrol ediliyor: {domain}")
        status = check_domain(domain)
        # Temiz domain adını alalım
        clean_domain = domain.replace("https://", "").replace("http://", "").strip("/")
        results_dict[clean_domain] = status
        formatted_results.append(f"{clean_domain} -> HTTP: {status}")

    all_data = "\n".join(formatted_results)

    # AI Analizi Al
    report = analyze_with_ai(all_data)

    if report:
        send_telegram_message(report)
    else:
        # AI çalışmasa bile Telegram'a kesinlikle tablo gidecek
        fallback_table = create_fallback_table(results_dict)
        send_telegram_message(fallback_table)

    print("İşlem tamamlandı.")


if __name__ == "__main__":
    main()
