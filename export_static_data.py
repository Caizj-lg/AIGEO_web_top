import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from paid_citation_batch_stats import (
    PAID_EXCEL_PATH,
    build_batch_detail,
    build_match_result,
    load_ai_data_from_mysql,
    load_paid_excel,
    DB_CONFIG,
)


BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
DATA_DIR = DOCS_DIR / "data"


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    df_paid, excel_raw_rows = load_paid_excel(str(BASE_DIR / PAID_EXCEL_PATH))
    df_ai, db_total_rows = load_ai_data_from_mysql(DB_CONFIG)
    df_match = build_match_result(df_paid, df_ai)
    df_detail = build_batch_detail(df_match)

    articles_df = df_paid[["软文批次", "文章标题", "网站", "成功发送的URL"]].drop_duplicates().copy()
    batch_detail_df = df_detail.copy()

    articles = articles_df.rename(
        columns={
            "软文批次": "paid_batch",
            "文章标题": "article_title",
            "网站": "website",
            "成功发送的URL": "success_url",
        }
    ).to_dict(orient="records")

    batch_details = batch_detail_df.rename(
        columns={
            "上传批次": "upload_batch",
            "软文批次": "paid_batch",
            "文章标题": "article_title",
            "网站": "website",
            "成功发送的URL": "success_url",
            "本批次引用次数": "citation_count",
        }
    ).to_dict(orient="records")

    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_excel": PAID_EXCEL_PATH,
        "excel_raw_rows": int(excel_raw_rows),
        "excel_valid_rows": int(len(df_paid)),
        "db_total_rows": int(db_total_rows),
        "match_total_rows": int(len(df_match)),
        "article_total": int(len(articles_df)),
        "website_total": int(articles_df["网站"].nunique()),
        "upload_batches": sorted(batch_detail_df["上传批次"].dropna().astype(str).unique().tolist()) if not batch_detail_df.empty else [],
    }

    write_json(DATA_DIR / "articles.json", articles)
    write_json(DATA_DIR / "batch_detail.json", batch_details)
    write_json(DATA_DIR / "meta.json", meta)

    print(f"Exported static data to: {DATA_DIR}")


if __name__ == "__main__":
    main()
