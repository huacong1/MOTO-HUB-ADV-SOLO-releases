#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MOTO-HUB ADV-SOLO — zh-CN 自动构建管线。

流程：查上游最新 release -> 下载官方 APK -> apktool 解码 -> 用词库注入
values-zh-rCN -> apktool 重建 -> zipalign -> apksigner 签名 -> 校验 -> 输出 build-info.json。

本地（Windows/macOS/Linux）与 GitHub Actions 通用；所有外部依赖由环境变量/参数指定。

环境变量（缺省值见代码）：
  UPSTREAM_REPO     上游 release 仓库，默认 vincenzobpt/MOTO-HUB-ADV-SOLO-releases
  GITHUB_TOKEN      可选；用于提高 GitHub API 配额、检查本仓库是否已发布同一版本
  BUILD_REPO        可选；本仓库 slug（owner/name），用于“是否已经打过这一版”的判断
  APKTOOL_JAR       apktool jar 路径
  BUILD_TOOLS       Android build-tools 目录（含 zipalign、apksigner）
  KEYSTORE / KEYSTORE_PASS / KEY_ALIAS / KEY_PASS   签名信息
  CATALOGUE         词库 JSON（资源名 -> 中文），默认 catalogue/strings-zh-CN.json
  GLOSSARY          术语表 markdown，供自动翻译使用
  TRANSLATE_API_KEY / TRANSLATE_BASE_URL / TRANSLATE_MODEL  可选的 OpenAI 兼容翻译接口
  WORK_DIR / OUT_DIR
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

API = "https://api.github.com"
UA = {"User-Agent": "motohub-zh-builder"}


# ----------------------------------------------------------------------------- utils
def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    log("$ " + " ".join(str(c) for c in cmd))
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True,
                       encoding="utf-8", errors="replace",
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout or ""
    if out.strip():
        print(out.rstrip(), flush=True)
    if check and p.returncode != 0:
        raise SystemExit(f"命令失败（exit {p.returncode}）：{cmd[0]}")
    return p


def http_json(url: str, token: str | None = None) -> dict | list:
    req = urllib.request.Request(url, headers=dict(UA))
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as f:
        return json.loads(f.read().decode("utf-8"))


def http_download(url: str, dest: Path, token: str | None = None) -> None:
    req = urllib.request.Request(url, headers=dict(UA))
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=300) as f, open(dest, "wb") as out:
        shutil.copyfileobj(f, out)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------- upstream release
def latest_release(token: str | None) -> dict:
    url = f"{API}/repos/{os.environ.get('UPSTREAM_REPO', 'vincenzobpt/MOTO-HUB-ADV-SOLO-releases')}/releases/latest"
    rel = http_json(url, token)
    assets = [a for a in rel.get("assets", []) if a["name"].lower().endswith(".apk")]
    if not assets:
        raise SystemExit("上游 release 没有 APK 资产")
    apk = assets[0]
    return {"tag": rel.get("tag_name", ""), "name": rel.get("name", ""),
            "published_at": rel.get("published_at", ""), "apk_url": apk["browser_download_url"],
            "apk_name": apk["name"], "size": apk.get("size", 0)}


def already_built(build_repo: str | None, tag: str, token: str | None) -> bool:
    if not build_repo or not token:
        return False
    try:
        rels = http_json(f"{API}/repos/{build_repo}/releases?per_page=100", token)
    except Exception as e:  # noqa: BLE001
        log(f"（检查已有 release 失败，忽略：{e}）")
        return False
    for r in rels:
        if r.get("tag_name") == tag:
            log(f"本仓库已有 {tag}，跳过。")
            return True
    return False


# --------------------------------------------------------------------- apktool / build
def apktool(args: list[str]) -> None:
    jar = os.environ.get("APKTOOL_JAR", "tools/apktool.jar")
    run(["java", "-Xmx4g", "-jar", jar] + args)


def decode(apk: Path, out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    apktool(["d", "-f", "-s", str(apk), "-o", str(out)])


def read_apktool_yml(decoded: Path) -> dict:
    txt = (decoded / "apktool.yml").read_text(encoding="utf-8", errors="replace")

    def grab(key: str) -> str | None:
        m = re.search(rf"^\s*{key}:\s*'?([^'\n]+)'?\s*$", txt, re.M)
        return m.group(1).strip() if m else None

    vc = grab("versionCode")
    vn = grab("versionName")
    return {"versionCode": int(vc) if vc and vc.isdigit() else 0, "versionName": vn or ""}


def apply_version_override(decoded: Path, ver: dict, revision: int) -> dict:
    """给汉化包一个比官方更高、且每次重建都能递增的版本号。

    官方 versionCode 单调递增（…63、64、65…），直接沿用则「同一官方版本重打」时
    版本号不变，Obtainium / 系统都不会认为是更新。这里改成：

        versionCode = 官方 versionCode × 100 + 修订号
        versionName = 官方 versionName + "." + 修订号     （数字点分，Obtainium 才比得清）

      0.1.62 (64) + rev 2  ->  0.1.62.2 (6402)
      官方出新版 0.1.63 (65) + rev 1 -> 0.1.63.1 (6501)，依旧更大，仍算升级。

    注意：apktool 的 yml 解析器要求 versionCode 是**不带引号**的整数，写成 '6402' 会报
    NumberFormatException: For input string: "'6402'"。
    """
    revision = max(1, int(revision or 1))
    base_vc = int(ver.get("versionCode") or 0)
    base_vn = ver.get("versionName") or "0"
    new_vc = base_vc * 100 + revision
    new_vn = f"{base_vn}.{revision}"
    p = decoded / "apktool.yml"
    txt = p.read_text(encoding="utf-8")
    txt = re.sub(r"(?m)^(\s*versionCode:\s*)'?[^'\n]+'?\s*$", lambda m: f"{m.group(1)}{new_vc}", txt, count=1)
    txt = re.sub(r"(?m)^(\s*versionName:\s*)'?[^'\n]+'?\s*$", lambda m: f"{m.group(1)}'{new_vn}'", txt, count=1)
    p.write_text(txt, encoding="utf-8")
    log(f"版本改写：{base_vn} ({base_vc}) -> {new_vn} ({new_vc})")
    return {"versionCode": new_vc, "versionName": new_vn, "baseVersionCode": base_vc, "baseVersionName": base_vn}


STR_RE = re.compile(r'<string name="([^"]+)"([^>]*)>(.*?)</string>', re.S)
RES_STR_RE = re.compile(r'<string name="([^"]+)"[^>]*>(.*?)</string>', re.S)


def parse_strings(path: Path) -> dict[str, tuple[str, str]]:
    """返回 name -> (属性串, 原文)。原文件不存在时返回空表。"""
    if not path.exists():
        return {}
    txt = path.read_text(encoding="utf-8")
    return {m.group(1): (m.group(2), m.group(3)) for m in STR_RE.finditer(txt)}


def xml_escape_attr(text: str) -> str:
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def write_zh_strings(decoded: Path, catalogue: dict[str, str],
                     translated: dict[str, str] | None = None) -> tuple[int, int, list[str]]:
    """把中文词库注入 res/values-zh-rCN/strings.xml。

    英文条目的属性（如 formatted="false"）会被继承，避免 aapt2 硬错误。
    返回 (写入条数, 官方原有条数, 仍缺译的资源名列表)。
    """
    res = decoded / "res"
    en = parse_strings(res / "values" / "strings.xml")
    official = {n: t for n, (_, t) in parse_strings(res / "values-zh-rCN" / "strings.xml").items()}
    translated = translated or {}

    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<resources>"]
    written = 0
    missing: list[str] = []
    for name, (attrs, _en_text) in en.items():
        value = catalogue.get(name)
        if value is None:
            value = official.get(name)   # 官方自带的译文（若有）
        if value is None:
            value = translated.get(name)  # 本次自动翻译（若有）
        if value is None:
            missing.append(name)
            continue
        lines.append(f'<string name="{name}"{attrs}>{value}</string>')
        written += 1
    lines.append("</resources>")
    (res / "values-zh-rCN").mkdir(parents=True, exist_ok=True)
    (res / "values-zh-rCN" / "strings.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return written, len(official), missing


def ensure_locale_config(decoded: Path) -> bool:
    p = decoded / "res" / "xml" / "locales_config.xml"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('<?xml version="1.0" encoding="utf-8"?>\n'
                     '<locale-config xmlns:android="http://schemas.android.com/apk/res/android">\n'
                     '    <locale android:name="zh-CN" />\n</locale-config>\n', encoding="utf-8")
        return True
    txt = p.read_text(encoding="utf-8")
    if 'android:name="zh-CN"' in txt:
        return False
    txt = txt.replace("</locale-config>", '    <locale android:name="zh-CN" />\n</locale-config>')
    p.write_text(txt, encoding="utf-8")
    return True


DEX_RUN_RE = re.compile(rb"[\x20-\x7e\r\n]{8,4096}")


def _iter_dex_runs(data: bytes):
    for m in DEX_RUN_RE.finditer(data):
        yield m.start(), m.group()


def _periodic_key(cipher: bytes, plain: bytes) -> bytes | None:
    """若 cipher XOR plain 是周期 <=32 的重复密钥，返回该密钥。"""
    if len(cipher) != len(plain):
        return None
    delta = bytes(a ^ b for a, b in zip(cipher, plain))
    for period in range(1, min(33, len(delta) + 1)):
        if all(delta[i] == delta[i % period] for i in range(len(delta))):
            return delta[:period]
    return None


def _find_encrypted(data: bytes, plaintext: str):
    """在 dex 里找出把 plaintext 混淆存放的副本：[(offset, orig_span, key)]。

    App 用 base64(XOR(url, key)) 存 URL，key 本身以 base64 存在同一 dex 里；
    dex 的字符串前紧挨 uleb128 长度前缀（可能是可打印字符），所以每个片段要
    试 0~3 个前导偏移再解码。
    """
    target = plaintext.encode()
    found = []
    for start, raw in _iter_dex_runs(data):
        for k in range(4):
            s = re.sub(rb"\s", b"", raw[k:])
            if len(s) % 4 or len(s) < 16:
                continue
            try:
                dec = base64.b64decode(s, validate=True)
            except Exception:
                continue
            if len(dec) != len(target):
                continue
            key = _periodic_key(dec, target)
            if key is None:
                continue
            if base64.b64encode(key) in data:
                found.append((start + k, raw[k:], key))
                break
    return found


def _rewrite_b64_span(span: bytes, new_plain: bytes, key: bytes) -> bytes:
    """把一段 base64（可能夹着换行）换成新明文的密文，保留原有换行的位置。"""
    new_b64 = base64.b64encode(bytes(a ^ b for a, b in zip(new_plain, (key * (len(new_plain) // len(key) + 1))[:len(new_plain)])))
    out, i = bytearray(), 0
    for ch in span:
        if chr(ch).isalnum() or ch in b"+/=":
            if i < len(new_b64):
                out.append(new_b64[i])
                i += 1
            else:
                out.append(ch)
        else:
            out.append(ch)
    if i != len(new_b64):
        raise ValueError(f"base64 长度不一致：写入 {i} / 期望 {len(new_b64)}")
    return bytes(out)


def patch_module_base_url(decoded: Path, from_url: str, to_url: str) -> bool:
    """把 dex 里模块目录的地址换成镜像地址（等长原地替换 + 重算 dex 头）。

    官方把「模块」页的 8 张卡片文案放在远程 index.json 里，APK 字符串表改不到；
    把地址指向自己的镜像仓库后，卡片标题/简介就能是中文。

    关键：这些地址大多**不是明文**，而是 base64(XOR(url, key)) 的混淆常量
    （解密器形如 KB0.m2846abstract(enc_b64, key_b64)）。只替换明文副本不会生效，
    必须把混淆副本一起换掉，因此这里按「周期性 XOR 密钥」反推并重写密文。
    必须等长：dex 内字符串紧凑存储，长度一变就要重排整个 dex。
    """
    src, dst = from_url.encode(), to_url.encode()
    if not src or not dst:
        return False
    if len(src) != len(dst):
        log(f"警告：镜像地址长度 {len(dst)} 与原地址 {len(src)} 不一致，跳过模块镜像")
        return False

    targets = [from_url, from_url + "index.json"]
    replacements = [to_url, to_url + "index.json"]
    total_enc = total_plain = 0
    for f in sorted(decoded.glob("classes*.dex")):
        buf = bytearray(f.read_bytes())
        if not _dex_ok(bytes(buf)):
            log(f"警告：{f.name} 头校验异常，跳过模块镜像")
            return False
        original = bytes(buf)
        changed = 0

        # 1) 混淆副本（原地等长重写密文）
        for plain, repl in zip(targets, replacements):
            for off, span, key in _find_encrypted(original, plain):
                new_span = _rewrite_b64_span(span, repl.encode(), key)
                if len(new_span) != len(span):
                    log(f"警告：{f.name} 混淆副本长度变化，跳过")
                    return False
                buf[off:off + len(span)] = new_span
                changed += 1
                total_enc += 1

        # 2) 明文副本（老版本可能直接存明文）
        text = bytes(buf)
        for plain, repl in zip(targets, replacements):
            n = text.count(plain.encode())
            if n:
                text = text.replace(plain.encode(), repl.encode())
                changed += n
                total_plain += n
        if changed:
            buf = bytearray(text)
            _fix_dex_header(buf)
            if not _dex_ok(bytes(buf)):
                log(f"警告：{f.name} 修补后校验失败，跳过模块镜像")
                return False
            f.write_bytes(bytes(buf))
            log(f"{f.name}: 替换 {changed} 处（混淆 {total_enc}，明文 {total_plain}）")

    if not (total_enc or total_plain):
        log("警告：没找到模块目录地址（混淆/明文都没有），上游结构可能变了")
        return False
    log(f"模块目录地址已指向镜像：{to_url}（混淆副本 {total_enc} 处，明文 {total_plain} 处）")
    return True


def _fix_dex_header(buf: bytearray) -> None:
    buf[12:32] = hashlib.sha1(bytes(buf[32:])).digest()
    struct.pack_into("<I", buf, 8, zlib.adler32(bytes(buf[12:])) & 0xFFFFFFFF)


def _dex_ok(buf: bytes) -> bool:
    stored = struct.unpack_from("<I", buf, 8)[0]
    return stored == (zlib.adler32(buf[12:]) & 0xFFFFFFFF) and buf[12:32] == hashlib.sha1(buf[32:]).digest()


# --------------------------------------------------------------------------- translate
TRANSLATE_PROMPT = """你是 MOTO-HUB（摩托车互联 App）的简体中文本地化译者。把下面的英文 UI 文案译成简体中文。

规则（必须遵守）：
1. 严格遵守术语表；术语表没写的按下方已译风格保持一致。
2. 保留所有 %1$s %2$d 这类占位符，数量、顺序、类型都不能变；不要新增或删除 % 号。
3. 品牌名不翻译：MOTO-HUB、Android Auto、T-Box、TFT、OBD、GPS、RPM、Mapbox、TomTom、Flyby、Immich、Dawarich、Google、Discord。
4. 按钮/标题不加句号；正文保留原句的标点与语气。
5. 只输出 JSON 对象：{"<资源名>": "<译文>", ...}，不要任何解释、不要 markdown 代码块。

术语表：
{glossary}

待译条目（JSON：资源名 -> 英文）：
{items}
"""


def auto_translate(items: dict[str, str], glossary: str, batch: int = 40) -> dict[str, str]:
    key = os.environ.get("TRANSLATE_API_KEY")
    if not key or not items:
        return {}
    base = os.environ.get("TRANSLATE_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("TRANSLATE_MODEL", "deepseek-chat")
    names = list(items)
    out: dict[str, str] = {}
    for i in range(0, len(names), batch):
        chunk = {n: items[n] for n in names[i:i + batch]}
        body = json.dumps({
            "model": model,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": TRANSLATE_PROMPT.format(
                glossary=glossary[:4000], items=json.dumps(chunk, ensure_ascii=False, indent=1))}],
        }).encode("utf-8")
        req = urllib.request.Request(base + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=180) as f:
                data = json.loads(f.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
            text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
            got = json.loads(text)
            out.update({k: v for k, v in got.items() if k in chunk and isinstance(v, str) and v.strip()})
            log(f"自动翻译：{len(got)}/{len(chunk)} 条")
        except Exception as e:  # noqa: BLE001
            log(f"自动翻译失败（{type(e).__name__}: {e}），本批保持英文回退")
    return out


# ------------------------------------------------------------------------- sign / verify
def build_tools() -> Path | None:
    bt = os.environ.get("BUILD_TOOLS")
    if bt and Path(bt).exists():
        return Path(bt)
    return None


def find_tool(name: str) -> str | None:
    """在 BUILD_TOOLS 里找工具（兼容 Windows 的 .exe/.bat），否则退回 PATH。"""
    bt = build_tools()
    if bt:
        for suffix in ("", ".exe", ".bat"):
            p = bt / (name + suffix)
            if p.exists():
                return str(p)
    return shutil.which(name)


def sign(unsigned: Path, out_apk: Path) -> None:
    zipalign = find_tool("zipalign")
    apksigner = find_tool("apksigner")
    if not zipalign or not apksigner:
        raise SystemExit("找不到 zipalign / apksigner，请设置 BUILD_TOOLS")
    aligned = out_apk.with_suffix(".aligned.apk")
    run([zipalign, "-p", "-f", "4", str(unsigned), str(aligned)])
    ks = os.environ["KEYSTORE"]
    run([apksigner, "sign",
         "--ks", ks,
         "--ks-key-alias", os.environ.get("KEY_ALIAS", "motohub"),
         "--ks-pass", "pass:" + os.environ.get("KEYSTORE_PASS", ""),
         "--key-pass", "pass:" + os.environ.get("KEY_PASS", os.environ.get("KEYSTORE_PASS", "")),
         "--out", str(out_apk), str(aligned)], check=False)
    aligned.unlink(missing_ok=True)


def verify(apk: Path) -> dict:
    apksigner = find_tool("apksigner")
    aapt2 = find_tool("aapt2")
    info: dict = {}
    if apksigner:
        # 注意：不加 --verbose 时 apksigner 只打印证书，不打印 "Verified using ... scheme" 行
        p = run([apksigner, "verify", "--verbose", "--print-certs", str(apk)], check=False)
        out = p.stdout or ""
        v3 = "Verified using v3 scheme (APK Signature Scheme v3): true" in out
        info["signature_ok"] = (p.returncode == 0) and (v3 or "Verified using v2 scheme (APK Signature Scheme v2): true" in out)
        m = re.search(r"SHA-256 digest: ([0-9a-f]+)", out)
        info["cert_sha256"] = m.group(1) if m else ""
    if aapt2:
        p = run([aapt2, "dump", "badging", str(apk)], check=False)
        out = p.stdout or ""
        for key, pat in (("package", r"package: name='([^']+)'"),
                         ("versionCode", r"versionCode='([^']+)'"),
                         ("versionName", r"versionName='([^']+)'")):
            m = re.search(pat, out)
            info[key] = m.group(1) if m else ""
        p = run([aapt2, "dump", "resources", str(apk)], check=False)
        info["zh_entries"] = len(re.findall(r"\(zh-rCN\)", p.stdout or ""))
    return info


# -------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", help="直接用本地 APK（调试用，跳过下载）")
    ap.add_argument("--force", action="store_true", help="忽略“已发布过同版本”的判断")
    ap.add_argument("--skip-translate", action="store_true")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    work = Path(os.environ.get("WORK_DIR", root / "work"))
    out_dir = Path(os.environ.get("OUT_DIR", root / "out"))
    work.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("GITHUB_TOKEN") or None

    # 1) 上游最新版
    apk_path: Path
    upstream = None
    if args.apk:
        apk_path = Path(args.apk).resolve()
        log(f"使用本地 APK：{apk_path}")
    else:
        upstream = latest_release(token)
        log(f"上游最新：{upstream['name']} ({upstream['tag']})，资产 {upstream['apk_name']}")
        apk_path = work / upstream["apk_name"]
        if not apk_path.exists() or apk_path.stat().st_size != upstream["size"]:
            log("下载中…")
            http_download(upstream["apk_url"], apk_path, token)

    # 2) 解码并读版本
    decoded = work / "decoded"
    log("apktool 解码…")
    decode(apk_path, decoded)
    ver = read_apktool_yml(decoded)
    log(f"版本：{ver['versionName']} (versionCode {ver['versionCode']})")

    # 版本号改写：官方 ×100 + 修订号，保证「同一官方版本重打」也能被识别成更新
    revision = int(os.environ.get("ZH_REVISION", "1") or 1)
    ver = apply_version_override(decoded, ver, revision)
    release_tag = f"{ver['versionName']}-zh"

    if not args.force and not args.apk and already_built(os.environ.get("BUILD_REPO"), release_tag, token):
        print("SKIP=1")
        Path(work / "build-info.json").write_text(json.dumps({"skipped": True, **ver}, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
        return 0

    # 3) 注入中文
    cat_path = Path(os.environ.get("CATALOGUE", root / "catalogue" / "strings-zh-CN.json"))
    catalogue = json.loads(cat_path.read_text(encoding="utf-8"))
    log(f"词库：{len(catalogue)} 条（{cat_path}）")
    written, official, missing = write_zh_strings(decoded, catalogue)

    translated: dict[str, str] = {}
    if missing and not args.skip_translate:
        en_map = {n: t for n, (_, t) in parse_strings(decoded / "res" / "values" / "strings.xml").items()
                  if n in set(missing)}
        glossary = ""
        gp = Path(os.environ.get("GLOSSARY", root / "catalogue" / "glossary.md"))
        if gp.exists():
            glossary = gp.read_text(encoding="utf-8")
        translated = auto_translate(en_map, glossary)
        if translated:
            written, official, missing = write_zh_strings(decoded, catalogue, translated)

    locale_added = ensure_locale_config(decoded)
    log(f"中文条目：{written}（官方原有 {official}），仍缺 {len(missing)}，locale 配置{'新增' if locale_added else '已含'} zh-CN")

    # 「模块」页卡片文案来自远程 index.json，把基址换到镜像仓库才能真正中文
    module_from = os.environ.get("MODULE_URL_FROM", "https://raw.githubusercontent.com/vincenzobpt/MOTO-HUB-modules/main/")
    module_to = os.environ.get("MODULE_MIRROR_URL", "").strip()
    module_patched = False
    if module_to:
        module_patched = patch_module_base_url(decoded, module_from, module_to)

    new_list = []
    if missing:
        en_all = parse_strings(decoded / "res" / "values" / "strings.xml")
        new_list = [{"name": n, "en": en_all[n][1]} for n in missing if n in en_all]
        (work / "untranslated.json").write_text(json.dumps(new_list, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4) 重建 + 签名
    unsigned = work / "unsigned.apk"
    log("apktool 重建…")
    apktool(["b", str(decoded), "-o", str(unsigned)])
    out_name = f"MOTO-HUB-ADV-SOLO-{ver['versionName']}-zh-CN.apk"
    out_apk = out_dir / out_name
    log("zipalign + 签名…")
    sign(unsigned, out_apk)

    # 5) 校验
    info = verify(out_apk)
    digest = sha256(out_apk)
    info.update({"versionCode": ver["versionCode"], "versionName": ver["versionName"],
                 "release_tag": release_tag,
                 "zh_written": written, "zh_official": official, "untranslated": len(new_list),
                 "sha256": digest, "size": out_apk.stat().st_size, "file": out_name,
                 "module_mirror": module_to if module_patched else "",
                 "upstream": upstream, "skipped": False})
    (work / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    log("完成：" + json.dumps(info, ensure_ascii=False))
    if not info.get("signature_ok"):
        log("ERROR: 签名校验失败，产物不可用")
        return 2

    # GitHub Actions 输出
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"skip=0\nversion_code={ver['versionCode']}\nversion_name={ver['versionName']}\n"
                    f"release_tag={release_tag}\napk={out_apk}\nsha256={digest}\nuntranslated={len(new_list)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
