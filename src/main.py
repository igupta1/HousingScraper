import argparse
import logging
import sys
from typing import List

from . import config, dedupe, filters, notifier
from .models import Listing
from .scrapers.craigslist import CraigslistScraper
from .scrapers.reddit import RedditScraper
from .scrapers.zillow import ZillowScraper


log = logging.getLogger("main")


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _scrape_and_store(scrapers) -> int:
    total_new = 0
    for scraper in scrapers:
        try:
            raw = scraper.fetch()
        except Exception as e:
            log.exception("%s scraper crashed: %s", scraper.name, e)
            continue
        matched = filters.apply(raw)
        new = dedupe.insert_new(config.DB_PATH, matched)
        log.info("%s: %d raw -> %d matched -> %d new",
                 scraper.name, len(raw), len(matched), len(new))
        total_new += len(new)
    return total_new


def _send_pending() -> int:
    pending: List[Listing] = dedupe.fetch_pending_notifications(config.DB_PATH)
    if not pending:
        log.info("no pending notifications")
        return 0
    log.info("sending digest for %d pending listings", len(pending))
    notifier.send_digest(pending)
    dedupe.mark_notified(config.DB_PATH, [l.dedup_key for l in pending])
    return len(pending)


def run_fast() -> None:
    """Craigslist + Reddit + send digest of all unsent listings."""
    log.info("=== FAST tick: Craigslist + Reddit + notify ===")
    new_count = _scrape_and_store([CraigslistScraper(), RedditScraper()])
    sent = _send_pending()
    log.info("fast tick done: %d new this run, %d notified", new_count, sent)


def run_zillow() -> None:
    """Zillow only — no email; the next fast tick will pick up new rows."""
    log.info("=== ZILLOW tick ===")
    new_count = _scrape_and_store([ZillowScraper()])
    log.info("zillow tick done: %d new", new_count)


def main(argv=None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(description="SF apartment monitor")
    parser.add_argument(
        "mode",
        choices=["fast", "zillow", "all"],
        help="fast = CL+Reddit+notify; zillow = Zillow only; all = everything + notify",
    )
    args = parser.parse_args(argv)

    try:
        if args.mode == "fast":
            run_fast()
        elif args.mode == "zillow":
            run_zillow()
        elif args.mode == "all":
            _scrape_and_store([
                CraigslistScraper(), RedditScraper(), ZillowScraper(),
            ])
            _send_pending()
        return 0
    except Exception as e:
        log.exception("fatal: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
