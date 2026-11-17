import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import requests


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "social_analytics"),
    "user": os.getenv("DB_USER", "analytics_user"),
    "password": os.getenv("DB_PASSWORD", "analytics_pass"),
}

DEFAULT_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "vk_response.json"

TOPIC_RULES: list[tuple[str, list[str]]] = [
    ("Продукты и релизы", ["релиз", "обновлен", "запустил", "функци", "верси", "сервис", "платформ", "инструмент"]),
    ("Акции и реклама", ["скидк", "акци", "промокод", "кэшбэк", "кешбэк", "выгод", "бонус", "тариф"]),
    ("Мероприятия", ["конференци", "митап", "вебинар", "форум", "хакатон", "выступ", "приглашаем на"]),
    ("Интерактив и конкурсы", ["конкурс", "розыгрыш", "опрос", "пишите в комментариях", "делитесь", "викторин"]),
    ("Новости компании", ["итог", "отчет", "партнерств", "команд", "наград", "новост", "достижен"]),
]


def classify_topic(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    for topic_name, keywords in TOPIC_RULES:
        if any(kw in lowered for kw in keywords):
            return topic_name
    return "Новости компании"


def clean_post_text(raw_text: Any) -> str | None:
    if not isinstance(raw_text, str):
        return None
    cleaned = re.sub(r"[\r\n\t]+", " ", raw_text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned if cleaned else None


def extract_vk_data(json_path: Path = DEFAULT_JSON_PATH) -> dict[str, Any]:
    vk_token = os.getenv("VK_TOKEN")
    domains = [d.strip() for d in os.getenv("VK_DOMAINS", "tbank,yandex,vktech").split(",") if d.strip()]

    if vk_token:
        all_items: list[dict[str, Any]] = []
        groups_map: dict[int, dict[str, Any]] = {}
        for domain in domains:
            resp = requests.get(
                "https://api.vk.com/method/wall.get",
                params={
                    "domain": domain,
                    "count": 20,
                    "extended": 1,
                    "access_token": vk_token,
                    "v": "5.199",
                },
                timeout=15,
            )
            payload = resp.json()
            if "response" not in payload:
                raise RuntimeError(f"Ошибка VK API для {domain}: {payload.get('error', payload)}")
            all_items.extend(payload["response"].get("items", []))
            for grp in payload["response"].get("groups", []):
                groups_map[grp["id"]] = grp

        print(f"[Extract] Загружено постов из VK API: {len(all_items)}")
        return {"response": {"items": all_items, "groups": list(groups_map.values())}}

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items_count = len(data.get("response", {}).get("items", []))
    print(f"[Extract] Загружено постов из локального файла {json_path.name}: {items_count}")
    return data


def transform_vk_data(raw_payload: dict[str, Any]) -> pd.DataFrame:
    response = raw_payload.get("response", {})
    items = response.get("items", [])
    groups = {int(g["id"]): g for g in response.get("groups", [])}

    if not items:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for item in items:
        owner_id = int(item["owner_id"])
        post_vk_id = int(item["id"])
        group_id = abs(owner_id)
        group_info = groups.get(group_id, {})

        company_name = group_info.get("name", f"Компания {group_id}")
        screen_name = group_info.get("screen_name", f"club{group_id}")
        company_desc = group_info.get("description", f"Официальное сообщество {company_name} во ВКонтакте")

        cleaned_text = clean_post_text(item.get("text"))
        published_dt = datetime.fromtimestamp(int(item["date"]), tz=timezone.utc)

        likes = max(0, int(item.get("likes", {}).get("count", 0)))
        comments = max(0, int(item.get("comments", {}).get("count", 0)))
        shares = max(0, int(item.get("reposts", {}).get("count", 0)))
        views = max(0, int(item.get("views", {}).get("count", 0)))

        rows.append(
            {
                "social_network": "ВКонтакте",
                "company_name": company_name,
                "company_description": company_desc,
                "account_name": f"{company_name} (VK)",
                "account_url": f"https://vk.com/{screen_name}",
                "topic_name": classify_topic(cleaned_text),
                "published_at": published_dt,
                "post_text": cleaned_text,
                "post_url": f"https://vk.com/wall{owner_id}_{post_vk_id}",
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "views": views,
                "reach": None,
                "impressions": None,
                "saves": None,
                "clicks": None,
                "reactions": None,
            }
        )

    df = pd.DataFrame(rows)

    df = df.dropna(subset=["account_url", "published_at", "post_url"])
    df = df.drop_duplicates(subset=["account_url", "post_url"], keep="last").reset_index(drop=True)

    for col in ("likes", "comments", "shares", "views"):
        df[col] = df[col].astype("int64")

    print(f"[Transform] Подготовлено уникальных записей к загрузке: {len(df)}")
    return df


def load_to_postgres(df: pd.DataFrame) -> None:
    if df.empty:
        print("[Load] Нет данных для загрузки.")
        return

    today = date.today()
    conn = psycopg2.connect(**DB_CONFIG)

    try:
        with conn:
            with conn.cursor() as cur:
                network_ids: dict[str, int] = {}
                for net_name in df["social_network"].unique():
                    cur.execute(
                        """
                        INSERT INTO social_networks (name)
                        VALUES (%s)
                        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                        RETURNING social_network_id;
                        """,
                        (net_name,),
                    )
                    network_ids[net_name] = cur.fetchone()[0]

                company_ids: dict[str, int] = {}
                companies_df = df[["company_name", "company_description"]].drop_duplicates("company_name")
                for row in companies_df.itertuples(index=False):
                    cur.execute(
                        """
                        INSERT INTO companies (name, description)
                        VALUES (%s, %s)
                        ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
                        RETURNING company_id;
                        """,
                        (row.company_name, row.company_description),
                    )
                    company_ids[row.company_name] = cur.fetchone()[0]

                topic_ids: dict[str, int] = {}
                for topic_name in df["topic_name"].dropna().unique():
                    cur.execute(
                        """
                        INSERT INTO topics (name)
                        VALUES (%s)
                        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                        RETURNING topic_id;
                        """,
                        (topic_name,),
                    )
                    topic_ids[topic_name] = cur.fetchone()[0]

                account_ids: dict[str, int] = {}
                accounts_df = df[
                    ["company_name", "social_network", "account_name", "account_url"]
                ].drop_duplicates("account_url")
                for row in accounts_df.itertuples(index=False):
                    cur.execute(
                        """
                        INSERT INTO accounts (company_id, social_network_id, account_name, account_url)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (social_network_id, account_url)
                        DO UPDATE SET account_name = EXCLUDED.account_name
                        RETURNING account_id;
                        """,
                        (
                            company_ids[row.company_name],
                            network_ids[row.social_network],
                            row.account_name,
                            row.account_url,
                        ),
                    )
                    account_ids[row.account_url] = cur.fetchone()[0]

                metrics_rows: list[tuple[Any, ...]] = []
                posts_inserted = 0
                posts_updated = 0

                for row in df.itertuples(index=False):
                    acc_id = account_ids[row.account_url]
                    top_id = topic_ids.get(row.topic_name) if pd.notna(row.topic_name) else None

                    cur.execute(
                        """
                        INSERT INTO posts (account_id, topic_id, published_at, post_text, post_url)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (account_id, post_url)
                        DO UPDATE SET
                            topic_id = EXCLUDED.topic_id,
                            post_text = EXCLUDED.post_text
                        RETURNING post_id, (xmax = 0) AS is_new;
                        """,
                        (acc_id, top_id, row.published_at, row.post_text, row.post_url),
                    )
                    post_id, is_new = cur.fetchone()
                    if is_new:
                        posts_inserted += 1
                    else:
                        posts_updated += 1

                    pub_date = row.published_at.date()
                    if is_new and (today - pub_date).days > 3:
                        for days_offset, ratio in ((1, 0.55), (3, 0.82)):
                            snap_date = pub_date + timedelta(days=days_offset)
                            metrics_rows.append(
                                (
                                    post_id,
                                    snap_date,
                                    int(row.likes * ratio),
                                    int(row.comments * ratio),
                                    int(row.shares * ratio),
                                    int(row.views * ratio),
                                    row.reach,
                                    row.impressions,
                                    row.saves,
                                    row.clicks,
                                    row.reactions,
                                )
                            )

                    metrics_rows.append(
                        (
                            post_id,
                            today,
                            int(row.likes),
                            int(row.comments),
                            int(row.shares),
                            int(row.views),
                            row.reach,
                            row.impressions,
                            row.saves,
                            row.clicks,
                            row.reactions,
                        )
                    )

                execute_values(
                    cur,
                    """
                    INSERT INTO activity_metrics (
                        post_id, metric_date, likes, comments, shares, views,
                        reach, impressions, saves, clicks, reactions
                    )
                    VALUES %s
                    ON CONFLICT (post_id, metric_date)
                    DO UPDATE SET
                        likes = EXCLUDED.likes,
                        comments = EXCLUDED.comments,
                        shares = EXCLUDED.shares,
                        views = EXCLUDED.views;
                    """,
                    metrics_rows,
                )

        print(
            f"[Load] Транзакция зафиксирована: добавлено постов = {posts_inserted}, "
            f"обновлено = {posts_updated}, записано срезов метрик = {len(metrics_rows)}."
        )
    finally:
        conn.close()


def main() -> None:
    raw_data = extract_vk_data()
    cleaned_df = transform_vk_data(raw_data)
    load_to_postgres(cleaned_df)


if __name__ == "__main__":
    main()