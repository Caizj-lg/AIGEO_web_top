import os
from io import BytesIO
from html import escape
from typing import Dict, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from paid_citation_batch_stats import (
    DB_CONFIG,
    PAID_EXCEL_PATH,
    build_batch_detail,
    build_match_result,
    load_ai_data_from_mysql,
    load_paid_excel,
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container { max-width: 1360px; padding-top: 0.75rem; padding-bottom: 1rem; }
        [data-testid="stAppViewContainer"] > .main { background: #f9f9f9; }
        .hero { background: #fff; border: 1px solid #ececef; border-radius: 12px; padding: 14px 16px; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
        .hero-title { margin: 0; font-size: 1.6rem; font-weight: 700; color: #1c1c1e; }
        .hero-sub { margin: 6px 0 0 0; color: #8e8e93; font-size: 0.92rem; }
        .toolbar-title { color: #6b7280; font-size: 0.82rem; margin: 0 0 6px 2px; }
        .summary-bar { background: #fff; border: 1px solid #ececef; border-radius: 12px; padding: 8px 12px; color: #1c1c1e; font-size: 0.9rem; margin-bottom: 8px; }
        .filter-state { color: #6b7280; font-size: 0.85rem; margin-top: 4px; }
        .section-title { color: #1c1c1e; font-weight: 700; font-size: 0.98rem; margin: 4px 0 6px 0; }
        .stButton > button[kind="primary"] { background: #007aff !important; border: 1px solid #007aff !important; color: #fff !important; }
        .stButton > button, .stDownloadButton > button { border-radius: 10px !important; border-color: #d9d9de !important; min-height: 40px !important; }
        .stSelectbox > div[data-baseweb="select"] > div,
        .stTextInput > div > div > input {
            border-radius: 10px !important;
            min-height: 40px !important;
        }
        .stToggle label { font-size: 0.88rem !important; color: #1c1c1e !important; }
        [data-testid="stDataFrame"] {
            --gdg-bg-header: #f4f4f6;
            --gdg-bg-header-hovered: #efeff2;
            --gdg-border-color: rgba(60,60,67,0.18);
            --gdg-horizontal-border-color: rgba(60,60,67,0.12);
            --gdg-text-header: #1c1c1e;
            --gdg-text-medium: #3a3a3c;
            border: 1px solid #ececef;
            border-radius: 10px;
            overflow: hidden;
        }
        [data-testid="stDataFrame"] * { font-size: 13.5px; }
        [data-testid="stDataFrame"] [role="row"]:hover { background: #f5f9ff !important; }
        .table-wrap { border: 1px solid #ececef; border-radius: 10px; overflow: visible; background: #fff; }
        .rank-table { width: 100%; border-collapse: collapse; font-size: 13.5px; color: #1c1c1e; }
        .rank-table thead th {
            position: sticky; top: 0; z-index: 2;
            background: #f4f4f6; color: #2c2c2e; font-weight: 650;
            border-bottom: 1px solid #e3e3e8; padding: 9px 10px; text-align: left;
        }
        .rank-table tbody td {
            border-bottom: 1px solid #f0f0f2; padding: 8px 10px; vertical-align: top;
        }
        .rank-table tbody tr:hover td { background: #f7fbff; }
        .num { text-align: right; white-space: nowrap; }
        .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
        .url-cell { max-width: 520px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .filter-hit { margin: 6px 0 8px; color: #0a5bd8; font-size: 0.86rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def empty_detail_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["上传批次", "软文批次", "文章标题", "网站", "成功发送的URL", "本批次引用次数"])


def run_pipeline(excel_path: str) -> Dict:
    metrics = {"excel_raw_rows": 0, "excel_valid_rows": 0, "db_total_rows": 0, "match_total_rows": 0}
    detail_df = empty_detail_frame()
    paid_all_df = pd.DataFrame(columns=["软文批次", "文章标题", "网站", "成功发送的URL"])

    if not os.path.exists(excel_path):
        return {"ok": False, "message": f"未找到 Excel 文件: {excel_path}", "detail": detail_df, "paid_all": paid_all_df, "metrics": metrics}

    try:
        df_paid, metrics["excel_raw_rows"] = load_paid_excel(excel_path)
        paid_all_df = df_paid[["软文批次", "文章标题", "网站", "成功发送的URL"]].copy()
        metrics["excel_valid_rows"] = len(df_paid)
    except Exception as exc:
        return {"ok": False, "message": f"读取或清洗 Excel 失败: {exc}", "detail": detail_df, "paid_all": paid_all_df, "metrics": metrics}

    try:
        df_ai, metrics["db_total_rows"] = load_ai_data_from_mysql(DB_CONFIG)
    except SQLAlchemyError as exc:
        return {"ok": False, "message": f"MySQL 连接或查询失败: {exc}", "detail": detail_df, "paid_all": paid_all_df, "metrics": metrics}
    except Exception as exc:
        return {"ok": False, "message": f"数据库处理失败: {exc}", "detail": detail_df, "paid_all": paid_all_df, "metrics": metrics}

    if df_ai.empty:
        return {"ok": True, "message": "数据库查询结果为空。", "detail": detail_df, "paid_all": paid_all_df, "metrics": metrics}

    df_match = build_match_result(df_paid, df_ai)
    metrics["match_total_rows"] = len(df_match)
    if df_match.empty:
        return {"ok": True, "message": "URL 匹配结果为空。", "detail": detail_df, "paid_all": paid_all_df, "metrics": metrics}

    detail_df = build_batch_detail(df_match)
    return {"ok": True, "message": "统计完成。", "detail": detail_df, "paid_all": paid_all_df, "metrics": metrics}


def filter_paid_all(paid_all_df: pd.DataFrame, keyword: str) -> pd.DataFrame:
    df = paid_all_df.copy()
    key = keyword.strip().lower()
    if not key:
        return df
    mask = (
        df["软文批次"].astype(str).str.lower().str.contains(key)
        | df["文章标题"].astype(str).str.lower().str.contains(key)
        | df["网站"].astype(str).str.lower().str.contains(key)
        | df["成功发送的URL"].astype(str).str.lower().str.contains(key)
    )
    return df[mask].copy()


def apply_filters(detail_df: pd.DataFrame, upload_batch: str, keyword: str) -> pd.DataFrame:
    filtered = detail_df.copy()
    if upload_batch != "全部批次":
        filtered = filtered[filtered["上传批次"].astype(str) == upload_batch]

    key = keyword.strip().lower()
    if key:
        filtered = filtered[
            filtered["软文批次"].astype(str).str.lower().str.contains(key)
            | filtered["文章标题"].astype(str).str.lower().str.contains(key)
            | filtered["网站"].astype(str).str.lower().str.contains(key)
            | filtered["成功发送的URL"].astype(str).str.lower().str.contains(key)
        ]
    return filtered


def build_rankings(filtered_detail: pd.DataFrame, paid_all_filtered: pd.DataFrame, descending: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
    website_cols = ["排名", "网站", "引用次数", "命中软文篇数", "占比"]
    article_cols = ["排名", "软文批次", "文章标题", "网站", "成功发送的URL", "总引用次数", "命中上传批次数"]

    total_citations = int(filtered_detail["本批次引用次数"].sum()) if not filtered_detail.empty else 0

    website_base = paid_all_filtered[["网站"]].drop_duplicates().copy()
    if filtered_detail.empty:
        website_stat = pd.DataFrame(columns=["网站", "引用次数", "命中软文篇数"])
    else:
        website_stat = (
            filtered_detail.groupby("网站", dropna=False)
            .agg(引用次数=("本批次引用次数", "sum"), 命中软文篇数=("成功发送的URL", "nunique"))
            .reset_index()
        )
    website = website_base.merge(website_stat, on="网站", how="left")
    website["引用次数"] = website["引用次数"].fillna(0).astype(int)
    website["命中软文篇数"] = website["命中软文篇数"].fillna(0).astype(int)
    website["占比"] = website["引用次数"].apply(lambda x: f"{(x / total_citations * 100):.1f}%" if total_citations else "0.0%")
    website = website.sort_values(["引用次数", "网站"], ascending=[not descending, True]).reset_index(drop=True)
    website.insert(0, "排名", website.index + 1)

    article_base = paid_all_filtered[["软文批次", "文章标题", "网站", "成功发送的URL"]].drop_duplicates().copy()
    if filtered_detail.empty:
        article_stat = pd.DataFrame(columns=["软文批次", "文章标题", "网站", "成功发送的URL", "总引用次数", "命中上传批次数"])
    else:
        article_stat = (
            filtered_detail.groupby(["软文批次", "文章标题", "网站", "成功发送的URL"], dropna=False)
            .agg(总引用次数=("本批次引用次数", "sum"), 命中上传批次数=("上传批次", "nunique"))
            .reset_index()
        )
    article = article_base.merge(article_stat, on=["软文批次", "文章标题", "网站", "成功发送的URL"], how="left")
    for col, default_val in [("软文批次", "(未标注软文批次)"), ("文章标题", "(未命名标题)"), ("网站", "(未标注网站)"), ("成功发送的URL", "")]:
        article[col] = article[col].fillna(default_val).astype(str)
    article["总引用次数"] = article["总引用次数"].fillna(0).astype(int)
    article["命中上传批次数"] = article["命中上传批次数"].fillna(0).astype(int)
    article = article.sort_values(["总引用次数", "文章标题"], ascending=[not descending, True]).reset_index(drop=True)
    article.insert(0, "排名", article.index + 1)

    return website[website_cols], article[article_cols]


def clip_text(text: str, limit: int = 56) -> str:
    s = str(text or "")
    return s if len(s) <= limit else s[: limit - 1] + "…"


def render_rank_table(df: pd.DataFrame, columns: list[str], numeric_cols: set[str], url_cols: set[str] | None = None) -> None:
    url_cols = url_cols or set()
    headers = "".join(f"<th>{escape(c)}</th>" for c in columns)
    rows = []
    for _, row in df[columns].iterrows():
        tds = []
        for c in columns:
            val = row[c]
            text = "" if pd.isna(val) else str(val)
            cls = []
            if c in numeric_cols:
                cls.append("num")
            if c in url_cols:
                cls.extend(["mono", "url-cell"])
            class_attr = f' class="{" ".join(cls)}"' if cls else ""
            title_attr = f' title="{escape(text)}"' if c in url_cols else ""
            tds.append(f"<td{class_attr}{title_attr}>{escape(text)}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    html = (
        '<div class="table-wrap">'
        '<table class="rank-table">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def build_export_bytes(website_ranking: pd.DataFrame, article_ranking: pd.DataFrame) -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        website_ranking.to_excel(writer, sheet_name="网站引用次数排行榜", index=False)
        article_ranking.to_excel(writer, sheet_name="付费发文引用次数排行榜", index=False)
    bio.seek(0)
    return bio.read()


def paginate(df: pd.DataFrame, page_size: int, page_key: str) -> Tuple[pd.DataFrame, int, int]:
    if df.empty:
        return df, 1, 1
    total = len(df)
    total_pages = (total - 1) // page_size + 1
    page = st.session_state.get(page_key, 1)
    if page > total_pages:
        page = total_pages
    if page < 1:
        page = 1
    st.session_state[page_key] = page
    start = (page - 1) * page_size
    end = start + page_size
    return df.iloc[start:end], page, total_pages


def main() -> None:
    st.set_page_config(page_title="付费发文引用次数排行榜", layout="wide")
    inject_styles()

    if "result" not in st.session_state:
        st.session_state["result"] = None
    if "excel_path" not in st.session_state:
        st.session_state["excel_path"] = PAID_EXCEL_PATH

    st.markdown(
        """
        <div class="hero">
          <p class="hero-title">付费发文引用次数排行榜</p>
          <p class="hero-sub">Excel 与数据库 URL 匹配后的网站/软文引用统计，可按上传批次筛选</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state["result"] is None:
        st.session_state["result"] = run_pipeline(st.session_state["excel_path"])

    result = st.session_state["result"]
    if not result["ok"]:
        st.error(result["message"])

    detail_df = result["detail"].copy()
    paid_all_df = result.get("paid_all", pd.DataFrame(columns=["软文批次", "文章标题", "网站", "成功发送的URL"])).copy()

    with st.container(border=True):
        st.markdown('<p class="toolbar-title">筛选与导出</p>', unsafe_allow_html=True)
        t1, t2, t3, t4 = st.columns([0.9, 1.35, 0.95, 0.6], gap="small", vertical_alignment="bottom")

        batch_options = ["全部批次"]
        if not detail_df.empty:
            batch_options += sorted(detail_df["上传批次"].astype(str).unique().tolist())

        upload_batch = t1.selectbox("批次", batch_options, index=0, label_visibility="visible")
        keyword = t2.text_input("搜索", value="", placeholder="软文批次 / 标题 / 网站 / URL")
        sort_mode = t3.selectbox("排序", ["按引用次数降序", "按引用次数升序"], index=0)
        top_n = t4.selectbox("网站 Top", [10, 20, 50, 100], index=1)

        b1, b2, b3, b4 = st.columns([0.9, 0.9, 1.6, 0.9], gap="small", vertical_alignment="bottom")
        show_zero_websites = b1.toggle("显示零值网站", value=False)
        show_zero_articles = b2.toggle("显示零值软文", value=False)

    filtered_detail = apply_filters(detail_df, upload_batch, keyword)
    paid_all_filtered = filter_paid_all(paid_all_df, keyword)
    descending = sort_mode == "按引用次数降序"
    website_ranking, article_ranking = build_rankings(filtered_detail, paid_all_filtered, descending=descending)
    if not show_zero_websites:
        website_ranking = website_ranking[~((website_ranking["引用次数"] == 0) & (website_ranking["命中软文篇数"] == 0))].reset_index(drop=True)
        website_ranking["排名"] = range(1, len(website_ranking) + 1)
        website_ranking = website_ranking[["排名", "网站", "引用次数", "命中软文篇数", "占比"]]
    if not show_zero_articles:
        article_ranking = article_ranking[article_ranking["总引用次数"] > 0].reset_index(drop=True)
        article_ranking["排名"] = range(1, len(article_ranking) + 1)
        article_ranking = article_ranking[["排名", "软文批次", "文章标题", "网站", "成功发送的URL", "总引用次数", "命中上传批次数"]]

    filter_signature = (upload_batch, keyword, sort_mode, top_n, show_zero_websites, show_zero_articles)
    if st.session_state.get("filter_signature") != filter_signature:
        st.session_state["filter_signature"] = filter_signature
        st.session_state["filter_changed"] = True

        b4.download_button(
            label="导出 Excel",
            data=build_export_bytes(website_ranking, article_ranking),
            file_name="付费发文引用次数排行榜_当前筛选结果.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    total_refs = int(filtered_detail["本批次引用次数"].sum()) if not filtered_detail.empty else 0
    st.markdown(
        f'<div class="summary-bar">统计摘要：软文 <b>{len(article_ranking)}</b> 篇 · 网站 <b>{len(website_ranking)}</b> 个 · 总引用 <b>{total_refs}</b> 次'
        f'<div class="filter-state">当前筛选：批次 = <b>{upload_batch}</b>；关键词 = <b>{keyword if keyword else "无"}</b>；排序 = <b>{sort_mode}</b>；Top = <b>{top_n}</b>；零值网站 = <b>{"显示" if show_zero_websites else "隐藏"}</b>；零值软文 = <b>{"显示" if show_zero_articles else "隐藏"}</b></div></div>',
        unsafe_allow_html=True,
    )
    if st.session_state.get("filter_changed"):
        st.markdown('<div class="filter-hit">筛选条件已生效，排行榜已更新。</div>', unsafe_allow_html=True)
        st.session_state["filter_changed"] = False

    st.markdown('<div class="section-title">网站引用次数排行榜</div>', unsafe_allow_html=True)
    website_show = website_ranking if show_zero_websites else website_ranking.head(top_n)
    render_rank_table(
        website_show,
        columns=["排名", "网站", "引用次数", "命中软文篇数", "占比"],
        numeric_cols={"排名", "引用次数", "命中软文篇数"},
    )

    st.divider()
    st.markdown('<div class="section-title">付费发文明细排行</div>', unsafe_allow_html=True)
    if "article_page" not in st.session_state:
        st.session_state["article_page"] = 1
    article_page_df, page, total_pages = paginate(article_ranking, 20, "article_page")
    article_page_view = article_page_df[["排名", "文章标题", "网站", "总引用次数", "命中上传批次数", "成功发送的URL", "软文批次"]].copy()
    article_page_view["文章标题"] = article_page_view["文章标题"].apply(lambda x: clip_text(x, 68))
    article_page_view["成功发送的URL"] = article_page_view["成功发送的URL"].apply(lambda x: clip_text(x, 78))
    article_page_view = article_page_view.rename(columns={"成功发送的URL": "URL预览"})

    render_rank_table(
        article_page_view,
        columns=["排名", "文章标题", "网站", "总引用次数", "命中上传批次数", "URL预览", "软文批次"],
        numeric_cols={"排名", "总引用次数", "命中上传批次数"},
        url_cols={"URL预览"},
    )
    p1, p2, p3 = st.columns([0.7, 0.7, 2.2], gap="small", vertical_alignment="center")
    if p1.button("上一页", use_container_width=True):
        st.session_state["article_page"] = st.session_state.get("article_page", 1) - 1
    if p2.button("下一页", use_container_width=True):
        st.session_state["article_page"] = st.session_state.get("article_page", 1) + 1
    p3.caption(f"第 {page}/{total_pages} 页 · 共 {len(article_ranking)} 条")


if __name__ == "__main__":
    main()
