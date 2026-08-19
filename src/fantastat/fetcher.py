from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient


DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DATABASE = "fantastat"

DEFAULT_LLM_BASE_URL = "http://localhost:11434/v1/chat/completions"
DEFAULT_LLM_MODEL = "llama3.1"

DEFAULT_TIMEOUT = 20
DEFAULT_MAX_ARTICLES = 6
DEFAULT_MAX_ARTICLE_CHARS = 6000
DEFAULT_MAX_CONTEXT_CHARS = 24000

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)


def log(message: str, *, verbose: bool = False) -> None:
    if verbose:
        print(message)


def log_warning(message: str) -> None:
    print(f"warning: {message}")


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _slug(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9àèéìòù]+", "_", text)
    return text.strip("_")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_llm_url(base_url: str) -> str:
    base_url = base_url.rstrip("/")

    if base_url.endswith("/chat/completions"):
        return base_url

    if base_url.endswith("/v1"):
        return f"{base_url}/chat/completions"

    return f"{base_url}/v1/chat/completions"


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    return _clean_text(soup.get_text(" "))


def _rss_query_url(query: str, *, language: str = "it", country: str = "IT") -> str:
    encoded = quote_plus(query)
    return (
        "https://news.google.com/rss/search"
        f"?q={encoded}"
        f"&hl={language}"
        f"&gl={country}"
        f"&ceid={country}:{language}"
    )


def _parse_rss_datetime(value: str | None) -> str | None:
    if not value:
        return None
    return _clean_text(value)


def fetch_google_news_rss(
    query: str,
    *,
    max_articles: int,
    timeout: int,
    language: str = "it",
    country: str = "IT",
    proxies: dict[str, str] | None = None,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    url = _rss_query_url(query, language=language, country=country)

    log(f"rss: query={query}", verbose=verbose)
    log(f"rss: url={url}", verbose=verbose)

    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        proxies=proxies,
    )
    response.raise_for_status()

    log(
        f"rss: status={response.status_code}, bytes={len(response.content)}",
        verbose=verbose,
    )

    root = ET.fromstring(response.content)

    items: list[dict[str, Any]] = []

    for item in root.findall(".//item"):
        title = _clean_text(item.findtext("title"))
        link = _clean_text(item.findtext("link"))
        description = _strip_html(item.findtext("description"))
        published = _parse_rss_datetime(item.findtext("pubDate"))

        source_node = item.find("source")
        source = _clean_text(source_node.text if source_node is not None else "")

        if not title or not link:
            continue

        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "published": published,
                "snippet": description,
            }
        )

        if len(items) >= max_articles:
            break

    log(f"rss: found={len(items)}", verbose=verbose)

    return items


def extract_article_text(
    url: str,
    *,
    timeout: int,
    max_chars: int,
    proxies: dict[str, str] | None = None,
    verbose: bool = False,
) -> str:
    log(f"article: downloading={url}", verbose=verbose)

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            proxies=proxies,
        )
        response.raise_for_status()
    except Exception as error:
        log_warning(f"article download failed: {url}: {error}")
        return ""

    content_type = response.headers.get("content-type", "")

    log(
        (
            "article: "
            f"status={response.status_code}, "
            f"content_type={content_type}, "
            f"bytes={len(response.content)}"
        ),
        verbose=verbose,
    )

    if "html" not in content_type.lower():
        log(f"article: skipped non-html={url}", verbose=verbose)
        return ""

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(
        ["script", "style", "noscript", "svg", "form", "nav", "footer", "header"]
    ):
        tag.decompose()

    article = soup.find("article")
    scope = article if article else soup

    paragraphs = [
        _clean_text(p.get_text(" "))
        for p in scope.find_all(["p", "h1", "h2", "h3", "li"])
    ]

    text = "\n".join(p for p in paragraphs if len(p) >= 40)
    text = _clean_text(text)

    log(f"article: extracted_chars={len(text)}", verbose=verbose)

    return text[:max_chars]


def build_player_query(player: dict[str, Any]) -> str:
    name = str(player.get("name") or player.get("_id") or "").strip()

    team = None
    seasons = player.get("seasons")

    if isinstance(seasons, dict) and seasons:
        latest_year = sorted(seasons)[-1]
        attrs = seasons.get(latest_year, {}).get("attrs", {})

        if isinstance(attrs, dict):
            team = attrs.get("team")

    parts = [name]

    if team:
        parts.append(str(team))

    parts.extend(["Serie A", "fantacalcio", "news"])

    return " ".join(parts)


def build_llm_messages(
    *,
    player: dict[str, Any],
    articles: list[dict[str, Any]],
) -> list[dict[str, str]]:
    player_name = str(player.get("name") or player.get("_id"))

    article_blocks = []

    for idx, article in enumerate(articles, start=1):
        block = f"""
ARTICLE {idx}
Title: {article.get("title")}
Source: {article.get("source")}
Published: {article.get("published")}
URL: {article.get("url")}

Snippet:
{article.get("snippet") or ""}

Extracted text:
{article.get("text") or ""}
""".strip()
        article_blocks.append(block)

    context = "\n\n---\n\n".join(article_blocks)

    system = """
You are a football analyst building a concise wiki-like dossier for a Fantacalcio dashboard.

Rules:
- Use only the provided sources.
- Do not invent facts.
- If information is missing, write "Not found in the collected sources".
- Keep the output in Markdown.
- Use clear section headings.
- Be concise.
- Mention uncertainty explicitly.
""".strip()

    user = f"""
Player: {player_name}

Build exactly this Markdown template:

# {player_name}

## Current status

## Tactical role

## Minutes outlook

## Injuries and availability

## Transfer rumours

## Competition for place

## Fantasy football impact

## Risks

## Confidence

## Sources

Use bullet points where useful.
The Sources section must contain the URLs used.

Collected sources:

{context}
""".strip()

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def call_openai_compatible_llm(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: int,
    verbose: bool = False,
) -> str:
    url = _normalise_llm_url(base_url)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "stream": False,
    }

    log(f"llm: url={url}", verbose=verbose)
    log(f"llm: model={model}", verbose=verbose)
    log(f"llm: messages={len(messages)}", verbose=verbose)
    payload_chars = sum(
        len(json.dumps(m))
        for m in messages
    )

    log(f"llm: payload_chars={payload_chars}", verbose=verbose)

    response = requests.post(
        url,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()

    try:
        content = data["choices"][0]["message"]["content"].strip()
    except Exception as error:
        raise RuntimeError(f"Unexpected LLM response format: {data}") from error

    log(f"llm: output_chars={len(content)}", verbose=verbose)

    return content


class PlayerInfoFetcher:
    def __init__(
        self,
        *,
        database: Any,
        llm_base_url: str,
        llm_model: str,
        timeout: int,
        max_articles: int,
        max_article_chars: int,
        max_context_chars: int,
        force: bool,
        proxies: dict[str, str] | None = None,
        verbose: bool = False,
    ):
        self.db = database
        self.llm_base_url = llm_base_url
        self.llm_model = llm_model
        self.timeout = timeout
        self.max_articles = max_articles
        self.max_article_chars = max_article_chars
        self.max_context_chars = max_context_chars
        self.force = force
        self.proxies = proxies
        self.verbose = verbose

    def iter_players(
        self,
        *,
        player: str | None,
        limit: int | None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}

        if player:
            pattern = re.escape(player)
            query = {
                "$or": [
                    {"_id": {"$regex": pattern, "$options": "i"}},
                    {"name": {"$regex": pattern, "$options": "i"}},
                ]
            }

        log(f"mongo: player_query={query}", verbose=self.verbose)

        cursor = self.db["players"].find(query).sort("name", 1)

        if limit:
            cursor = cursor.limit(limit)

        players = list(cursor)

        log(f"mongo: players_found={len(players)}", verbose=self.verbose)

        return players

    def build_dossier(self, player: dict[str, Any]) -> dict[str, Any]:
        player_key = str(player.get("_id") or _slug(str(player.get("name"))))
        query = build_player_query(player)

        log(f"player: key={player_key}, name={player.get('name')}", verbose=self.verbose)
        log(f"player: query={query}", verbose=self.verbose)

        rss_items = fetch_google_news_rss(
            query,
            max_articles=self.max_articles,
            timeout=self.timeout,
            proxies=self.proxies,
            verbose=self.verbose,
        )

        articles: list[dict[str, Any]] = []

        for item in rss_items:
            item = dict(item)

            try:
                item["text"] = extract_article_text(
                    item["url"],
                    timeout=self.timeout,
                    max_chars=self.max_article_chars,
                    proxies=self.proxies,
                    verbose=self.verbose,
                )
            except Exception as error:
                log_warning(
                    (
                        f"{player.get('name')}: "
                        f"cannot download {item.get('url')}: "
                        f"{type(error).__name__}: {error}"
                    )
                )
                item["text"] = ""

            articles.append(item)

        source_fingerprint = _hash_payload(
            [
                {
                    "title": article.get("title"),
                    "url": article.get("url"),
                    "published": article.get("published"),
                    "snippet": article.get("snippet"),
                    "text_hash": _hash_payload(article.get("text") or ""),
                }
                for article in articles
            ]
        )

        log(
            f"player: source_fingerprint={source_fingerprint}",
            verbose=self.verbose,
        )

        existing = self.db["player_dossiers"].find_one({"_id": player_key})

        if (
            existing
            and not self.force
            and existing.get("source_fingerprint") == source_fingerprint
        ):
            log(f"player: cached={player_key}", verbose=self.verbose)

            return {
                "status": "cached",
                "_id": player_key,
                "name": player.get("name"),
            }

        limited_articles = self._limit_context(articles)

        context_chars = sum(len(article.get("text") or "") for article in limited_articles)
        log(f"llm: context_chars={context_chars}", verbose=self.verbose)

        messages = build_llm_messages(
            player=player,
            articles=limited_articles,
        )

        markdown = call_openai_compatible_llm(
            base_url=self.llm_base_url,
            model=self.llm_model,
            messages=messages,
            timeout=max(self.timeout, 120),
            verbose=self.verbose,
        )

        document = {
            "_id": player_key,
            "player_id": player.get("player_id"),
            "name": player.get("name"),
            "query": query,
            "generated_at": _utc_now(),
            "llm": {
                "base_url": self.llm_base_url,
                "model": self.llm_model,
            },
            "source_fingerprint": source_fingerprint,
            "sources": [
                {
                    "title": article.get("title"),
                    "url": article.get("url"),
                    "source": article.get("source"),
                    "published": article.get("published"),
                    "snippet": article.get("snippet"),
                    "domain": urlparse(article.get("url") or "").netloc,
                    "text_chars": len(article.get("text") or ""),
                }
                for article in articles
            ],
            "markdown": markdown,
        }

        self.db["player_dossiers"].replace_one(
            {"_id": player_key},
            document,
            upsert=True,
        )

        log(f"mongo: dossier_upserted={player_key}", verbose=self.verbose)

        return {
            "status": "updated",
            "_id": player_key,
            "name": player.get("name"),
            "sources": len(articles),
        }

    def _limit_context(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        used = 0

        for article in articles:
            article = dict(article)
            text = article.get("text") or ""
            available = max(self.max_context_chars - used, 0)

            if available <= 0:
                break

            if len(text) > available:
                text = text[:available]

            article["text"] = text
            used += len(text)
            result.append(article)

        log(
            f"context: articles={len(result)}, chars={used}",
            verbose=self.verbose,
        )

        return result

    def run(
        self,
        *,
        player: str | None,
        limit: int | None,
    ) -> list[dict[str, Any]]:
        players = self.iter_players(player=player, limit=limit)

        results = []

        for item in players:
            try:
                result = self.build_dossier(item)
            except Exception as error:
                result = {
                    "status": "error",
                    "_id": item.get("_id"),
                    "name": item.get("name"),
                    "error_type": type(error).__name__,
                    "error": str(error),
                }

            results.append(result)

        return results


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fantastat fetchinfo",
        description="Fetch RSS player news and generate LLM dossiers.",
    )

    parser.add_argument(
        "--uri",
        default=DEFAULT_MONGO_URI,
        help="MongoDB URI",
    )
    parser.add_argument(
        "--database",
        default=DEFAULT_DATABASE,
        help="MongoDB database name",
    )
    parser.add_argument(
        "--player",
        default=None,
        help="Player name or player key filter. If omitted, all players are processed.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of players to process.",
    )
    parser.add_argument(
        "--llm-url",
        default=DEFAULT_LLM_BASE_URL,
        help="OpenAI-compatible base URL. Default: http://localhost:11434",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_LLM_MODEL,
        help="LLM model name exposed by the local OpenAI-compatible API.",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=DEFAULT_MAX_ARTICLES,
        help="Maximum RSS articles per player.",
    )
    parser.add_argument(
        "--max-article-chars",
        type=int,
        default=DEFAULT_MAX_ARTICLE_CHARS,
        help="Maximum extracted characters per article.",
    )
    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=DEFAULT_MAX_CONTEXT_CHARS,
        help="Maximum article text characters sent to the LLM.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate dossiers even if source fingerprint is unchanged.",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Proxy URL for RSS and article downloads. Not used for local LLM calls.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed fetch, extraction and LLM diagnostics.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    proxies = (
        {"http": args.proxy, "https": args.proxy}
        if args.proxy
        else None
    )

    client = MongoClient(args.uri)
    db = client[args.database]

    fetcher = PlayerInfoFetcher(
        database=db,
        llm_base_url=args.llm_url,
        llm_model=args.model,
        timeout=args.timeout,
        max_articles=args.max_articles,
        max_article_chars=args.max_article_chars,
        max_context_chars=args.max_context_chars,
        force=args.force,
        proxies=proxies,
        verbose=args.verbose,
    )

    results = fetcher.run(
        player=args.player,
        limit=args.limit,
    )

    updated = sum(1 for result in results if result["status"] == "updated")
    cached = sum(1 for result in results if result["status"] == "cached")
    errors = [result for result in results if result["status"] == "error"]

    for result in results:
        status = result["status"]
        name = result.get("name") or result.get("_id")

        if status == "updated":
            print(f"updated: {name} ({result.get('sources', 0)} sources)")
        elif status == "cached":
            print(f"cached: {name}")
        else:
            print(
                f"error: {name}: "
                f"{result.get('error_type')}: "
                f"{result.get('error')}"
            )

    print(f"Done: updated={updated}, cached={cached}, errors={len(errors)}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())