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
    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            print(f"❌ Telegram Hatası ({response.status_code}): {response.text}")
        else:
            print("✅ Telegram mesajı başarıyla gönderildi!")
    except Exception as e:
        print(f"❌ Telegram bağlantı hatası: {e}")

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
    
    # Denenecek modeller
    models = ['gemini-2.5-flash', 'gemini-2.0-flash']
    
    for model_name in models:
        for attempt in range(2):
            try:
                print(f"🤖 {model_name} deneniyor (Deneme {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                print(f"⚠️ {model_name} hatası: {e}")
                time.sleep(5)
                
    return None

def main():
    if not os.path.exists("domains.txt"):
        send_telegram_message("❌ `domains.txt` dosyası bulunamadı!")
        return

    with open("domains.txt", "r") as f:
        domains = [line.strip() for line in f if line.strip()]

    if not domains:
        send_telegram_message("⚠️ `domains.txt` dosyası boş, kontrol edilecek domain yok.")
        return

    results = []
    for domain in domains:
        status, content = check_domain(domain)
        results.append(f"Domain: {domain}\nStatus: {status}\nİçerik Özeti: {content[:300]}\n---")

    all_data = "\n".join(results)
    
    # AI Analizini Al
    report = analyze_with_ai(all_data)
    
    if report:
        send_telegram_message(f"📊 **Haftalık Domain Durum Raporu**\n\n{report}")
    else:
        # AI yanıt vermese bile Telegram'a ham veriyi gönder
        send_telegram_message(f"⚠️ AI özet üretemedi, ancak domainler tarandı:\n\n{all_data[:1500]}")

if __name__ == "__main__":
    main()
