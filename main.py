import urllib3
# SSL uyarılarını konsolda gizlemek için
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check_domain(domain):
    domain = domain.strip()
    if not domain:
        return "EMPTY"

    if domain.startswith(("http://", "https://")):
        urls = [domain]
    else:
        urls = [f"https://{domain}", f"http://{domain}"]

    # Gerçek Chrome tarayıcı başlıkları (WAF ve Bot engellerini aşmak için)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }

    session = requests.Session()

    for url in urls:
        # 1. Aşama: GET isteği ile doğrulama (SSL doğrulaması kapalı)
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
