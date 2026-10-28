#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 bopomofo.csv 產生 Lua 對照表：雙拼 → 拼音、拼音 → 注音。

用法：
    python tools/misc/mapping_bopomofo.py [--verbose]

預設隱藏 converter.py 匯入時產生的解析警告；加上 --verbose 可顯示。
"""
import argparse
import contextlib
import csv
import io
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS_DIR = HERE.parent
BOPOMOFO_CSV = HERE / "bopomofo.csv"


def load_flypy(verbose=False):
    """匯入上層 tools/converter.py。

    converter.py 在模組層級以相對路徑載入資料檔，因此匯入期間必須暫時
    切換到 tools/ 目錄；它同時會輸出大量與本腳本無關的警告，預設隱藏。
    """
    sys.path.insert(0, str(TOOLS_DIR))
    cwd = os.getcwd()
    os.chdir(TOOLS_DIR)
    try:
        if verbose:
            import converter as flypy
        else:
            with contextlib.redirect_stderr(io.StringIO()):
                import converter as flypy
    finally:
        os.chdir(cwd)
        sys.path.remove(str(TOOLS_DIR))
    return flypy


def load_bopomofo(path=BOPOMOFO_CSV):
    """讀取「注音<TAB>拼音」對照表，回傳 {拼音: 注音}。"""
    bopomofo = {}
    with open(path, newline="", encoding="utf-8") as csvfile:
        for row in csv.reader(csvfile):
            if not row:
                continue
            zh, py = row[0].strip().split()
            bopomofo[py] = zh
    return bopomofo


def show_pinyin_to_bopomofo(bopomofo):
    for py, zy in bopomofo.items():
        print(f"[\"%s\"]=\"%s\"," % (py, zy))


def show_sp_to_pinyin(flypy, bopomofo):
    for py in bopomofo:
        sp = flypy.pinyin_to_shuangpin(py)
        print(f"[\"%s\"]=\"%s\"," % (sp, py))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true",
                        help="顯示 converter.py 匯入時的警告")
    args = parser.parse_args(argv)

    flypy = load_flypy(verbose=args.verbose)
    bopomofo = load_bopomofo()

    print("# shuangpin to pinyin")
    show_sp_to_pinyin(flypy, bopomofo)

    print("# pinyin to bopomofo")
    show_pinyin_to_bopomofo(bopomofo)


if __name__ == "__main__":
    main()
