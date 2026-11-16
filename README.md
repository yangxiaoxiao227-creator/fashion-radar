# 日韩穿搭趋势雷达

每天早上 6:30（北京时间）自动采集日本、韩国的穿搭趋势，生成一个手机就能打开的网页。

| 数据源 | 采什么 | 说明 |
| --- | --- | --- |
| MUSINSA（韩国） | 女装总榜、25–29 岁榜、外套榜 | 主力数据源 |
| WEAR（日本） | 穿搭排行、话题、趋势关键词 | 主力数据源，图片文字里自带品类和颜色 |
| TikTok Creative Center | 日本、韩国热门话题（近 7 天、近 30 天） | 匿名访问只给前 3 名，条数少 |
| Pinterest Trends | 韩国、美国增长中的搜索词 | 只保留服饰相关的词；可能采不到 |

报告里有：各数据源是否正常、今日热度（单品 / 颜色 / 风格）、多个来源同时出现的词、新上榜、持续上升，以及各平台的原始榜单。日韩文字通过内置词典翻译成中文；"新上榜"和"持续上升"需要先积累 3 天数据。

---

## 第一次部署（约 20 分钟，只需做一次）

全程在网页上操作，不需要装任何软件。

### 1. 注册 GitHub 并新建仓库

1. 打开 https://github.com 注册账号。
2. 右上角 **+** → **New repository**。
3. Repository name 填 `fashion-radar`，选 **Public**（免费账号只有公开仓库能用网页功能），点 **Create repository**。

> 公开仓库意味着别人能看到代码和报告。报告内容都是公开榜单数据，没有隐私问题。

### 2. 上传文件

1. 在新仓库页面点 **uploading an existing file**。
2. 把解压后 `fashion-radar` 文件夹**里面的所有内容**拖进去（不是拖文件夹本身），点 **Commit changes**。
3. 检查仓库里是否有 `.github` 文件夹。Mac 默认隐藏以点开头的文件夹，常常会漏传：
   - 如果没有：点 **Add file → Create new file**，文件名一栏输入 `.github/workflows/daily.yml`，把压缩包里同名文件的内容全部复制粘贴进去，点 **Commit changes**。

### 3. 打开写入权限

**Settings → Actions → General**，拉到最下面 **Workflow permissions**，选 **Read and write permissions**，点 **Save**。

### 4. 启用 GitHub Pages

**Settings → Pages**，Source 选 **GitHub Actions**。每日任务生成报告后会发布 `docs/` 中的网页。

### 5. 第一次手动运行并打开网页

1. 点顶部 **Actions**。如果提示要启用工作流，点绿色按钮同意。
2. 左边点 **每日趋势雷达** → 右边 **Run workflow** → 再点绿色 **Run workflow**。
3. 等采集和发布任务都出现绿色对勾，在 **Settings → Pages** 查看网址，格式是：
   `https://你的用户名.github.io/fashion-radar/`
4. 可以把网址加到手机主屏幕。以后每天早上自动更新。

---

## 第一次运行后：检查数据源

打开网页，看最上面的"数据源状态"表。

- 全部"正常"：完成，什么都不用做。
- 某个来源"未采到"：网站可能改版或拦截了访问。请这样把调试数据发给我：
  1. **Actions** → 点最近一次运行。
  2. 页面底部 **Artifacts** 里下载 `debug-数字`。
  3. 把这个压缩包和网页上的数据源状态截图一起发我，我据此修改采集代码。

TikTok 和 Pinterest 条数少或采不到属于预期内；MUSINSA 和 WEAR 是主力，这两个要能采到。

## 日常调整

- **改采集范围**：编辑 `config.json`（GitHub 网页上点文件 → 右上角铅笔图标），比如增删 MUSINSA 的榜单、把某个来源的 `enabled` 改成 `false`。
- **补充词典**：编辑 `radar/glossary.py`，照格式加一行，例如：
  `("灯笼裤", "单品", ["벌룬 팬츠", "バルーンパンツ", "balloon pants"]),`
  词典没收录的词不会进入热度统计，但会出现在原始榜单里。
- **改运行时间**：编辑 `.github/workflows/daily.yml` 里的 `cron`（时间是 UTC，北京时间减 8 小时）。

## 注意

- GitHub 规定公开仓库如果 60 天没有任何动静，定时任务会被自动停用。本工具每天会提交一次数据，正常不会触发；如果哪天发现网页没更新，去 **Actions** 页面看看是否有重新启用的提示。
- 每个网站每天只访问几次，频率很低。数据仅用于个人选题参考，请勿转售或大规模分发。

## 文件说明

```
run.py                     每天运行的入口
config.json                采集范围设置
radar/collectors/          四个数据源的采集代码
radar/glossary.py          日韩英 → 中文服饰词典
radar/analyze.py           热度、新上榜、持续上升的计算
radar/report.py            网页生成
data/history/              每天的统计结果（用于对比趋势）
docs/                      生成的网页（index.html 是最新一期）
tests/                     离线自检
.github/workflows/         定时任务
```
