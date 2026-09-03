import smtplib
from email.message import EmailMessage
from html import escape
from typing import List

from . import config
from .models import Listing


def _format_price(value):
    return f"${value:,}" if isinstance(value, (int, float)) else "?"


def _header_line(listing: Listing) -> str:
    hood = (listing.neighborhood or "SF").strip().title()
    bath = f"{listing.bathrooms:g}" if listing.bathrooms is not None else "?"
    ppb = listing.price_per_bedroom
    ppb_str = f"${ppb:,.0f}/bed" if ppb is not None else "?/bed"
    return (
        f"[{listing.source}] {hood} - {_format_price(listing.price)} total "
        f"· {listing.bedrooms or '?'}BR / {bath}BA "
        f"· {ppb_str}"
    )


def _listing_html_block(listing: Listing) -> str:
    header = _header_line(listing)
    title = listing.title or ""
    address = listing.address or ""
    # Avoid showing the same string twice if title and address are identical.
    show_title = title and title != address
    return f"""
    <div style="margin-bottom:18px;padding:12px;border-left:3px solid #2b7;background:#f8faf9;">
      <div style="font-size:15px;font-weight:600;margin-bottom:6px;">
        {escape(header)}
      </div>
      {f'<div style="color:#444;margin-bottom:4px;">{escape(title)}</div>' if show_title else ''}
      {f'<div style="color:#666;margin-bottom:6px;">{escape(address)}</div>' if address else ''}
      <div><a href="{escape(listing.url)}">{escape(listing.url)}</a></div>
    </div>
    """


def _filter_summary() -> str:
    beds = (
        f"{config.MIN_BEDS}BR"
        if config.MIN_BEDS == config.MAX_BEDS
        else f"{config.MIN_BEDS}-{config.MAX_BEDS}BR"
    )
    hoods = " / ".join(h.title() for h in config.NEIGHBORHOODS)
    return (
        f"{beds}, ${config.MIN_PRICE_PER_BED:,}-${config.MAX_PRICE_PER_BED:,}/bed, {hoods}"
    )


def build_digest(listings: List[Listing]) -> tuple[str, str, str]:
    count = len(listings)
    subject = f"[SF Apt] {count} new match{'es' if count != 1 else ''}"

    blocks = "\n".join(_listing_html_block(l) for l in listings)
    html_body = f"""
    <html><body style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;">
      <div style="max-width:640px;">
        <h2 style="margin-bottom:4px;">SF Apartment Monitor</h2>
        <p style="color:#666;margin-top:0;">{count} new match{'es' if count != 1 else ''} since last check.</p>
        {blocks}
        <p style="color:#999;font-size:12px;">Filter: {_filter_summary()}</p>
      </div>
    </body></html>
    """

    text_lines = [f"SF Apartment Monitor — {count} new match(es)\n"]
    for l in listings:
        text_lines.append(_header_line(l))
        if l.title and l.title != (l.address or ""):
            text_lines.append(f"  {l.title}")
        if l.address:
            text_lines.append(f"  {l.address}")
        text_lines.append(f"  {l.url}")
        text_lines.append("")
    text_body = "\n".join(text_lines)

    return subject, text_body, html_body


def _recipients() -> List[str]:
    raw = config.ALERT_TO_EMAIL or ""
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def send_digest(listings: List[Listing]) -> None:
    if not listings:
        return
    recipients = _recipients()
    if not (config.GMAIL_USER and config.GMAIL_APP_PASSWORD and recipients):
        raise RuntimeError("Gmail credentials or recipient not configured")

    subject, text_body, html_body = build_digest(listings)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_USER
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
        smtp.send_message(msg)
