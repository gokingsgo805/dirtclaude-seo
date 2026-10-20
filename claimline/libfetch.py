import ipaddress
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

UA = "ClaimlineAudit/1.0 (+https://dirtclaude.ai; page audit)"
MAX_BYTES = 1_200_000


class FetchError(Exception):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def validate_url(raw: str):
    text = (raw or "").strip()
    if not text:
        raise FetchError("Enter a URL.")
    if "://" in text and not text.lower().startswith(("http://", "https://")):
        raise FetchError("Use an http or https URL.")
    if not text.lower().startswith(("http://", "https://")):
        text = "https://" + text
    url = urlparse(text)
    if url.scheme not in ("http", "https"):
        raise FetchError("Use an http or https URL.")
    if url.username or url.password:
        raise FetchError("Remove the username and password from the URL.")
    host = (url.hostname or "").lower().rstrip(".")
    if not host:
        raise FetchError("That URL is missing a host.")
    if url.port and url.port not in (80, 443):
        raise FetchError("Only ports 80 and 443 are allowed.")
    if host in {"localhost", "metadata.google.internal"} or host.endswith((".localhost", ".local", ".internal")):
        raise FetchError("That host is blocked.")
    try:
        ipaddress.ip_address(host)
        if not _public(host):
            raise FetchError("That host is blocked.")
    except ValueError:
        pass
    return url


def _resolve(host: str):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise FetchError("Could not resolve that host.") from exc
    ips = []
    for info in infos:
        ip = info[4][0]
        if ip.startswith("::ffff:"):
            ip = ip.split("::ffff:")[-1]
        ips.append(ip)
    if not ips or any(not _public(ip) for ip in ips):
        raise FetchError("That host resolves to a private address.")


def _open(url: str, accept: str, hops: int = 4):
    parsed = validate_url(url)
    _resolve(parsed.hostname)
    req = Request(parsed.geturl(), headers={"User-Agent": UA, "Accept": accept})
    opener = build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=12) as resp:
            body = resp.read(MAX_BYTES + 1)
            status = getattr(resp, "status", 200)
            final = resp.geturl()
            ctype = resp.headers.get("Content-Type", "")
    except HTTPError as exc:
        if 300 <= exc.code < 400 and hops > 0:
            loc = exc.headers.get("Location") if exc.headers else None
            if not loc:
                raise FetchError("Too many redirects.") from exc
            return _open(urljoin(parsed.geturl(), loc), accept, hops - 1)
        body = exc.read(MAX_BYTES + 1)
        status = exc.code
        final = parsed.geturl()
        ctype = exc.headers.get("Content-Type", "") if exc.headers else ""
    except URLError as exc:
        raise FetchError(f"Could not fetch that URL. {exc.reason}") from exc
    if len(body) > MAX_BYTES:
        raise FetchError("Page is over 1.2 MB. Paste the main HTML instead.")
    return status, final, body.decode("utf-8", "replace"), ctype


def fetch_page(url: str):
    return _open(url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1")


def probe(url: str):
    try:
        status, _final, body, _ctype = _open(url, "text/plain,text/html,application/xml;q=0.8,*/*;q=0.1")
        return status, body[:20000]
    except FetchError:
        return None, None
