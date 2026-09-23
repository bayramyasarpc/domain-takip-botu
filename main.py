import os
import time
import requests

from google import genai
from google.genai import errors

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")

client = genai.Client(api_key=GEMINI_API_KEY)

MODELS = [
    "gemini-3.6-flash",
    "gemini-2.0-flash",
]


def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram settings are missing.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, json=payload, timeout=15)

        if response.ok:
            print("Telegram message sent.")
            return

        print(
            f"Telegram error: {response.status_code} "
            f"{response.text}"
        )

        if len(message) > 4000:
            message = message[:4000]

        response = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message
            },
            timeout=15
        )

        if not response.ok:
            print(
                f"Telegram retry error: "
                f"{response.status_code} {response.text}"
            )

    except requests.RequestException as exc:
        print(f"Telegram connection error: {exc}")


def check_domain(domain):
    domain = domain.strip()

    if not domain:
        return "EMPTY", "", ""

    if domain.startswith("http://") or domain.startswith("https://"):
        urls = [domain]
    else:
        urls = [
            f"https://{domain}",
            f"http://{domain}"
        ]

    last_error = ""

    for url in urls:
        try:
            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
                allow_redirects=True
            )

            return (
                response.status_code,
                response.text[:3000],
                response.url
            )

        except requests.RequestException as exc:
            last_error = str(exc)

    return "ERROR", last_error, ""


def analyze_with_ai(domain_results):
    prompt = f"""
Analyze the following domain monitoring results.

For every domain determine:

1. Is the domain reachable?
2. What is the HTTP status?
3. Was it redirected?
4. Does it look like a normal website?
5. Does it look like a domain sale page?
6. Are there signs of Sedo, GoDaddy, Afternic or domain parking?
7. Are there phrases such as "domain for sale", "buy this domain",
   "make an offer" or similar?
8. Does the site appear closed or unused?
9. Is there evidence that the domain may have changed ownership?

Use only the supplied HTTP data and page content.
Do not state uncertain conclusions as facts.

Write a short Turkish Telegram report.

Use this structure:

DOMAIN
STATUS
SHORT EXPLANATION

At the end add:

GENEL OZET

Data:

{domain_results}
"""

    for model_name in MODELS:
        print(f"Trying model: {model_name}")

        for attempt in range(4):
            try:
                print(f"Attempt {attempt + 1}/4")

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                if response is None:
                    raise RuntimeError("Empty Gemini response")

                text = getattr(response, "text", None)

                if not text:
                    raise RuntimeError("Empty Gemini response text")

                return text

            except errors.APIError as exc:
                print(f"Gemini API error: {exc}")

                status_code = getattr(exc, "code", None)

                retryable_codes = {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504
                }

                if status_code not in retryable_codes:
                    break

                wait_time = min(5 * (2 ** attempt), 60)
                print(f"Waiting {wait_time} seconds")
                time.sleep(wait_time)

            except Exception as exc:
                print(f"Gemini error: {exc}")

                wait_time = min(5 * (2 ** attempt), 60)
                time.sleep(wait_time)

    return None


def main():
    print("Starting domain monitor")

    if not os.path.exists("domains.txt"):
        send_telegram_message(
            "domains.txt file was not found."
        )
        return

    try:
        with open(
            "domains.txt",
            "r",
            encoding="utf-8"
        ) as file:
            domains = [
                line.strip()
                for line in file
                if line.strip()
                and not line.strip().startswith("#")
            ]

    except Exception as exc:
        print(f"Could not read domains.txt: {exc}")
        send_telegram_message(
            f"Could not read domains.txt: {exc}"
        )
        return

    if not domains:
        send_telegram_message(
            "domains.txt is empty."
        )
        return

    results = []

    for domain in domains:
        print(f"Checking: {domain}")

        status, content, final_url = check_domain(domain)

        result = (
            f"Domain: {domain}\n"
            f"HTTP Status: {status}\n"
            f"Final URL: {final_url}\n"
            f"Content:\n{content[:1500]}\n"
            f"{'-' * 50}"
        )

        results.append(result)

    all_data = "\n\n".join(results)

    report = analyze_with_ai(all_data)

    if report:
        message = (
            "Haftalik Domain Durum Raporu\n\n"
            f"{report}"
        )
    else:
        message = (
            "AI raporu olusturulamadi.\n\n"
            "Ham tarama sonuclari:\n\n"
            f"{all_data[:3500]}"
        )

    send_telegram_message(message)

    print("Domain monitor finished")


if __name__ == "__main__":
    main()
