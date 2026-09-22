```python
import os
import time
import requests

from google import genai
from google.genai import errors


# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN bulunamadı!")

if not TELEGRAM_CHAT_ID:
    print("❌ TELEGRAM_CHAT_ID bulunamadı!")

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY bulunamadı!")


client = genai.Client(api_key=GEMINI_API_KEY)


# Gemini modelleri
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram_message(message):
    """
    Telegram'a mesaj gönderir.

    Önce Markdown ile dener.
    Markdown problemi olursa düz text olarak tekrar dener.
    """

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram bilgileri eksik.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        if response.ok:
            print("✅ Telegram mesajı başarıyla gönderildi!")
            return

        print(
            f"⚠️ Telegram Markdown mesajı gönderilemedi "
            f"({response.status_code}): {response.text}"
        )

        # Markdown yüzünden hata olduysa düz text dene
        payload.pop("parse_mode", None)

        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        if response.ok:
            print("✅ Telegram mesajı düz text olarak gönderildi!")
        else:
            print(
                f"❌ Telegram mesajı gönderilemedi "
                f"({response.status_code}): {response.text}"
            )

    except requests.RequestException as e:
        print(f"❌ Telegram bağlantı hatası: {e}")


# ============================================================
# DOMAIN CHECK
# ============================================================

def check_domain(domain):
    """
    Domain'i kontrol eder.

    Önce HTTPS,
    sonra HTTP denenir.

    Sonuç:
        status
        content
        final_url
    """

    domain = domain.strip()

    if not domain:
        return "EMPTY", "", ""

    # Eğer kullanıcı zaten http/https yazdıysa aynen kullan
    if domain.startswith("http://") or domain.startswith("https://"):
        urls = [domain]
    else:
        urls = [
            f"https://{domain}",
            f"http://{domain}"
        ]

    last_error = None

    for url in urls:

        try:

            print(f"🌐 Kontrol ediliyor: {url}")

            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "(Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 "
                        "(KHTML, like Gecko) "
                        "Chrome/140.0 Safari/537.36"
                    )
                },
                allow_redirects=True
            )

            print(
                f"   → HTTP {response.status_code} "
                f"→ {response.url}"
            )

            return (
                response.status_code,
                response.text[:2000],
                response.url
            )

        except requests.RequestException as e:

            last_error = str(e)

            print(
                f"⚠️ {url} erişilemedi: {last_error}"
            )

    return "ERROR", last_error or "Bilinmeyen hata", ""


# ============================================================
# AI ANALYSIS
# ============================================================

def analyze_with_ai(domain_results):

    prompt = f"""
Sen domain takip sistemi için çalışan bir analiz asistanısın.

Aşağıdaki domain tarama sonuçlarını analiz et.

Her domain için özellikle şunları değerlendir:

1. Domain erişilebilir mi?
2. HTTP durum kodu nedir?
3. Başka bir adrese yönlendirilmiş mi?
4. Domain satış sayfası gibi görünüyor mu?
5. Sedo, GoDaddy, Afternic veya benzeri domain parking/satış
   hizmetlerinden biri görünüyor mu?
6. "This domain is for sale", "Buy this domain",
   "Domain parked", "Make an offer" gibi ifadeler var mı?
7. Domain kapanmış veya kullanılmıyor gibi mi?
8. Normal çalışan bir web sitesi gibi mi?
9. Önceki sahip değişikliğine işaret eden belirgin bir durum var mı?

ÖNEMLİ:

Sadece verilen HTML/içerik ve HTTP bilgilerine dayan.

Kesin olarak bilinmeyen bir şeyi gerçekmiş gibi söyleme.

Örneğin:

"Satışta" yerine
"Satışta olabileceğine işaret ediyor"

gibi ifadeler kullan.

Sonucu Türkçe hazırla.

Telegram'da okunabilecek şekilde kısa ve anlaşılır yaz.

Emoji kullan.

Her domain için:

🌐 DOMAIN

🟢 / 🟡 / 🔴 DURUM

Kısa açıklama

şeklinde rapor oluştur.

En sonunda:

📌 GENEL ÖZET

başlığı altında önemli değişiklikleri belirt.

Taranan veriler:

{domain_results}
"""

    # ========================================================
    # MODEL + RETRY
    # ========================================================

    for model_name in MODELS:

        print(
            f"\n🤖 Model kullanılacak: {model_name}"
        )

        # Her model için 4 deneme
        for attempt in range(4):

            try:

                print(
                    f"   Deneme {attempt + 1}/4..."
                )

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                # Boş response kontrolü
                if not response:
                    raise RuntimeError(
                        "Gemini boş response döndürdü."
                    )

                if not response.text:
                    raise RuntimeError(
                        "Gemini response.text boş."
                    )

                print(
                    f"✅ {model_name} başarılı!"
                )

                return response.text

            except errors.APIError as e:

                print(
                    f"⚠️ Gemini API hatası: {e}"
                )

                # HTTP status kodunu mümkünse al
                status_code = getattr(
                    e,
                    "code",
                    None
                )

                # Geçici hatalar
                retryable_codes = {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504
                }

                if status_code not in retryable_codes:

                    print(
                        "❌ Bu hata retry gerektirmiyor."
                    )

                    break

                # Exponential backoff
                wait_time = min(
                    5 * (2 ** attempt),
                    60
                )

                print(
                    f"⏳ {wait_time} saniye sonra tekrar denenecek..."
                )

                time.sleep(wait_time)

            except Exception as e:

                print(
                    f"⚠️ Beklenmeyen Gemini hatası: {e}"
                )

                wait_time = min(
                    5 * (2 ** attempt),
                    60
                )

                print(
                    f"⏳ {wait_time} saniye bekleniyor..."
                )

                time.sleep(wait_time)

        print(
            f"❌ {model_name} kullanılamadı."
        )

    # ========================================================
    # TÜM MODELLER BAŞARISIZ
    # ========================================================

    print(
        "❌ Tüm Gemini modelleri başarısız oldu."
    )

    return None


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("🚀 DOMAIN TAKİP BOTU BAŞLIYOR")
    print("=" * 60)

    # --------------------------------------------------------
    # domains.txt
    # --------------------------------------------------------

    if not os.path.exists("domains.txt"):

        print(
            "❌ domains.txt dosyası bulunamadı!"
        )

        send_telegram_message(
            "❌ `domains.txt` dosyası bulunamadı!"
        )

        return

    # --------------------------------------------------------
    # DOMAINLERİ OKU
    # --------------------------------------------------------

    try:

        with open(
            "domains.txt",
            "r",
            encoding="utf-8"
        ) as f:

            domains = [
                line.strip()
                for line in f
                if line.strip()
                and not line.strip().startswith("#")
            ]

    except Exception as e:

        print(
            f"❌ domains.txt okunamadı: {e}"
        )

        send_telegram_message(
            f"❌ domains.txt okunamadı:\n{e}"
        )

        return

    # --------------------------------------------------------
    # DOMAIN VAR MI?
    # --------------------------------------------------------

    if not domains:

        print(
            "⚠️ domains.txt boş."
        )

        send_telegram_message(
            "⚠️ `domains.txt` dosyası boş, "
            "takip edilen domain yok."
        )

        return

    print(
        f"📋 {len(domains)} domain bulundu."
    )

    # --------------------------------------------------------
    # DOMAINLERİ TARA
    # --------------------------------------------------------

    results = []

    for index, domain in enumerate(domains, start=1):

        print(
            f"\n[{index}/{len(domains)}] "
            f"{domain}"
        )

        status, content, final_url = check_domain(
            domain
        )

        result = (
            f"Domain: {domain}\n"
            f"HTTP Status: {status}\n"
            f"Final URL: {final_url}\n"
            f"İçerik:\n{content[:1000]}\n"
            f"{'-' * 50}"
        )

        results.append(result)

    # --------------------------------------------------------
    # AI VERİSİ
    # --------------------------------------------------------

    all_data = "\n\n".join(results)

    print(
        "\n🤖 Gemini domain sonuçlarını analiz ediyor..."
    )

    report = analyze_with_ai(
        all_data
    )

    # --------------------------------------------------------
    # RAPOR
    # --------------------------------------------------------

    if report:

        message = (
            "📊 *Haftalık Domain Durum Raporu*\n\n"
            f"{report}"
        )

        send_telegram_message(
            message
        )

    else:

        print(
            "⚠️ AI raporu oluşturulamadı."
        )

        # AI çalışmasa bile Telegram'a
        # ham sonuçları gönder.

        raw_message = (
            "⚠️ *AI raporu oluşturulamadı.*\n\n"
            "🔎 *Ham Domain Tarama Sonuçları:*\n\n"
            f"{all_data[:3500]}"
        )

        send_telegram_message(
            raw_message
        )

    print(
        "\n" + "=" * 60
    )

    print(
        "🏁 DOMAIN TAKİP BOTU TAMAMLANDI"
    )

    print(
        "=" * 60
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
```

Bu sürümde önemli değişiklik şu:

Senin eski kodunda:

```python
except Exception as e:
    print(...)
    time.sleep(5)
```

vardı.

Ama Gemini tarafında zaten otomatik retry mekanizması bulunuyor ve `503 UNAVAILABLE` geçici bir sunucu yoğunluğu hatası olabilir. Google özellikle `503` ve `429` gibi hatalarda exponential backoff öneriyor.

Ben bunu:

```text
1. deneme
   ↓
5 saniye
   ↓
2. deneme
   ↓
10 saniye
   ↓
3. deneme
   ↓
20 saniye
   ↓
4. deneme
   ↓
sonraki Gemini modeli
```

şeklinde yaptım.

Ayrıca **503 gelmesi botun artık crash olmasına neden olmayacak.**

### Senin aldığın hatada tam olarak ne oldu?

Şu:

```text
google.genai.errors.ServerError:
503 UNAVAILABLE
```

Gemini'nin:

> This model is currently experiencing high demand.

demesi.

Yani:

```text
Senin Python kodun
       ↓
Gemini API
       ↓
gemini-2.5-flash
       ↓
503 UNAVAILABLE
```

olmuş.

Bu, API key'in yanlış olduğu anlamına gelmiyor. API key problemi olsaydı tipik olarak `401/403` gibi başka bir hata görürdün. Google'ın hata rehberinde de `503` geçici servis problemi olarak ele alınıyor.

### Bir de önemli bir nokta

Başta gördüğün:

```text
Direct use of automatic function calling (AFC) in
Models.generate_content is not recommended.
```

**crash sebebi değil.**

Sen şu anda herhangi bir function/tool kullanmıyorsun. Normal text generation yapıyorsun ve Google'ın güncel Python örneklerinde de `client.models.generate_content(...)` kullanımı gösteriliyor.

Dolayısıyla şu satırı:

```python
client.models.generate_content(
    model=model_name,
    contents=prompt
)
```

sırf bu uyarı yüzünden değiştirmen gerekmiyor.

### Bir sonraki aşamada botu daha sağlam yapabiliriz

Şu anki botun temel mimarisi:

```text
domains.txt
     ↓
Domain HTTP kontrolü
     ↓
HTML al
     ↓
Gemini
     ↓
Telegram
```

Bunu biraz daha profesyonel hale getirirsek:

```text
                    ┌── HTTPS kontrol
                    │
domains.txt ────────┼── HTTP kontrol
                    │
                    └── Redirect kontrol
                           ↓
                    HTML analiz
                           ↓
                ┌──────────┴──────────┐
                │                     │
          Teknik analiz          Gemini analiz
                │                     │
                └──────────┬──────────┘
                           ↓
                    Değişiklik tespiti
                           ↓
                     Telegram
```

Özellikle **"domain bugün normaldi ama bu hafta satışa çıktı"** bilgisini yakalamak istiyorsan, bir sonraki önemli geliştirme **önceki taramanın sonucunu kaydetmek**. Böylece Gemini'ye yalnızca bugünkü HTML'yi değil:

```text
Geçen hafta:
Normal web sitesi

Bugün:
"This domain is for sale"
```

şeklinde iki sonucu karşılaştırabiliriz.

Bu, senin botun için mevcut halinden çok daha değerli olur.
