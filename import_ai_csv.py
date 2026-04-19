import argparse
from typing import Dict

import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

from paid_citation_batch_stats import DB_CONFIG


CSV_COLUMNS = [
    "问题",
    "AI输出的答案",
    "文件名",
    "序号",
    "标题",
    "内容",
    "网站",
    "网站url",
    "文章引用时间",
    "是否为嵌入式引用内容",
    "实际引用次数",
    "AI平台",
]


def build_engine(db_config: Dict[str, str]):
    user = db_config["user"]
    pwd = quote_plus(db_config["password"])
    host = db_config["host"]
    database = db_config["database"]
    charset = db_config.get("charset", "utf8mb4")
    conn_str = f"mysql+pymysql://{user}:{pwd}@{host}/{database}?charset={charset}"
    return create_engine(conn_str)


def parse_citation_time(value):
    text_value = str(value).strip()
    if not text_value or text_value == "无":
        return pd.NaT
    parsed = pd.to_datetime(text_value, format="%Y年%m月%d日", errors="coerce")
    return parsed


def clean_csv(path: str, upload_batch: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing_cols = [col for col in CSV_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"CSV 缺少字段: {missing_cols}")

    work = df[CSV_COLUMNS].copy()
    work["问题"] = work["问题"].astype(str).str.strip()
    work["AI输出的答案"] = work["AI输出的答案"].astype(str)
    work["文件名"] = work["文件名"].astype(str).str.strip()
    work["序号"] = pd.to_numeric(work["序号"], errors="coerce").astype("Int64")
    work["标题"] = work["标题"].astype(str).str.strip()
    work["内容"] = work["内容"].astype(str)
    work["网站"] = work["网站"].astype(str).str.strip()
    work["网站url"] = work["网站url"].astype(str).str.strip()
    work["文章引用时间"] = work["文章引用时间"].apply(parse_citation_time)
    work["是否为我们发布的软文"] = work["是否为嵌入式引用内容"].astype(str).str.strip()
    work["上传批次"] = upload_batch
    work["AI平台"] = work["AI平台"].astype(str).str.strip()

    work = work[
        [
            "问题",
            "AI输出的答案",
            "文件名",
            "序号",
            "标题",
            "内容",
            "网站",
            "网站url",
            "文章引用时间",
            "是否为我们发布的软文",
            "上传批次",
            "AI平台",
        ]
    ].copy()

    work = work[work["网站url"] != ""].reset_index(drop=True)
    return work


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 AI 采集 CSV 到 MySQL 的 AIget_data 表")
    parser.add_argument("csv_path", help="CSV 文件路径")
    parser.add_argument("upload_batch", help="上传批次，例如 260418第一批")
    parser.add_argument("--truncate-batch", action="store_true", help="导入前先删除同批次已有数据")
    args = parser.parse_args()

    df = clean_csv(args.csv_path, args.upload_batch)
    engine = build_engine(DB_CONFIG)

    with engine.begin() as conn:
        if args.truncate_batch:
            conn.execute(text("DELETE FROM AIget_data WHERE 上传批次 = :upload_batch"), {"upload_batch": args.upload_batch})
        df.to_sql("AIget_data", conn, if_exists="append", index=False)

    print(f"imported_rows={len(df)}")
    print(f"upload_batch={args.upload_batch}")


if __name__ == "__main__":
    main()
