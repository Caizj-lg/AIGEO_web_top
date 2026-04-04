import os
import re
from typing import Dict, List, Tuple
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

PAID_EXCEL_PATH = "GEO项目付费发文_260306_上线版本.xlsx"
OUTPUT_EXCEL_PATH = "GEO付费发文引用统计结果.xlsx"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "qwer1234",
    "database": "rili_db",
    "charset": "utf8mb4",
}


def normalize_url(url: str) -> str:
    if pd.isna(url):
        return ""
    text = str(url).strip().lower()
    if not text:
        return ""
    return text.rstrip("/")


def _normalize_header(name: str) -> str:
    text = str(name).strip().lower()
    return re.sub(r"[\s\-_/:：()（）\[\]【】]", "", text)


def _pick_best_column(columns: List[str], scorer) -> str:
    if not columns:
        return ""
    ranked = sorted(((scorer(c), c) for c in columns), key=lambda x: x[0], reverse=True)
    best_score, best_col = ranked[0]
    return best_col if best_score > 0 else ""


def detect_paid_columns(df: pd.DataFrame) -> Dict[str, str]:
    cols = [str(c) for c in df.columns]

    def score_url(col: str) -> int:
        n = _normalize_header(col)
        score = 0
        if "成功发送的url" in n:
            score += 15
        if "网站url" in n:
            score += 10
        if "url" in n:
            score += 8
        if "链接" in n:
            score += 4
        if "网址" in n:
            score += 3
        if "成功" in n:
            score += 3
        if "发送" in n:
            score += 2
        if "需要发送的网站" in n:
            score -= 5
        return score

    def score_title(col: str) -> int:
        n = _normalize_header(col)
        if "是否一致" in n:
            return -10
        score = 0
        if "文章标题" in n:
            score += 12
        if n == "标题":
            score += 8
        if "标题" in n:
            score += 5
        return score

    def score_batch(col: str) -> int:
        n = _normalize_header(col)
        score = 0
        if "文章批次" in n:
            score += 10
        if "上传批次" in n:
            score += 10
        if "批次" in n:
            score += 4
        return score

    def score_channel(col: str) -> int:
        n = _normalize_header(col)
        score = 0
        if "渠道" in n:
            score += 8
        if "网站" in n or "网址" in n or "媒体" in n:
            score += 3
        return score

    url_col = _pick_best_column(cols, score_url)
    title_col = _pick_best_column(cols, score_title)
    batch_col = _pick_best_column(cols, score_batch)
    channel_col = _pick_best_column(cols, score_channel)

    remark_cols = [
        c for c in cols if any(k in str(c) for k in ["备注", "状态", "相似", "符合率", "标题是否一致"])
    ]

    return {
        "url_col": url_col,
        "title_col": title_col,
        "batch_col": batch_col,
        "channel_col": channel_col,
        "remark_cols": remark_cols,
    }


def clean_paid_excel(df: pd.DataFrame) -> pd.DataFrame:
    col_map = detect_paid_columns(df)
    url_col = col_map["url_col"]
    title_col = col_map["title_col"]
    channel_col = col_map["channel_col"]
    batch_col = col_map["batch_col"]

    if not url_col:
        raise ValueError("无法识别 URL 列（如：成功发送的URL）")
    if not title_col:
        raise ValueError("无法识别标题列（如：文章标题）")

    work = df.copy()

    work["成功发送的URL"] = work[url_col]
    work["文章标题"] = work[title_col].fillna("").astype(str).str.strip()
    if batch_col and batch_col in work.columns:
        work["软文批次"] = work[batch_col].fillna("").astype(str).str.strip()
    else:
        work["软文批次"] = ""
    if channel_col and channel_col in work.columns:
        work["网站"] = work[channel_col].fillna("").astype(str).str.strip()
    else:
        work["网站"] = ""

    for rc in col_map["remark_cols"]:
        if rc not in work.columns:
            work[rc] = ""
        work[rc] = work[rc].fillna("").astype(str)

    hard_invalid_regex = re.compile(r"拒稿|撤稿", re.IGNORECASE)
    wait_feedback_regex = re.compile(r"等待.{0,8}反馈|等待反馈|供应商反馈|待反馈", re.IGNORECASE)

    raw_url = work["成功发送的URL"].fillna("").astype(str)
    has_raw_url = raw_url.str.strip() != ""

    def row_has(pattern: re.Pattern, row) -> bool:
        for rc in col_map["remark_cols"]:
            if pattern.search(str(row.get(rc, ""))):
                return True
        return False

    hard_invalid_mask = work.apply(lambda r: row_has(hard_invalid_regex, r), axis=1)
    wait_only_without_url_mask = work.apply(lambda r: row_has(wait_feedback_regex, r), axis=1) & (~has_raw_url)

    filtered = work[~hard_invalid_mask & ~wait_only_without_url_mask].copy()
    filtered["norm_url"] = filtered["成功发送的URL"].apply(normalize_url)
    filtered = filtered[filtered["norm_url"] != ""].copy()

    filtered = filtered[["软文批次", "文章标题", "网站", "成功发送的URL", "norm_url"]].copy()
    filtered["软文批次"] = filtered["软文批次"].replace("", "(未标注软文批次)")
    filtered["文章标题"] = filtered["文章标题"].replace("", "(未命名标题)")
    filtered["网站"] = filtered["网站"].replace("", "(未标注网站)")
    filtered = filtered.drop_duplicates(subset=["norm_url"], keep="first").reset_index(drop=True)

    return filtered


def load_paid_excel(path: str) -> Tuple[pd.DataFrame, int]:
    df = pd.read_excel(path)
    raw_count = len(df)
    cleaned = clean_paid_excel(df)
    return cleaned, raw_count


def load_ai_data_from_mysql(db_config: Dict[str, str]) -> Tuple[pd.DataFrame, int]:
    user = db_config["user"]
    pwd = quote_plus(db_config["password"])
    host = db_config["host"]
    database = db_config["database"]
    charset = db_config.get("charset", "utf8mb4")

    conn_str = f"mysql+pymysql://{user}:{pwd}@{host}/{database}?charset={charset}"
    query = """
    SELECT 标题, 网站url, 上传批次, 文章引用时间, AI平台
    FROM AIget_data
    """

    engine = create_engine(conn_str)
    with engine.connect() as conn:
        df_ai = pd.read_sql(query, conn)
    raw_count = len(df_ai)

    df_ai["norm_url"] = df_ai["网站url"].apply(normalize_url)
    df_ai = df_ai[df_ai["norm_url"] != ""].copy()
    return df_ai, raw_count


def build_match_result(df_paid: pd.DataFrame, df_ai: pd.DataFrame) -> pd.DataFrame:
    if df_paid.empty or df_ai.empty:
        return pd.DataFrame(
            columns=[
                "上传批次",
                "软文批次",
                "文章标题",
                "网站",
                "成功发送的URL",
                "数据库标题",
                "数据库网站url",
                "AI平台",
                "文章引用时间",
                "norm_url",
            ]
        )

    merged = pd.merge(
        df_paid,
        df_ai,
        how="inner",
        on="norm_url",
        suffixes=("_excel", "_db"),
    )

    result = merged.rename(
        columns={
            "标题": "数据库标题",
            "网站url": "数据库网站url",
        }
    )

    keep_cols = [
        "上传批次",
        "软文批次",
        "文章标题",
        "网站",
        "成功发送的URL",
        "数据库标题",
        "数据库网站url",
        "AI平台",
        "文章引用时间",
        "norm_url",
    ]

    for c in keep_cols:
        if c not in result.columns:
            result[c] = ""

    return result[keep_cols].copy()


def build_batch_detail(df_match: pd.DataFrame) -> pd.DataFrame:
    out_cols = ["上传批次", "软文批次", "文章标题", "网站", "成功发送的URL", "本批次引用次数"]
    if df_match.empty:
        return pd.DataFrame(columns=out_cols)

    detail = (
        df_match.groupby(["上传批次", "软文批次", "文章标题", "网站", "成功发送的URL"], dropna=False)
        .size()
        .reset_index(name="本批次引用次数")
    )

    detail = detail.sort_values(by=["上传批次", "本批次引用次数"], ascending=[True, False]).reset_index(drop=True)
    return detail[out_cols]


def build_batch_summary(df_detail: pd.DataFrame) -> pd.DataFrame:
    out_cols = ["上传批次", "软文数量", "总引用次数", "平均每篇引用次数"]
    if df_detail.empty:
        return pd.DataFrame(columns=out_cols)

    grouped = df_detail.groupby("上传批次", dropna=False)
    summary = grouped.agg(
        软文数量=("成功发送的URL", "nunique"),
        总引用次数=("本批次引用次数", "sum"),
    ).reset_index()

    summary["平均每篇引用次数"] = (
        summary["总引用次数"] / summary["软文数量"].replace(0, pd.NA)
    ).fillna(0).round(2)

    summary = summary.sort_values(by=["上传批次"], ascending=[True]).reset_index(drop=True)
    return summary[out_cols]


def export_excel(summary_df: pd.DataFrame, detail_df: pd.DataFrame, output_path: str) -> None:
    summary_cols = ["上传批次", "软文数量", "总引用次数", "平均每篇引用次数"]
    detail_cols = ["上传批次", "软文批次", "文章标题", "网站", "成功发送的URL", "本批次引用次数"]

    summary_out = summary_df.reindex(columns=summary_cols)
    detail_out = detail_df.reindex(columns=detail_cols)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_out.to_excel(writer, sheet_name="上传批次汇总", index=False)
        detail_out.to_excel(writer, sheet_name="上传批次明细", index=False)


def main() -> None:
    excel_raw_rows = 0
    excel_valid_rows = 0
    db_total_rows = 0
    match_total_rows = 0
    batch_count = 0

    empty_summary = pd.DataFrame(columns=["上传批次", "软文数量", "总引用次数", "平均每篇引用次数"])
    empty_detail = pd.DataFrame(columns=["上传批次", "软文批次", "文章标题", "网站", "成功发送的URL", "本批次引用次数"])

    try:
        if not os.path.exists(PAID_EXCEL_PATH):
            raise FileNotFoundError(f"未找到 Excel 文件: {PAID_EXCEL_PATH}")

        df_paid, excel_raw_rows = load_paid_excel(PAID_EXCEL_PATH)
        excel_valid_rows = len(df_paid)
    except Exception as exc:
        print(f"[错误] 读取或清洗付费发文 Excel 失败: {exc}")
        export_excel(empty_summary, empty_detail, OUTPUT_EXCEL_PATH)
        print(f"1. Excel 原始总行数: {excel_raw_rows}")
        print(f"2. Excel 有效 URL 行数: {excel_valid_rows}")
        print(f"3. 数据库读取总记录数: {db_total_rows}")
        print(f"4. URL 匹配成功总记录数: {match_total_rows}")
        print(f"5. 生成的上传批次数: {batch_count}")
        print(f"6. 结果文件输出路径: {os.path.abspath(OUTPUT_EXCEL_PATH)}")
        return

    try:
        df_ai, db_total_rows = load_ai_data_from_mysql(DB_CONFIG)
    except SQLAlchemyError as exc:
        print(f"[错误] MySQL 连接或查询失败: {exc}")
        export_excel(empty_summary, empty_detail, OUTPUT_EXCEL_PATH)
        print(f"1. Excel 原始总行数: {excel_raw_rows}")
        print(f"2. Excel 有效 URL 行数: {excel_valid_rows}")
        print(f"3. 数据库读取总记录数: {db_total_rows}")
        print(f"4. URL 匹配成功总记录数: {match_total_rows}")
        print(f"5. 生成的上传批次数: {batch_count}")
        print(f"6. 结果文件输出路径: {os.path.abspath(OUTPUT_EXCEL_PATH)}")
        return
    except Exception as exc:
        print(f"[错误] 数据库处理失败: {exc}")
        export_excel(empty_summary, empty_detail, OUTPUT_EXCEL_PATH)
        print(f"1. Excel 原始总行数: {excel_raw_rows}")
        print(f"2. Excel 有效 URL 行数: {excel_valid_rows}")
        print(f"3. 数据库读取总记录数: {db_total_rows}")
        print(f"4. URL 匹配成功总记录数: {match_total_rows}")
        print(f"5. 生成的上传批次数: {batch_count}")
        print(f"6. 结果文件输出路径: {os.path.abspath(OUTPUT_EXCEL_PATH)}")
        return

    if df_ai.empty:
        print("[提示] 数据库查询结果为空，导出空结果表头。")
        export_excel(empty_summary, empty_detail, OUTPUT_EXCEL_PATH)
        print(f"1. Excel 原始总行数: {excel_raw_rows}")
        print(f"2. Excel 有效 URL 行数: {excel_valid_rows}")
        print(f"3. 数据库读取总记录数: {db_total_rows}")
        print(f"4. URL 匹配成功总记录数: {match_total_rows}")
        print(f"5. 生成的上传批次数: {batch_count}")
        print(f"6. 结果文件输出路径: {os.path.abspath(OUTPUT_EXCEL_PATH)}")
        return

    df_match = build_match_result(df_paid, df_ai)
    match_total_rows = len(df_match)

    if df_match.empty:
        print("[提示] URL 匹配结果为空，导出空结果表头。")
        export_excel(empty_summary, empty_detail, OUTPUT_EXCEL_PATH)
        print(f"1. Excel 原始总行数: {excel_raw_rows}")
        print(f"2. Excel 有效 URL 行数: {excel_valid_rows}")
        print(f"3. 数据库读取总记录数: {db_total_rows}")
        print(f"4. URL 匹配成功总记录数: {match_total_rows}")
        print(f"5. 生成的上传批次数: {batch_count}")
        print(f"6. 结果文件输出路径: {os.path.abspath(OUTPUT_EXCEL_PATH)}")
        return

    detail_df = build_batch_detail(df_match)
    summary_df = build_batch_summary(detail_df)
    batch_count = summary_df["上传批次"].nunique() if not summary_df.empty else 0

    export_excel(summary_df, detail_df, OUTPUT_EXCEL_PATH)

    print(f"1. Excel 原始总行数: {excel_raw_rows}")
    print(f"2. Excel 有效 URL 行数: {excel_valid_rows}")
    print(f"3. 数据库读取总记录数: {db_total_rows}")
    print(f"4. URL 匹配成功总记录数: {match_total_rows}")
    print(f"5. 生成的上传批次数: {batch_count}")
    print(f"6. 结果文件输出路径: {os.path.abspath(OUTPUT_EXCEL_PATH)}")


if __name__ == "__main__":
    main()
