import csv
import sys
import convert_to_flypy_quick5 as flypy

bopomofo_mapping = "bopomofo.csv"

bopomofo = {} # py -> bopomofo

with open(bopomofo_mapping, newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        zh,py = row[0].strip().split()
        bopomofo[py] = zh

def show_pinyin_to_bopomofo():
    for py, zy in bopomofo.items():
        #py = flypy.get_toneless_pinyin(py)
        print(f"[\"%s\"]=\"%s\"," %(py, zy))

def show_sp_to_pinyin():
    for py in bopomofo:
        #py = flypy.get_toneless_pinyin(py)
        sp = flypy.pinyin_to_shuangpin(py)
        print(f"[\"%s\"]=\"%s\"," %(sp, py))

print("# shuangpin to pinyin")
show_sp_to_pinyin()

print("# pinyin to bopomofo")
show_pinyin_to_bopomofo()
