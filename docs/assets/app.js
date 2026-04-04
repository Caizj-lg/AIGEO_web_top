const state = {
  articles: [],
  batchDetail: [],
  meta: {},
  filters: {
    uploadBatch: "全部批次",
    keyword: "",
    sortMode: "desc",
    topN: 20,
    showZeroWebsites: false,
    showZeroArticles: false,
  },
  articlePage: 1,
  pageSize: 20,
};

const qs = (id) => document.getElementById(id);

function clipText(text, limit = 68) {
  const s = String(text || "");
  return s.length <= limit ? s : `${s.slice(0, limit - 1)}…`;
}

function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function rankTable(columns, rows, numericCols = new Set(), urlCols = new Set()) {
  const head = columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("");
  const body = rows
    .map((row) => {
      const cells = columns
        .map((col) => {
          const raw = row[col] ?? "";
          const classes = [];
          if (numericCols.has(col)) classes.push("num");
          if (urlCols.has(col)) classes.push("url-cell");
          const title = urlCols.has(col) ? ` title="${escapeHtml(raw)}"` : "";
          return `<td class="${classes.join(" ")}"${title}>${escapeHtml(raw)}</td>`;
        })
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table class="rank-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function buildRankings() {
  const key = state.filters.keyword.trim().toLowerCase();
  const uploadBatch = state.filters.uploadBatch;
  const filteredDetail = state.batchDetail.filter((item) => {
    const matchBatch = uploadBatch === "全部批次" || item.upload_batch === uploadBatch;
    const hay = [item.paid_batch, item.article_title, item.website, item.success_url].join(" ").toLowerCase();
    const matchKeyword = !key || hay.includes(key);
    return matchBatch && matchKeyword;
  });

  const paidAllFiltered = state.articles.filter((item) => {
    const hay = [item.paid_batch, item.article_title, item.website, item.success_url].join(" ").toLowerCase();
    return !key || hay.includes(key);
  });

  const desc = state.filters.sortMode === "desc";
  const totalCitations = filteredDetail.reduce((sum, item) => sum + Number(item.citation_count || 0), 0);

  const websiteMap = new Map();
  paidAllFiltered.forEach((item) => {
    if (!websiteMap.has(item.website)) websiteMap.set(item.website, { 网站: item.website, 引用次数: 0, 命中软文篇数: 0 });
  });
  const websiteArticleSets = new Map();
  filteredDetail.forEach((item) => {
    const row = websiteMap.get(item.website) || { 网站: item.website, 引用次数: 0, 命中软文篇数: 0 };
    row.引用次数 += Number(item.citation_count || 0);
    websiteMap.set(item.website, row);
    const k = `${item.website}__${item.success_url}`;
    websiteArticleSets.set(k, true);
  });
  [...websiteArticleSets.keys()].forEach((key2) => {
    const [website] = key2.split("__");
    if (websiteMap.has(website)) websiteMap.get(website).命中软文篇数 += 1;
  });

  let websiteRows = [...websiteMap.values()].map((row) => ({
    ...row,
    占比: totalCitations ? `${((row.引用次数 / totalCitations) * 100).toFixed(1)}%` : "0.0%",
  }));
  if (!state.filters.showZeroWebsites) websiteRows = websiteRows.filter((row) => !(row.引用次数 === 0 && row.命中软文篇数 === 0));
  websiteRows.sort((a, b) => (desc ? b.引用次数 - a.引用次数 : a.引用次数 - b.引用次数) || a.网站.localeCompare(b.网站, "zh-CN"));
  websiteRows = websiteRows.map((row, idx) => ({ 排名: idx + 1, ...row }));

  const articleMap = new Map();
  paidAllFiltered.forEach((item) => {
    const k = `${item.paid_batch}__${item.article_title}__${item.website}__${item.success_url}`;
    articleMap.set(k, {
      软文批次: item.paid_batch || "(未标注软文批次)",
      文章标题: item.article_title || "(未命名标题)",
      网站: item.website || "(未标注网站)",
      成功发送的URL: item.success_url || "",
      总引用次数: 0,
      命中上传批次数: 0,
    });
  });
  const articleBatchSets = new Map();
  filteredDetail.forEach((item) => {
    const k = `${item.paid_batch}__${item.article_title}__${item.website}__${item.success_url}`;
    if (!articleMap.has(k)) return;
    articleMap.get(k).总引用次数 += Number(item.citation_count || 0);
    articleBatchSets.set(`${k}__${item.upload_batch}`, true);
  });
  [...articleBatchSets.keys()].forEach((k) => {
    const articleKey = k.split("__").slice(0, 4).join("__");
    if (articleMap.has(articleKey)) articleMap.get(articleKey).命中上传批次数 += 1;
  });

  let articleRows = [...articleMap.values()];
  if (!state.filters.showZeroArticles) articleRows = articleRows.filter((row) => row.总引用次数 > 0);
  articleRows.sort((a, b) => (desc ? b.总引用次数 - a.总引用次数 : a.总引用次数 - b.总引用次数) || a.文章标题.localeCompare(b.文章标题, "zh-CN"));
  articleRows = articleRows.map((row, idx) => ({ 排名: idx + 1, ...row }));

  return { websiteRows, articleRows, totalCitations };
}

function updateSummary(websiteRows, articleRows, totalCitations) {
  qs("summaryText").innerHTML = `统计摘要：软文 <b>${articleRows.length}</b> 篇 · 网站 <b>${websiteRows.length}</b> 个 · 总引用 <b>${totalCitations}</b> 次`;
  qs("filterState").innerHTML =
    `当前筛选：批次 = <b>${escapeHtml(state.filters.uploadBatch)}</b>；关键词 = <b>${escapeHtml(state.filters.keyword || "无")}</b>；排序 = <b>${state.filters.sortMode === "desc" ? "按引用次数降序" : "按引用次数升序"}</b>；Top = <b>${state.filters.topN}</b>；零值网站 = <b>${state.filters.showZeroWebsites ? "显示" : "隐藏"}</b>；零值软文 = <b>${state.filters.showZeroArticles ? "显示" : "隐藏"}</b>`;
}

function render() {
  const { websiteRows, articleRows, totalCitations } = buildRankings();
  updateSummary(websiteRows, articleRows, totalCitations);

  const websiteShow = state.filters.showZeroWebsites ? websiteRows : websiteRows.slice(0, state.filters.topN);
  qs("websiteTable").innerHTML = rankTable(
    ["排名", "网站", "引用次数", "命中软文篇数", "占比"],
    websiteShow,
    new Set(["排名", "引用次数", "命中软文篇数"])
  );

  const totalPages = Math.max(1, Math.ceil(articleRows.length / state.pageSize));
  if (state.articlePage > totalPages) state.articlePage = totalPages;
  if (state.articlePage < 1) state.articlePage = 1;
  const start = (state.articlePage - 1) * state.pageSize;
  const paged = articleRows.slice(start, start + state.pageSize).map((row) => ({
    排名: row.排名,
    文章标题: clipText(row.文章标题, 68),
    网站: row.网站,
    总引用次数: row.总引用次数,
    命中上传批次数: row.命中上传批次数,
    URL预览: clipText(row.成功发送的URL, 78),
    软文批次: row.软文批次,
  }));

  qs("articleTable").innerHTML = rankTable(
    ["排名", "文章标题", "网站", "总引用次数", "命中上传批次数", "URL预览", "软文批次"],
    paged,
    new Set(["排名", "总引用次数", "命中上传批次数"]),
    new Set(["URL预览"])
  );
  const pageText = `第 ${state.articlePage}/${totalPages} 页 · 共 ${articleRows.length} 条`;
  qs("pageTextBottom").textContent = pageText;
}

function signalRefresh() {
  const el = qs("refreshHint");
  el.classList.remove("hidden");
  window.clearTimeout(signalRefresh.timer);
  signalRefresh.timer = window.setTimeout(() => el.classList.add("hidden"), 1000);
}

function bindControls() {
  qs("uploadBatch").addEventListener("change", (e) => {
    state.filters.uploadBatch = e.target.value;
    state.articlePage = 1;
    render();
    signalRefresh();
  });
  qs("keyword").addEventListener("input", (e) => {
    state.filters.keyword = e.target.value;
    state.articlePage = 1;
    render();
    signalRefresh();
  });
  qs("sortMode").addEventListener("change", (e) => {
    state.filters.sortMode = e.target.value;
    state.articlePage = 1;
    render();
    signalRefresh();
  });
  qs("topN").addEventListener("change", (e) => {
    state.filters.topN = Number(e.target.value);
    render();
    signalRefresh();
  });
  qs("showZeroWebsites").addEventListener("change", (e) => {
    state.filters.showZeroWebsites = e.target.checked;
    render();
    signalRefresh();
  });
  qs("showZeroArticles").addEventListener("change", (e) => {
    state.filters.showZeroArticles = e.target.checked;
    state.articlePage = 1;
    render();
    signalRefresh();
  });
  const prev = () => { state.articlePage -= 1; render(); };
  const next = () => { state.articlePage += 1; render(); };
  qs("prevPageBottom").addEventListener("click", prev);
  qs("nextPageBottom").addEventListener("click", next);
  qs("exportBtn").addEventListener("click", exportExcel);
}

function exportExcel() {
  const { websiteRows, articleRows } = buildRankings();
  const websiteExport = (state.filters.showZeroWebsites ? websiteRows : websiteRows.slice(0, state.filters.topN)).map((row) => ({
    排名: row.排名,
    网站: row.网站,
    引用次数: row.引用次数,
    命中软文篇数: row.命中软文篇数,
    占比: row.占比,
  }));
  const articleExport = articleRows.map((row) => ({
    排名: row.排名,
    文章标题: row.文章标题,
    网站: row.网站,
    总引用次数: row.总引用次数,
    命中上传批次数: row.命中上传批次数,
    成功发送的URL: row.成功发送的URL,
    软文批次: row.软文批次,
  }));
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(websiteExport), "网站引用次数排行榜");
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(articleExport), "付费发文引用次数排行榜");
  XLSX.writeFile(wb, "付费发文引用次数排行榜_当前筛选结果.xlsx");
}

async function init() {
  const [articles, batchDetail, meta] = await Promise.all([
    fetch("./data/articles.json").then((r) => r.json()),
    fetch("./data/batch_detail.json").then((r) => r.json()),
    fetch("./data/meta.json").then((r) => r.json()),
  ]);
  state.articles = articles;
  state.batchDetail = batchDetail;
  state.meta = meta;

  const batchSelect = qs("uploadBatch");
  ["全部批次", ...(meta.upload_batches || [])].forEach((item) => {
    const option = document.createElement("option");
    option.value = item;
    option.textContent = item;
    batchSelect.appendChild(option);
  });

  bindControls();
  render();
}

init();
