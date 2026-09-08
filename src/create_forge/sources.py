"""Pure validation and display boundary for untrusted Copier sources."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit, urlunsplit


class SourceError(ValueError):
    """An unsafe source, described without including the supplied value."""


_GUIDANCE = "Use a credential-free source with a Git credential helper or SSH agent."
_CONTROLS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _url_source(source: str) -> str | None:
    """Identify URL forms without interpreting local paths as URLs."""
    candidate = source.removeprefix("git+")
    for shortcut, host in (("gh:", "github.com"), ("gl:", "gitlab.com")):
        if candidate.startswith(shortcut):
            return f"https://{host}/{candidate[len(shortcut) :].lstrip('/')}"
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
        return candidate
    if re.match(r"^(?:https?|ssh):", candidate, re.IGNORECASE):
        raise SourceError("Malformed template URL. " + _GUIDANCE)
    return None


def validate_source(source: str, *, origin: str = "--template-url") -> None:
    """Reject embedded authentication and ambiguous URLs without echoing input."""
    try:
        if not source or source != source.strip() or _CONTROLS.search(source):
            raise SourceError("Invalid template source. " + _GUIDANCE)
        url = _url_source(source)
        if url is None:
            return
        parts = urlsplit(url)
        authority = parts.netloc
        if (
            not parts.hostname
            or "\\" in authority
            or any(char.isspace() for char in authority)
            or unquote(authority) != authority
        ):
            raise SourceError("Malformed template URL authority. " + _GUIDANCE)
        # Accessing port also validates malformed/non-numeric/out-of-range ports.
        _ = parts.port
        if "@" in authority and (
            parts.scheme.lower() != "ssh"
            or parts.password is not None
            or not parts.username
            or authority.count("@") != 1
        ):
            raise SourceError("Embedded URL credentials are not allowed. " + _GUIDANCE)
        if "?" in url or "#" in url:
            raise SourceError(
                "Template URL queries and fragments are not allowed. "
                "Use --ref for template versions. " + _GUIDANCE
            )
        if _CONTROLS.search(unquote(url)):
            raise SourceError("Invalid template URL characters. " + _GUIDANCE)
    except SourceError as exc:
        raise SourceError(f"{origin}: {exc}") from None
    except ValueError:
        # urllib errors may include the authority; never forward their text.
        raise SourceError(f"{origin}: Malformed template URL. {_GUIDANCE}") from None


def display_source(source: str) -> str:
    """Return literal display text with URL authentication/query/fragment removed."""
    if _CONTROLS.search(source):
        return "[invalid template source]"
    try:
        url = _url_source(source)
        if url is None:
            validate_source(source)
            return source
        parts = urlsplit(url)
        clean = urlunsplit(
            (parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", "")
        )
        validate_source(clean)
        return clean
    except ValueError:
        return "[invalid template source]"
