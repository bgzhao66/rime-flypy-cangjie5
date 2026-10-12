#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RIME 一键安装脚本

功能（通过开关选择）：
    --ime-name <NAME>      安装方案文件，并把方案名注册到 default.custom.yaml
    --plugins              安装插件（需要与 --ime-name 一起使用）
    --rime-dir <PATH>      指定 RIME 用户目录（缺省时自动探测）
    --dry-run              仅检查与预览：不修改任何文件，只打印计划与可操作性

方案安装（--ime-name 触发，源目录 = 脚本所在目录的上一级）：
    ../<NAME>.schema.yaml       -> <RIME>/<NAME>.schema.yaml
    ../<NAME>*.dict.yaml        -> <RIME>/<NAME>*.dict.yaml
    并自动把 <NAME> 注册到 <RIME>/default.custom.yaml 的 patch/schema_list

插件安装（--plugins 且 --ime-name 同时给出时触发，源目录 = 脚本所在目录）：
    lua/*.lua                   -> <RIME>/lua/*.lua       （仅 .lua，跳过 rime.lua）
    lua/rime.lua                -> <RIME>/rime.lua
    latex/latex.dict.yaml       -> <RIME>/latex.dict.yaml
    latex/latex.schema.yaml     -> <RIME>/latex.schema.yaml
    <NAME>.custom.yaml          -> <RIME>/<NAME>.custom.yaml  （合并 patch）

default.custom.yaml 中 schema_list 的条目采用如下格式：
    - {schema: <NAME>}

退出码：
    0    全部成功（含幂等跳过）
    1    安装过程中有任务失败
    2    参数错误
    130  用户中断

用法：
    python install.py --ime-name flypy_cangjie5
    python install.py --ime-name flypy_cangjie5 --plugins
    python install.py --ime-name flypy_cangjie5 --plugins --dry-run
    python install.py --rime-dir "D:/RimeConfig" --ime-name flypy_cangjie5 --plugins
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 脚本目录：无论从哪里执行，都切到这里
# ---------------------------------------------------------------------------

SOURCE_DIR = Path(__file__).resolve().parent
os.chdir(SOURCE_DIR)

PARENT_DIR = SOURCE_DIR.parent


# ---------------------------------------------------------------------------
# 插件安装映射（固定，不含 <IME_NAME>.custom.yaml —— 它是动态的）
# ---------------------------------------------------------------------------

PLUGIN_FILE_MAP = [
    ("lua/rime.lua",                "rime.lua"),
    ("latex/latex.dict.yaml",       "latex.dict.yaml"),
    ("latex/latex.schema.yaml",     "latex.schema.yaml"),
]

LUA_DIR_SRC = "lua"
LUA_DIR_DST = "lua"
LUA_EXCLUDE = {"rime.lua"}   # rime.lua 单独安装到 RIME 根目录


# ---------------------------------------------------------------------------
# 定位 RIME 目录
# ---------------------------------------------------------------------------

def detect_rime_dir() -> Path | None:
    """按平台自动探测 RIME 用户目录，找不到返回 None。"""
    candidates = []
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "Rime")
    elif sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Rime")
    else:
        candidates.append(Path.home() / ".local" / "share" / "fcitx5" / "rime")
        candidates.append(Path.home() / ".config" / "ibus" / "rime")

    for c in candidates:
        if c.exists():
            return c.resolve()
    return None


def resolve_rime_dir(user_arg: str | None) -> Path:
    """命令行 --rime-dir 优先，否则自动探测，都不行则报错。"""
    if user_arg:
        p = Path(os.path.expandvars(user_arg)).expanduser()
        try:
            p = p.resolve()
        except OSError as e:
            raise FileNotFoundError(f"无法解析路径 {user_arg!r}: {e}")
        if not p.exists():
            raise FileNotFoundError(f"--rime-dir 指定的目录不存在: {p}")
        if not p.is_dir():
            raise NotADirectoryError(f"--rime-dir 指定的不是目录: {p}")
        return p

    detected = detect_rime_dir()
    if detected is None:
        raise FileNotFoundError(
            "无法自动定位 RIME 用户目录。\n"
            "请通过 --rime-dir 指定，例如：\n"
            "    python install.py --rime-dir \"D:/RimeConfig\"\n"
            "    python install.py --rime-dir ~/Library/Rime"
        )
    return detected


# ---------------------------------------------------------------------------
# 可操作性检查
# ---------------------------------------------------------------------------

def check_source(src: Path) -> str | None:
    """源可用返回 None，否则返回错误说明。"""
    if not src.exists():
        return f"源文件不存在: {src}"
    if not src.is_file():
        return f"源不是普通文件: {src}"
    return None


def check_target_writable(dst: Path) -> str | None:
    """判断目标位置是否可写。可写返回 None。"""
    parent = dst.parent
    cur = parent
    while not cur.exists():
        if cur == cur.parent:
            return f"无法创建目录: {parent}"
        cur = cur.parent

    if not cur.is_dir():
        return f"路径不是目录: {cur}"

    if not os.access(cur, os.W_OK):
        return f"目录不可写: {cur}"

    if dst.exists() and dst.is_dir():
        return f"目标是目录，无法覆盖: {dst}"

    return None


# ---------------------------------------------------------------------------
# 复制文件
# ---------------------------------------------------------------------------

def copy_file(src: Path, dst: Path, dry_run: bool, errors: list[str]) -> bool:
    err = check_source(src)
    if err:
        print(f"  [失败] {err}")
        errors.append(err)
        return False

    err = check_target_writable(dst)
    if err:
        print(f"  [失败] {err}")
        errors.append(err)
        return False

    if dry_run:
        action = "覆盖" if dst.exists() else "新增"
        print(f"  [计划] {action} {dst}  <-  {src}")
        return True

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except OSError as e:
        msg = f"写入失败 {dst}: {e}"
        print(f"  [失败] {msg}")
        errors.append(msg)
        return False

    print(f"  [安装] {src.name}  ->  {dst}")
    return True


# ---------------------------------------------------------------------------
# .custom.yaml 的智能合并
# ---------------------------------------------------------------------------

def merge_custom_yaml(src: Path, dst: Path, dry_run: bool,
                      errors: list[str]) -> bool:
    """
    合并 src 与 dst 的 patch 段：
        * patch 下的 list：去重后追加
        * patch 下的其它值：以 src 为准覆盖
    目标不存在时退化为直接复制。
    """
    err = check_source(src)
    if err:
        print(f"  [失败] {err}")
        errors.append(err)
        return False

    if not dst.exists():
        return copy_file(src, dst, dry_run, errors)

    err = check_target_writable(dst)
    if err:
        print(f"  [失败] {err}")
        errors.append(err)
        return False

    try:
        import yaml  # type: ignore
    except ImportError:
        print(f"  [警告] 未安装 pyyaml，将直接覆盖 {dst.name}")
        if dry_run:
            print(f"  [计划] 覆盖 {dst}  <-  {src}")
            return True
        try:
            shutil.copy2(src, dst)
        except OSError as e:
            msg = f"覆盖失败 {dst}: {e}"
            print(f"  [失败] {msg}")
            errors.append(msg)
            return False
        print(f"  [覆盖] {src.name}  ->  {dst}")
        return True

    try:
        src_data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
        dst_data = yaml.safe_load(dst.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        msg = f"读取 YAML 失败 ({src} / {dst}): {e}"
        print(f"  [失败] {msg}")
        errors.append(msg)
        return False

    src_patch = src_data.get("patch") or {}
    dst_patch = dst_data.get("patch") or {}

    merged = dict(dst_patch)
    added_keys = []
    for key, val in src_patch.items():
        if key in merged and isinstance(merged[key], list) and isinstance(val, list):
            new_items = [v for v in val if v not in merged[key]]
            if new_items:
                merged[key] = merged[key] + new_items
                added_keys.append(f"{key} (+{len(new_items)})")
        elif merged.get(key) != val:
            merged[key] = val
            added_keys.append(f"{key} (替换)")

    if not added_keys:
        print(f"  [跳过] {dst.name} 已是最新，无需合并")
        return True   # 幂等，不算失败

    dst_data["patch"] = merged

    if dry_run:
        print(f"  [计划] 合并 {dst}  patch: {', '.join(added_keys)}")
        return True

    try:
        with dst.open("w", encoding="utf-8") as f:
            yaml.safe_dump(dst_data, f,
                           allow_unicode=True,
                           sort_keys=False,
                           default_flow_style=False)
    except OSError as e:
        msg = f"写入失败 {dst}: {e}"
        print(f"  [失败] {msg}")
        errors.append(msg)
        return False

    print(f"  [合并] {dst.name}  patch: {', '.join(added_keys)}")
    return True


# ---------------------------------------------------------------------------
# 更新 default.custom.yaml 中的 patch/schema_list
# ---------------------------------------------------------------------------

def _schema_list_contains(text: str, ime_name: str) -> bool:
    """
    检查文本中的 schema_list 是否已包含 ime_name。
    兼容以下写法（引号可选）：
        - {schema: flypy_cangjie5}
        - { schema: flypy_cangjie5 }
        - schema: flypy_cangjie5
        - flypy_cangjie5
    """
    if not text:
        return False

    name = re.escape(ime_name)
    quoted = rf"[\"']?{name}[\"']?"

    brace = rf"-\s*\{{\s*schema\s*:\s*{quoted}\s*\}}"
    plain = rf"-\s*schema\s*:\s*{quoted}\s*$"
    bare = rf"-\s*{quoted}\s*$"

    pattern = rf"^[ \t]*(?:{brace}|{plain}|{bare})"
    return bool(re.search(pattern, text, re.MULTILINE))


def _insert_schema_into_yaml(text: str, ime_name: str) -> str:
    """
    在 YAML 文本的 patch/schema_list 中追加条目，保留原有格式和注释。
    新条目统一使用: - {schema: <ime_name>}
    """
    new_item_line = f"- {{schema: {ime_name}}}"

    if not text.strip():
        return (
            "patch:\n"
            "  schema_list:\n"
            f"    {new_item_line}\n"
        )

    m = re.search(r"^([ \t]*)schema_list[ \t]*:[ \t]*$", text, re.MULTILINE)
    if m:
        base_indent = m.group(1)
        item_indent = base_indent + "  "
        rest = text[m.end():]
        lines = rest.split("\n")

        consumed = 0
        last_content_end = 0
        for i, line in enumerate(lines):
            has_newline = (i < len(lines) - 1)
            step = len(line) + (1 if has_newline else 0)

            if not line.strip():
                consumed += step
                continue

            stripped = line.lstrip()
            line_indent = len(line) - len(stripped)
            belongs = (
                line_indent > len(base_indent)
                and (stripped.startswith("-")
                     or line_indent > len(item_indent))
            )
            if belongs:
                consumed += step
                last_content_end = consumed
            else:
                break

        insert_pos = m.end() + last_content_end
        new_line = f"{item_indent}{new_item_line}\n"
        return text[:insert_pos] + new_line + text[insert_pos:]

    m2 = re.search(r"^patch[ \t]*:[ \t]*$", text, re.MULTILINE)
    if m2:
        insertion = (
            "\n"
            "  schema_list:\n"
            f"    {new_item_line}\n"
        )
        return text[:m2.end()] + insertion + text[m2.end():]

    addition = (
        ("\n" if text and not text.endswith("\n") else "")
        + "patch:\n"
        "  schema_list:\n"
        f"    {new_item_line}\n"
    )
    return text + addition


def ensure_schema_in_default_custom(rime_dir: Path, ime_name: str,
                                    dry_run: bool,
                                    errors: list[str]) -> bool:
    """确保 <RIME>/default.custom.yaml 的 patch/schema_list 包含 ime_name。"""
    target = rime_dir / "default.custom.yaml"

    try:
        text = target.read_text(encoding="utf-8") if target.exists() else ""
    except OSError as e:
        msg = f"读取失败 {target}: {e}"
        print(f"  [失败] {msg}")
        errors.append(msg)
        return False

    if _schema_list_contains(text, ime_name):
        print(f"  [跳过] {target.name} 的 schema_list 已包含 {ime_name}")
        return True   # 幂等，不算失败

    err = check_target_writable(target)
    if err:
        print(f"  [失败] {err}")
        errors.append(err)
        return False

    if dry_run:
        if target.exists():
            print(f"  [计划] 更新 {target}：schema_list += {ime_name}")
        else:
            print(f"  [计划] 新建 {target}：schema_list 含 {ime_name}")
        return True

    new_text = _insert_schema_into_yaml(text, ime_name)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_text, encoding="utf-8")
    except OSError as e:
        msg = f"写入失败 {target}: {e}"
        print(f"  [失败] {msg}")
        errors.append(msg)
        return False

    print(f"  [更新] {target.name}: patch/schema_list += {ime_name}")
    return True


# ---------------------------------------------------------------------------
# 插件安装
# ---------------------------------------------------------------------------

def install_lua_dir(rime_dir: Path, dry_run: bool,
                    errors: list[str]) -> None:
    """把 <SOURCE>/lua/*.lua 复制到 <RIME>/lua/（跳过 rime.lua）。"""
    src_lua = SOURCE_DIR / LUA_DIR_SRC
    dst_lua = rime_dir / LUA_DIR_DST

    if not src_lua.exists():
        msg = f"源目录不存在: {src_lua}"
        print(f"  [失败] {msg}")
        errors.append(msg)
        return

    files = [
        f for f in sorted(src_lua.iterdir())
        if f.is_file()
        and f.suffix.lower() == ".lua"
        and f.name not in LUA_EXCLUDE
    ]
    if not files:
        print("  [提示] lua/ 目录下没有需要安装的 *.lua 文件")
        return

    if not dry_run:
        try:
            dst_lua.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"创建目录失败 {dst_lua}: {e}"
            print(f"  [失败] {msg}")
            errors.append(msg)
            return

    for f in files:
        copy_file(f, dst_lua / f.name, dry_run, errors)


def install_plugins(rime_dir: Path, ime_name: str, dry_run: bool,
                    errors: list[str]) -> None:
    """
    安装插件：
        * lua/*.lua              -> <RIME>/lua/
        * lua/rime.lua           -> <RIME>/rime.lua
        * latex/*.yaml           -> <RIME>/
        * <IME_NAME>.custom.yaml -> <RIME>/<IME_NAME>.custom.yaml（合并 patch）
    """
    print("[插件] 安装 lua/ 目录下的脚本")
    install_lua_dir(rime_dir, dry_run, errors)

    print("\n[插件] 安装 rime.lua / latex")
    for src_rel, dst_rel in PLUGIN_FILE_MAP:
        src = SOURCE_DIR / src_rel
        dst = rime_dir / dst_rel
        copy_file(src, dst, dry_run, errors)

    # <IME_NAME>.custom.yaml（插件配置文件，来源在脚本目录）
    custom_src = SOURCE_DIR / f"{ime_name}.custom.yaml"
    custom_dst = rime_dir / f"{ime_name}.custom.yaml"
    print(f"\n[插件] 合并 <{ime_name}>.custom.yaml")
    if custom_src.exists():
        merge_custom_yaml(custom_src, custom_dst, dry_run, errors)
    else:
        msg = f"未找到插件配置文件: {custom_src}"
        print(f"  [失败] {msg}")
        errors.append(msg)


# ---------------------------------------------------------------------------
# 方案安装（--ime-name）
# ---------------------------------------------------------------------------

def install_ime(rime_dir: Path, ime_name: str, dry_run: bool,
                errors: list[str]) -> None:
    """
    从脚本父目录安装：
        ../<IME_NAME>.schema.yaml  -> <RIME>/<IME_NAME>.schema.yaml
        ../<IME_NAME>*.dict.yaml   -> <RIME>/<IME_NAME>*.dict.yaml
    并确保 <RIME>/default.custom.yaml 的 schema_list 包含 <IME_NAME>。
    """
    print(f"[方案] 安装 <{ime_name}> 相关文件（源目录: {PARENT_DIR}）")

    # 1. schema.yaml（精确匹配）
    schema_src = PARENT_DIR / f"{ime_name}.schema.yaml"
    if schema_src.exists():
        copy_file(schema_src, rime_dir / schema_src.name, dry_run, errors)
    else:
        msg = f"未找到方案文件: {schema_src}"
        print(f"  [失败] {msg}")
        errors.append(msg)

    # 2. dict.yaml（前缀通配）
    pattern = f"{ime_name}*.dict.yaml"
    matched = sorted(PARENT_DIR.glob(pattern))
    if matched:
        for src in matched:
            copy_file(src, rime_dir / src.name, dry_run, errors)
    else:
        msg = f"未找到词典文件: {PARENT_DIR / pattern}"
        print(f"  [失败] {msg}")
        errors.append(msg)

    # 3. 注册到 default.custom.yaml
    print(f"\n[方案] 注册 {ime_name} 到 default.custom.yaml")
    ensure_schema_in_default_custom(rime_dir, ime_name, dry_run, errors)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="RIME 一键安装（插件 / 方案）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "    python install.py --ime-name flypy_cangjie5\n"
            "    python install.py --ime-name flypy_cangjie5 --plugins\n"
            "    python install.py --ime-name flypy_cangjie5 --plugins --dry-run\n"
            "    python install.py --rime-dir \"D:/RimeConfig\" --ime-name flypy_cangjie5 --plugins\n"
        ),
    )
    ap.add_argument(
        "--rime-dir",
        metavar="PATH",
        default=None,
        help="RIME 用户目录；不指定时按平台自动探测",
    )
    ap.add_argument(
        "--ime-name",
        metavar="IME_NAME",
        default=None,
        help="方案名：安装 ../<IME_NAME>.schema.yaml 与 ../<IME_NAME>*.dict.yaml，"
             "并把 <IME_NAME> 注册到 default.custom.yaml 的 schema_list",
    )
    ap.add_argument(
        "--plugins",
        action="store_true",
        help="安装插件：lua/*.lua、rime.lua、latex/*.yaml，并合并 <IME_NAME>.custom.yaml。"
             "需要与 --ime-name 一起使用",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="只检查与预览，不修改任何文件",
    )
    return ap.parse_args()


def _print_summary(errors: list[str], dry_run: bool) -> int:
    """打印汇总并返回退出码。"""
    if errors:
        print()
        print("!" * 60)
        print(f" ⚠️  安装过程中出现 {len(errors)} 项失败")
        print("!" * 60)
        for i, e in enumerate(errors, 1):
            print(f"   {i:>2}. {e}")
        print()
        if dry_run:
            print(" 这些失败项在真正执行时同样会失败，请先修正。")
        else:
            print(" 安装未全部完成，请修正后重试；已成功部分无需重复处理（幂等）。")
        return 1

    if dry_run:
        print("✅ DRY-RUN 结束，未修改任何文件，所有任务均可正常执行。")
        print("   移除 --dry-run 即可真正执行安装。")
    else:
        print("✅ 安装完成！请重新部署 RIME 使配置生效：")
        print("   Windows 小狼毫：右键托盘图标 → 重新部署")
        print("   macOS 鼠须管  ：右键菜单 → 重新部署")
        print("   Linux Fcitx5  ：fcitx5-remote -r")
    return 0


def main() -> int:
    args = parse_args()
    dry_run = args.dry_run

    # 前置校验
    if not args.plugins and not args.ime_name:
        print("未指定任何安装项。请至少使用 --ime-name <IME_NAME>。")
        print("示例：")
        print("    python install.py --ime-name flypy_cangjie5")
        print("    python install.py --ime-name flypy_cangjie5 --plugins")
        print("    python install.py --ime-name flypy_cangjie5 --plugins --dry-run")
        return 2

    if args.plugins and not args.ime_name:
        print("[错误] --plugins 必须与 --ime-name <IME_NAME> 一起使用。")
        print("       原因：插件的配置文件名为 <IME_NAME>.custom.yaml，需要方案名。")
        return 2

    print("=" * 60)
    if dry_run:
        print(" RIME 一键安装  [DRY-RUN：不修改任何文件]")
    else:
        print(" RIME 一键安装")
    print("=" * 60)

    try:
        rime_dir = resolve_rime_dir(args.rime_dir)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"\n[错误] {e}", file=sys.stderr)
        return 1

    top_err = None
    if rime_dir.exists():
        if not os.access(rime_dir, os.W_OK):
            top_err = f"RIME 目录不可写: {rime_dir}"
    else:
        top_err = f"RIME 目录不存在: {rime_dir}"

    print(f"\n[*] 脚本目录 : {SOURCE_DIR}")
    print(f"[*] 上级目录 : {PARENT_DIR}")
    print(f"[*] RIME 目录: {rime_dir}")
    print(f"[*] 目录来源 : {'命令行 --rime-dir' if args.rime_dir else '自动探测'}")
    print(f"[*] 模式     : {'dry-run（只预览）' if dry_run else '直接修改'}")
    if args.ime_name:
        print(f"[*] 方案名   : {args.ime_name}")
    if top_err:
        print(f"[!] 顶层预检: {top_err}")
    print()

    # 收集失败项
    errors: list[str] = []
    if top_err:
        errors.append(top_err)

    # 先装插件（合并 <IME_NAME>.custom.yaml）
    if args.plugins:
        install_plugins(rime_dir, args.ime_name, dry_run, errors)
        print()

    # 再装方案
    if args.ime_name:
        install_ime(rime_dir, args.ime_name, dry_run, errors)
        print()

    return _print_summary(errors, dry_run)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[中断] 用户取消", file=sys.stderr)
        sys.exit(130)
