```python
import os
import time
import requests

from google import genai
from google.genai import errors


# ============================================================
# AYARLAR
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# Gemini client
client = genai.Client(
    api_key=GEMINI_API_KEY
)


# Kullanılacak Gemini modelleri
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


# ============================================================
# TELEGRAM MESAJI GÖNDER
# ============================================================

def send_telegram_message(message):

    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN bulunamadı.")
        return

    if not TELEGRAM_CHAT_ID:
        print("TELEGRAM_CHAT_ID bulunamadı.")
        return

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

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

            print(
                "Telegram mesajı başarıyla gönderildi."
            )

            return

        print(
            f"Telegram Markdown hatası "
            f"({response.status_code}): "
            f"{response.text}"
        )

        # Markdown hata verirse düz text olarak tekrar dene
        payload.pop("parse_mode", None)

        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        if response.ok:

            print(
                "Telegram mesajı düz text olarak gönderildi."
            )

        else:

            print(
                f"Telegram hatası "
                f"({response.status_code}): "
                f"{response.text}"
            )

    except requests.RequestException as e:

        print(
            f"Telegram bağlantı hatası: {e}"
        )


# ============================================================
# DOMAIN KONTROL
# ============================================================

def check_domain(domain):

    domain = domain.strip()

    if not domain:
        return "EMPTY", "", ""

    # Kullanıcı URL vermişse onu kullan
    if domain.startswith("http://"):

        urls = [domain]

    elif domain.startswith("https://"):

        urls = [domain]

    else:

        urls = [
            f"https://{domain}",
            f"http://{domain}"
        ]

    last_error = None

    for url in urls:

        try:

            print(
                f"Kontrol ediliyor: {url}"
            )

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
                f"HTTP Status: {response.status_code}"
            )

            print(
                f"Son URL: {response.url}"
            )

            return (
                response.status_code,
                response.text[:2000],
                response.url
            )

        except requests.RequestException as e:

            last_error = str(e)

            print(
                f"Erişim hatası: {last_error}"
            )

    return (
        "ERROR",
        last_error or "Bilinmeyen hata",
        ""
    )


# ============================================================
# GEMINI ANALİZ
# ============================================================

def analyze_with_ai(domain_results):

    prompt = f"""
Sen bir domain takip sisteminin analiz asistanısın.

Aşağıdaki domain tarama sonuçlarını analiz et.

Her domain için şu bilgileri değerlendir:

1. Domain erişilebilir mi?
2. HTTP status kodu nedir?
3. Başka bir adrese yönlendirilmiş mi?
4. Normal bir web sitesi olarak çalışıyor mu?
5. Domain satış sayfası gibi görünüyor mu?
6. Sedo, GoDaddy, Afternic veya başka domain satış/park
   hizmetlerine ait belirtiler var mı?
7. "This domain is for sale", "Buy this domain",
   "Domain parked", "Make an offer" gibi ifadeler var mı?
8. Site kapanmış veya kullanılmıyor gibi görünüyor mu?
9. El değiştirmiş olabileceğine dair belirgin bir işaret var mı?

ÖNEMLİ:

Sadece verilen HTTP bilgisi ve sayfa içeriğine dayan.

Kesin olmayan durumlarda kesin hüküm verme.

Örneğin:
"Domain kesin satılık"

yerine:

"Domainin satışta olduğuna dair işaretler bulunuyor"

şeklinde yaz.

Sonucu Türkçe hazırla.

Telegram'da okunabilecek kısa ve anlaşılır bir rapor oluştur.

Her domain için şu formatı kullan:

🌐 DOMAIN

🟢 / 🟡 / 🔴 DURUM

Kısa açıklama

Sonunda:

📌 GENEL ÖZET

başlığı altında önemli noktaları özetle.

Domain tarama sonuçları:

{domain_results}
"""

    for model_name in MODELS:

        print(
            f"\nGemini modeli: {model_name}"
        )

        # Her model için 4 kez dene
        for attempt in range(4):

            try:

                print(
                    f"Deneme {attempt + 1}/4"
                )

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                if response is None:

                    raise RuntimeError(
                        "Gemini boş response döndürdü."
                    )

                if not response.text:

                    raise RuntimeError(
                        "Gemini response.text boş."
                    )

                print(
                    "Gemini analizi başarılı."
                )

                return response.text

            except errors.APIError as e:

                print(
                    f"Gemini API hatası: {e}"
                )

                status_code = getattr(
                    e,
                    "code",
                    None
                )

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
                        "Bu hata tekrar denenmeyecek."
                    )

                    break

                # Exponential backoff
                wait_time = min(
                    5 * (2 ** attempt),
                    60
                )

                print(
                    f"{wait_time} saniye bekleniyor."
                )

                time.sleep(wait_time)

            except Exception as e:

                print(
                    f"Beklenmeyen Gemini hatası: {e}"
                )

                wait_time = min(
                    5 * (2 ** attempt),
                    60
                )

                print(
                    f"{wait_time} saniye bekleniyor."
                )

                time.sleep(wait_time)

        print(
            f"{model_name} kullanılamadı."
        )

    return None


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("DOMAIN TAKIP BOTU BASLIYOR")
    print("=" * 60)

    # --------------------------------------------------------
    # domains.txt kontrol
    # --------------------------------------------------------

    if not os.path.exists("domains.txt"):

        print(
            "domains.txt dosyası bulunamadı."
        )

        send_telegram_message(
            "domains.txt dosyası bulunamadı."
        )

        return

    # --------------------------------------------------------
    # Domainleri oku
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
            f"domains.txt okunamadı: {e}"
        )

        send_telegram_message(
            f"domains.txt okunamadı:\n{e}"
        )

        return

    if not domains:

        print(
            "domains.txt boş."
        )

        send_telegram_message(
            "domains.txt boş, takip edilen domain yok."
        )

        return

    print(
        f"{len(domains)} domain bulundu."
    )

    # --------------------------------------------------------
    # Domainleri kontrol et
    # --------------------------------------------------------

    results = []

    for index, domain in enumerate(
        domains,
        start=1
    ):

        print(
            f"\n[{index}/{len(domains)}] {domain}"
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
    # Gemini analiz
    # --------------------------------------------------------

    all_data = "\n\n".join(results)

    print(
        "\nGemini analizine gönderiliyor..."
    )

    report = analyze_with_ai(
        all_data
    )

    # --------------------------------------------------------
    # Telegram raporu
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
            "Gemini raporu oluşturamadı."
        )

        raw_message = (
            "⚠️ *AI raporu oluşturulamadı.*\n\n"
            "🔎 *Ham Tarama Sonuçları:*\n\n"
            f"{all_data[:3500]}"
        )

        send_telegram_message(
            raw_message
        )

    print(
        "\nDOMAIN TAKIP BOTU TAMAMLANDI"
    )


# ============================================================
# PROGRAMI BASLAT
# ============================================================

if __name__ == "__main__":
    main()
```

**Önemli:** Bu kod bloğunun dışındaki açıklamaları `main.py` dosyasına kopyalama. Sadece yukarıdaki kod bloğunun içeriğini dosyaya koy.

Bir de GitHub Actions kullanıyorsan, `GEMINI_API_KEY`, `TELEGRAM_TOKEN` ve `TELEGRAM_CHAT_ID` değerlerinin **Repository → Settings → Secrets and variables → Actions** altında tanımlı olduğundan emin ol.

Bu değişiklikten sonra `503` gelirse bot artık doğrudan:

```text
Process completed with exit code 1
```

ile patlamayacak; önce tekrar deneyecek, sonra `gemini-2.0-flash` modeline geçecek, o da başarısız olursa **ham domain sonuçlarını Telegram'a gönderecek**.

Ayrıca `↓` hatasının sebebi olan açıklama metinlerini tamamen koddan çıkardım.
