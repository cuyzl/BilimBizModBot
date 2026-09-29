import re
from urllib.parse import urlparse

from allowed_links import ALLOWED_DOMAINS


URL_PATTERN = re.compile(
    r"(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s]*)",
    re.IGNORECASE,
)


def get_domain(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if "@" in domain:
        domain = domain.split("@")[-1]

    domain = domain.split(":")[0]

    return domain


def domain_is_allowed(domain: str) -> bool:
    for allowed in ALLOWED_DOMAINS:
        allowed = allowed.lower()

        if domain == allowed or domain.endswith("." + allowed):
            return True

    return False


def contains_blocked_link(text: str) -> bool:
    if not text:
        return False

    links = URL_PATTERN.findall(text)

    print("Найденные ссылки:", links)

    for link in links:
        domain = get_domain(link)

        print("Домен:", domain)

        if not domain_is_allowed(domain):
            return True

    return False