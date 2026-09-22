import os
import time
import requests
from google import genai

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    response = requests.post(url, json=payload)
    
    if not response.ok:
        print(f"❌ Telegram Hatası ({response.status_code}): {response.text}")
    else:
        print("✅ Telegram mesajı başarıyla gönderildi!")

def check_domain(domain):
    url = f"http://{domain}" if not domain.startswith("http") else domain
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        return response.status_code, response.text[:2000]
    except Exception as e:
        return "ERROR", str(e)

def analyze_with_ai(domain_results):
    prompt = f"""
    Aşağıda takip edilen domainlerin bugünkü tarama sonuçları var.
    Her domain için durumu analiz et:
    1. Erişilebilir durumda mı?
    2. Satışa çıkarılmış (sedo, godaddy park vb.), el değiştirmiş veya kapanmış gibi duruyor mu?
    
    Sonuçları kullanıcıya göndermek üzere Türkçe, anlaşılır, emoji içeren kısa ve öz bir haftalık özet rapor haline getir.
    
    Veriler:
    {domain_results}
    """
    
    # Sırasıyla denenecek güncel modeller
    models = ['gemini-2.5-flash', 'gemini-2.0-flash']
    
    for model_name in models:
        for attempt in range(3):
            try:
                print(f"🤖 {model_name} modeli ile deneniyor (Deneme {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                print(f"⚠️ {model_name} denemesi başarısız oldu: {e}")
                time.sleep(10)  # Sunucunun rahatlaması için 10 saniye bekle
                
    raise Exception("Tüm AI modelleri ve denemeleri sunucu yoğunluğu nedeniyle başarısız oldu.")

def main():
    if not os.path.exists("domains.txt"):
        send_telegram_message("❌ `domains.txt` dosyası bulunamadı!")
        return

    with open("domains.txt", "r") as f:
        domains = [line.strip() for line in f if line.strip()]

    results = []
    for domain in domains:
        status, content = check_domain(domain)
        results.append(f"Domain: {domain}\nStatus: {status}\nİçerik Özeti: {content[:300]}\n---")

    all_data = "\n".join(results)
    
    try:
        report = analyze_with_ai(all_data)
        send_telegram_message(f"📊 **Haftalık Domain Durum Raporu**\n\n{report}")
    except Exception as e:
        print(f"❌ AI analizi tamamen başarısız oldu: {e}")
        # Hata durumunda iş akışının tamamen çökmemesi ve verinin kaybolmaması için ham rapor gönderilir:
        send_telegram_message(f"⚠️ AI sunucuları geçici olarak yoğun olduğu için özet üretilemedi.\n\n**Ham Tarama Verileri:**\n\n{all_data[:1500]}")

if __name__ == "__main__":
    main()
