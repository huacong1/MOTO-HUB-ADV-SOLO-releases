# MOTO-HUB ADV-SOLO 简体中文自动构建

这个仓库里的 GitHub Actions 会**自动跟踪官方 [vincenzobpt/MOTO-HUB-ADV-SOLO-releases](https://github.com/vincenzobpt/MOTO-HUB-ADV-SOLO-releases)**：

1. 每 6 小时检查一次官方是否发了新版本（vX.Y.Z）；
2. 有新版本就下载官方 APK，解开 → 注入简体中文词库 → 重新打包、对齐、用**固定密钥签名**；
3. 在本仓库发一个 `zh-<versionCode>` 的 Release，APK 作为附件；
4. 手机端用 **Obtainium** 订阅本仓库，就能像装应用商店一样在线更新，不用再手动下载离线包。

> 中文词库（`catalogue/strings-zh-CN.json`，5,329 条）已经覆盖官方 APK 的全部字符串资源，官方自己没译的部分也包含在内，所以打出来的是**完整中文界面**。

---

## 一、一次性配置

### 1. 开启 Actions

仓库 → **Settings → Actions → General**：

- Fork 来的仓库默认关闭 Actions，先把 **Allow all actions and reusable workflows** 选上；
- 同一个页面拉到最下面 **Workflow permissions** 选 **Read and write permissions**（发布 Release 需要）。

### 2. 添加 4 个 Secret

仓库 → **Settings → Secrets and variables → Actions → New repository secret**：

| 名称 | 值 |
|---|---|
| `KEYSTORE_BASE64` | 签名密钥 `moto-hub-zh.jks` 的 Base64（见下） |
| `KEYSTORE_PASS` | keystore 口令 |
| `KEY_ALIAS` | 密钥别名（`motohub`） |
| `KEY_PASS` | 密钥口令 |

在 Windows PowerShell 里生成 `KEYSTORE_BASE64`：

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("D:\AI\MOTO-HUB-zh\keys\moto-hub-zh.jks"))
```

把输出的一整串（不要换行）粘进 Secret。

> **签名密钥必须永远用同一把。** 换了密钥，手机上的旧版就装不上新版（会报“应用未安装/签名冲突”），只能卸载重装、丢数据。

### 3.（可选）自动翻译新条目

官方如果新增了词库里没有的字符串，工作流可以调用任意 OpenAI 兼容接口自动翻译：

- Secret `TRANSLATE_API_KEY`：接口密钥；
- Variable `TRANSLATE_BASE_URL`（可选，默认 `https://api.deepseek.com`）；
- Variable `TRANSLATE_MODEL`（可选，默认 `deepseek-chat`）。

不配也能跑：新条目会**回退英文**，并在 `build-info.json` / `untranslated.json` 里列出来，之后补进 `catalogue/strings-zh-CN.json` 即可。

### 4.（可选）让「模块」页卡片也变中文

「模块」页那 8 张卡片的标题/简介是官方从远程文件读的，不在 APK 字符串里。若你已部署自己的镜像仓库（内容与官方 `MOTO-HUB-modules` 一致、只把 `index.json` 换成中文），加一个 **Variable**：

| 名称 | 值 |
|---|---|
| `MODULE_MIRROR_URL` | 例如 `https://raw.githubusercontent.com/huacong1/MOTO-HUB-modules-cn/main/` |

要求：**长度必须与官方地址完全一致**（`https://raw.githubusercontent.com/vincenzobpt/MOTO-HUB-modules/main/`，68 字节），否则脚本会警告并跳过——dex 里的字符串是紧凑存储的，长度一变就得重排整个 dex。

> **重要（2026-11-07 修正）**：这些地址在 APK 里**大多是混淆常量**，不是明文——形如 `base64(XOR(url, key))`，`key` 本身也是同一 dex 里的 base64 字符串（解密器类似 `KB0.m2846abstract(String enc_b64, String key_b64)`）。
> 只替换明文副本**不会生效**（早期版本就踩过这个坑：包做了，模块页还是英文）。
> 现在的 `zh_pipeline.py` 会自动：① 按「周期性 XOR 密钥」反推并等长重写混淆副本；② 顺手替换可能存在的明文副本；③ 重算 dex 头（adler32 + SHA-1）并回读校验。
> 0.1.62 实测：混淆副本 3 处（基址 2 + `index.json` 1）+ 明文 1 处，全部换到镜像后 aapt2/dalvik 校验通过。
> 以后上游若改了混淆方式，脚本会打印「没找到模块目录地址」并继续出包（模块页保持英文），不会让整次构建失败。

### 4. 先手动跑一次

仓库 → **Actions → Build zh-CN APK → Run workflow**（可勾 `force`）。

跑完会出现在 **Releases** 里，形如 `0.1.62.1-zh / zh-CN 0.1.62.1`。

**版本号规则（重要）**：包内版本号 = 官方版本号 ×100 + 修订号 → `0.1.62`(64) 打成 `0.1.62.1`(6401)；
同一官方版本想重打一次，把 `revision` 填 2 → `0.1.62.2`(6402)。这样 Obtainium 和系统都会认为它是「升级」，
否则版本号不变、手机上不会有更新提示（踩过这个坑）。官方出 0.1.63（65）时自动变成 `0.1.63.1`(6501)，依旧更大。

---

## 二、手机端在线更新（Obtainium）

1. 安装 [Obtainium](https://github.com/ImranR98/Obtainium/releases)；
2. Add App → 填本仓库地址 `https://github.com/<你的用户名>/MOTO-HUB-ADV-SOLO-releases`；
3. 它会自动读取 Releases、下载匹配的 APK 并提示更新（可设置“自动安装”需要额外授权）。

> ⚠️ 本项目的包签名与官方不同：
> - 从**官方版**切到汉化版，需要**先卸载官方版**（数据会丢）——这一步只做一次；
> - 之后的所有汉化版之间可以直接覆盖安装；
> - 应用内自带的「检查更新」永远指向官方仓库，装的是官方签名包，点了也装不上，请忽略它，只用 Obtainium 更新。

---

## 三、目录结构

```
.github/workflows/zh-build.yml   # 定时 + 手动触发
tools/zh_pipeline.py             # 下载 → 解码 → 注入中文 → 打包 → 签名 → 校验
catalogue/strings-zh-CN.json     # 资源名 → 中文（5,329 条）
catalogue/glossary.md            # 术语表（自动翻译时喂给模型，保证用词统一）
```

本地调试（不依赖 Actions）：

```powershell
python tools/zh_pipeline.py --apk "D:\path\to\MOTO-HUB-ADV-SOLO-0.1.62-64.apk" --skip-translate
```

会用到环境变量：`APKTOOL_JAR`、`BUILD_TOOLS`、`KEYSTORE`、`KEYSTORE_PASS`、`KEY_ALIAS`、`KEY_PASS`、`CATALOGUE`、`GLOSSARY`、`WORK_DIR`、`OUT_DIR`。

---

## 四、已知限制

| 限制 | 说明 |
|---|---|
| 只有 arm64-v8a | 官方包就是 arm64 单架构，汉化包保持原样 |
| 「模块」页卡片文字 | 那 8 张卡片的标题/简介来自**远程 JSON**（`raw.githubusercontent.com/vincenzobpt/MOTO-HUB-modules/main/index.json`），不在 APK 字符串里。配置 `MODULE_MIRROR_URL` 后本流水线会把 dex 里**混淆存放**的地址重写到你的镜像仓库（含 `index.json` 那个常量），卡片就会显示中文；不配则卡片保持英文。根治办法仍是作者在 `index.json` 里加多语言字段 |
| 定时精度 | GitHub 的 cron 最小间隔 5 分钟，但实测触发常延迟 10–30 分钟；急用就手动 Run workflow |
| 私有仓库额度 | 公开仓库 Actions 免费；私有仓库走你账号的分钟数（每次约 2–4 分钟） |
| 自动翻译质量 | 只翻词库里没有的新条目，仍建议人工过一遍；品牌名/占位符有硬规则保护 |
| 上游协议 | 汉化包属于再分发修改版，请自用、不要公开传播 APK |
