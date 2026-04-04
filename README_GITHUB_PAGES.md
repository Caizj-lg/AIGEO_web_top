# GitHub Pages 部署说明

## 1. 本地生成静态数据

```bash
python export_static_data.py
```

会生成：

- `docs/data/articles.json`
- `docs/data/batch_detail.json`
- `docs/data/meta.json`

## 2. 本地预览

在项目根目录执行：

```bash
python -m http.server 8000
```

然后访问：

`http://127.0.0.1:8000/docs/`

## 3. 推送到 GitHub

```bash
git init
git add .
git commit -m "init static dashboard"
git remote add origin https://github.com/Caizj-lg/AIGEO_web_top.git
git branch -M main
git push -u origin main
```

## 4. GitHub Pages 设置

GitHub 仓库中：

- `Settings`
- `Pages`
- `Build and deployment`
- `Source`: `Deploy from a branch`
- `Branch`: `main`
- `Folder`: `/docs`

发布地址会类似：

`https://caizj-lg.github.io/AIGEO_web_top/`

## 5. 后续更新数据

```bash
python export_static_data.py
git add docs/data
git commit -m "refresh dashboard data"
git push
```
