import os
import requests
import google.generativeai as genai

# Çevre değişkenlerinden gizli anahtarları al
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def check_domain(domain):
    url = f"http://{domain}" if not domain.startswith("http") else domain
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        status_code = response.status_code
        text_content = response.text[:2000] # İlk 2000 karakteri analiz et
        return status_code, text_content
    except Exception as e:
        return "ERROR", str(e)

def analyze_with_ai(domain_results):
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Aşağıda takip edilen domainlerin bugünkü tarama sonuçları var.
    Her domain için durumu analiz et:
    1. Erişilebilir durumda mı?
    2. Satışa çıkarılmış (sedo, godaddy park vb.), el değiştirmiş veya kapanmış gibi duruyor mu?
    
    Sonuçları kullanıcıya göndermek üzere Türkçe, anlaşılır, emoji içeren kısa ve öz bir haftalık özet rapor haline getir.
    
    Veriler:
    {domain_results}
    """
    
    response = model.generate_content(prompt)
    return response.text

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
    report = analyze_with_ai(all_data)
    
    send_telegram_message(f"📊 **Haftalık Domain Durum Raporu**\n\n{report}")

if __name__ == "__main__":
    main()
