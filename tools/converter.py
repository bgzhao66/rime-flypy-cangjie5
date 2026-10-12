# -*- coding: utf-8 -*-
"""
Pinyin → Shuangpin (Xiaohe) converter with incremental encoding.

主要特性：
- 主碼：每字雙拼（兩碼）拼接，全部小寫。
- 頻率以「字詞 + 無調讀音序列」為唯一鍵累加，與輔助碼序列無關：
  同一字詞的多個有調讀音，若無調形式相同，視為同一條目，頻率相加。
- 條目結構：每個 (word, toneless_seq) 對應一個 entry，
  其 aux_seqs 為該字詞所有可能的輔助碼序列（list of list）。
- 增量編碼：對每個 (word, toneless_seq)，將其 aux_seqs 視為 trie 中的路徑，
  從根（full_code）出發，對每條路徑搜索一個無衝突的最短編碼。
  * 若多條路徑產生相同的最短碼，則合併到該 code 下；
  * 若路徑在 trie 中已分叉、產生不同編碼，則各自視為獨立編碼，不合併。
  結果結構：{(word, toneless_seq): {code: [remaining_aux_seq, ...]}}
- 輔助碼來源：倉頡碼（小寫）。
  統一處理：對每個字的倉頡碼列表做笛卡爾積，每個組合按詞長生成一個輔助碼序列。
  * 單字：尾碼、首碼、次碼（單字為多字詞的特例）
  * 雙字詞：尾字尾碼、首字首碼、尾字首碼
  * 三字詞：尾字尾碼、首字首碼、次字首碼
  * 四字及以上：無倉頡輔助碼，僅一個無輔助碼變體
- 單字長碼：若某主碼長度 < 4，則以該主碼為根，在該字詞記錄的剩餘 aux 樹基礎上
  繼續遍歷，對每條路徑逐步追加 aux_seq 直至碼長 >= 4 且唯一；
  aux_seq 耗盡後追加 a, b, c, ... 直至唯一。
  例如「低」→ dimo, diio。
- 簡碼：僅 1~3 字詞，長度 = 雙拼主碼長度 - 1，
  按詞頻降序分配；不得與任何主碼或已分配簡碼衝突。
  簡碼只看雙拼主碼，與倉頡輔助碼無關；
  同一 (word, toneless_seq) 只分配一個簡碼。
  輸出到 {name}_short.dict.yaml。
- 1~3 字詞若含無倉頡碼的字：打印錯誤日誌並放棄該字詞編碼。
- 解析帶拼音的詞彙文件時，校驗「拼音數 == 字數」，
  不一致則打印錯誤日誌並忽略該詞。
- 額外詞表：通過 input_files 傳入，每行 "word [frequency]"。
  已存在於主詞庫中的詞會被移除（按 word 去重）；
  剩餘詞條的拼音合成僅使用標準拼音 (kCharacterCodes)，
  不使用非標準拼音 (kCharacterCodesNonstandard)。
  基於主表 used_codes 進行增量編碼，輸出到 {name}_extra.dict.yaml。
- 所有編碼（主碼、輔助碼、字母後綴、長碼、簡碼）均為小寫字母。
"""

import sys
import re
import argparse
import unicodedata
import unittest
from collections import defaultdict
from itertools import product


# ============================================================
# 無聲調拼音映射
# ============================================================

TONELESS_MAPPING = """
ā a
á a
ǎ a
à a
ē e
é e
ě e
è e
ê ai
ê̄ ai
ế ai
ê̌ ai
ề ai
ḿ m
m̀ m
ń n
ň n
ǹ n
ō o
ó o
ǒ o
ò o
ī i
í i
ǐ i
ì i
ū u
ú u
ǔ u
ù u
ü v
ǖ v
ǘ v
ǚ v
ǜ v
"""


def get_toneless_mapping():
    mapping = {}
    for line in TONELESS_MAPPING.split('\n'):
        line = line.strip()
        if not line:
            continue
        pinyin, toneless = line.split()
        mapping[pinyin] = toneless
    return mapping


kTonelessMapping = get_toneless_mapping()


def get_toneless_pinyin(pinyin):
    toneless = ''
    for c in pinyin:
        if c in kTonelessMapping:
            toneless += kTonelessMapping[c]
        elif unicodedata.category(c).startswith('L'):
            toneless += c
    return toneless


def get_toneless_pinyin_seq(pinyin_seq):
    return [get_toneless_pinyin(p) for p in pinyin_seq]


# ============================================================
# 小鶴雙拼映射（全部小寫）
# ============================================================

INITIALS = {
    "b": "b", "p": "p", "m": "m", "f": "f",
    "d": "d", "t": "t", "n": "n", "l": "l",
    "g": "g", "k": "k", "h": "h",
    "j": "j", "q": "q", "x": "x",
    "zh": "v", "ch": "i", "sh": "u", "r": "r",
    "z": "z", "c": "c", "s": "s",
    "y": "y", "w": "w", "": ""
}

FINALS = {
    "iu": "q", "ei": "w", "uan": "r", "van": "r", "ue": "t", "ve": "t", "üe": "t",
    "un": "y", "vn": "y", "ün": "y", "uo": "o", "o": "o", "ie": "p",
    "a": "a", "ong": "s", "iong": "s", "ai": "d", "en": "f", "eng": "g",
    "ang": "h", "an": "j", "uai": "k", "ing": "k", "uang": "l", "iang": "l",
    "ou": "z", "ua": "x", "ia": "x", "ao": "c", "ui": "v", "v": "v",
    "in": "b", "iao": "n", "ian": "m",
    "e": "e", "i": "i", "u": "u", "ü": "v"
}

SPECIAL_CASES = {
    "a": "aa", "o": "oo", "e": "ee",
    "ang": "ah", "eng": "eg", "ng": "eg",
    "m": "mm", "n": "nn", "hng": "hg",
    "lü": "lv", "nü": "nv"
}


def pinyin_to_shuangpin(toneless):
    """無聲調拼音 → 小鶴雙拼（兩碼，小寫）。"""
    toneless = toneless.strip().lower()
    if not toneless:
        raise ValueError("Input Pinyin cannot be empty.")
    if toneless in SPECIAL_CASES:
        return SPECIAL_CASES[toneless]
    if len(toneless) == 2:
        return toneless
    i = len(toneless)
    pos = i
    while i > 0:
        i -= 1
        if toneless[i:] in FINALS:
            pos = i
    final = toneless[pos:]
    initial = toneless[:pos]
    if initial not in INITIALS:
        raise ValueError(f"Unknown initial: {initial} in {toneless}")
    if final not in FINALS:
        raise ValueError(f"Unknown final: {final} in {toneless}")
    return INITIALS[initial] + FINALS[final]


def pinyin_to_shuangpin_seq(toneless_seq):
    return [pinyin_to_shuangpin(t) for t in toneless_seq]


# ============================================================
# 數據加載
# ============================================================

STANDARD_CHINESE = "standard_chinese.txt"
PINYIN_CODES = ["pinyin.txt", "pinyin_tw.txt"]
PINYIN_PHRASES = ["pinyin_phrase.txt", "pinyin_tw_phrase.txt"]
PINYIN_DICT = "pinyin_trad.dict.txt"
PINYIN_EXT1_DICT = "pinyin_trad_ext1.dict.txt"
CANGJIE_CODE = "cangjie5.dict.yaml"


def get_standard_code_from_file(file):
    """讀取 '拼音: 字1 字2 ...' 格式。"""
    words = {}
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line[0] == '#':
                continue
            chars = re.split(r'[\s,:]+', line)
            if len(chars) <= 1:
                continue
            pinyin = chars[0]
            for char in chars[1:]:
                if not char:
                    continue
                words.setdefault(char, []).append(pinyin)
    return words


def get_pinyin_code_from_files(files):
    """讀取 'UNICODE: py1,py2 # word' 格式。"""
    words = {}
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line[0] == '#':
                    continue
                parts = re.split(r'\s+', line)
                if len(parts) < 4:
                    continue
                word = parts[3].strip()
                pinyins = parts[1].split(',')
                words.setdefault(word, []).extend(pinyins)
    return words


def get_pinyin_phrase_from_files(files):
    """
    讀取 'word: py1 py2 ...' 格式。
    校驗「拼音數 == 字數」，不一致則打印錯誤日誌並忽略該詞。
    """
    words = {}
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line or line[0] == '#':
                    continue
                parts = re.split(r':\s+', line)
                if len(parts) < 2:
                    continue
                word = parts[0].strip()
                pinyins = [p for p in re.split(r'\s+', parts[1]) if p]
                if len(word) != len(pinyins):
                    print(
                        f"Error: Mismatched pinyin count for word '{word}' "
                        f"(file={file}, line={line_no}): "
                        f"{len(word)} characters vs {len(pinyins)} pinyins. Skipping.",
                        file=sys.stderr,
                    )
                    continue
                words.setdefault(word, []).append(pinyins)
    return words


def get_frequency_from_files(files):
    """
    讀取 'word<tab>py1 py2 ...<tab>frequency' 格式。
    校驗「音節數 == 字數」，不一致則打印錯誤日誌並忽略該詞。
    """
    freq = {}
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) < 3:
                    continue
                word, code, frequency = parts[0], parts[1], parts[2]
                syllables = [s for s in code.split() if s]
                if len(word) != len(syllables):
                    print(
                        f"Error: Mismatched syllable count for word '{word}' "
                        f"(file={file}, line={line_no}): "
                        f"{len(word)} characters vs {len(syllables)} syllables. Skipping.",
                        file=sys.stderr,
                    )
                    continue
                code = re.sub(r'(?<=[ln])ue', 've', code)
                freq.setdefault(word, {})
                if code not in freq[word]:
                    freq[word][code] = (0, 0)
                f0, p0 = freq[word][code]
                freq[word][code] = (f0 + int(frequency), -line_no if p0 == 0 else p0)
    return freq


def get_cangjie_code_from_file(file):
    """讀取 'word<tab>cjcode extra_info' 格式，倉頡碼轉小寫。"""
    words = {}
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line[0] == '#':
                continue
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            word = parts[0].strip()
            cjcode = parts[1].strip().split()[0].lower()
            if cjcode[0] in ('x', 'z'):
                continue
            words.setdefault(word, []).append(cjcode)
    return words


def merge_character_codes(standard_codes, pinyin_codes):
    """合併標準與拼音碼，返回 (codes, nonstandard)。"""
    codes = {w: list(v) for w, v in standard_codes.items()}
    nonstandard = {}
    for word, pys in pinyin_codes.items():
        if word not in codes:
            codes[word] = list(pys)
        else:
            extra = [py for py in pys if py not in codes[word]]
            if extra:
                nonstandard[word] = extra
    return codes, nonstandard


# ============================================================
# 全局數據
# ============================================================

kStandardCodes = get_standard_code_from_file(STANDARD_CHINESE)
kPinyinCodes = get_pinyin_code_from_files(PINYIN_CODES)
kCharacterCodes, kCharacterCodesNonstandard = merge_character_codes(
    kStandardCodes, kPinyinCodes)

kPinyinPhrases = get_pinyin_phrase_from_files(PINYIN_PHRASES)
kWordsFreq = get_frequency_from_files([PINYIN_DICT, PINYIN_EXT1_DICT])
kCangjieCodes = get_cangjie_code_from_file(CANGJIE_CODE)


def get_freq_of_word(word, toneless_code, freq_dict):
    """查詢詞頻，默認 (0, -sys.maxsize+1)。"""
    default = (0, -sys.maxsize + 1)
    if word not in freq_dict:
        return default
    return freq_dict[word].get(toneless_code, default)


def get_toneless_pinyin_phrases():
    """從 kPinyinPhrases 與 kWordsFreq 收集無聲調拼音短語。"""
    phrases = {}
    for word, seqs in kPinyinPhrases.items():
        for seq in seqs:
            toneless = ' '.join(get_toneless_pinyin_seq(seq))
            phrases.setdefault(word, set()).add(toneless)
    for word in kWordsFreq:
        if len(word) <= 1:
            continue
        for toneless in kWordsFreq[word]:
            phrases.setdefault(word, set()).add(toneless)
    return {w: [c.split() for c in s] for w, s in phrases.items()}


kTonelessPinyinPhrases = get_toneless_pinyin_phrases()


# ============================================================
# 輔助碼序列
# ============================================================

def check_cangjie_availability(word):
    """
    檢查字詞中每個字是否有倉頡碼。
    四字及以上無需輔助碼，直接通過。
    缺失則打印錯誤日誌並返回 False。
    """
    if len(word) >= 4:
        return True
    for char in word:
        if char not in kCangjieCodes or not kCangjieCodes[char]:
            print(
                f"Error: Missing Cangjie code for character '{char}' "
                f"in word '{word}'. Skipping encoding.",
                file=sys.stderr,
            )
            return False
    return True


def _single_char_aux_seq(cj):
    """單字倉頡碼 → 輔助碼序列（尾碼、首碼、次碼）。"""
    cj = cj.lower()
    seq = [cj[-1], cj[0]]
    if len(cj) >= 2:
        seq.append(cj[1])
    return seq[:3]


def _build_aux_seq_from_combo(combo):
    """
    由倉頡碼組合生成輔助碼序列。
    combo: tuple，每個元素是一個字的倉頡碼，按詞順序。
    """
    L = len(combo)
    if L == 1:
        return _single_char_aux_seq(combo[0])
    if L == 2:
        cj0, cj1 = combo
        return [cj1[-1], cj0[0], cj1[0]][:3]
    if L == 3:
        cj0, cj1, cj2 = combo
        return [cj2[-1], cj0[0], cj1[0]][:3]
    return []


def get_auxiliary_sequences(word):
    """
    返回該字詞所有可能的輔助碼序列（list of list）。
    統一處理：對每個字的倉頡碼列表做笛卡爾積，
    每個組合按詞長生成一個輔助碼序列。
    單字為多字詞的特例（只有一個字的組合）。
    四字及以上返回 [[]]。
    """
    L = len(word)
    if L >= 4:
        return [[]]

    cj_lists = []
    for ch in word:
        cjs = [c.lower() for c in kCangjieCodes.get(ch, [])]
        cj_lists.append(cjs)

    if any(not lst for lst in cj_lists):
        return [[]]

    result = []
    seen = set()
    for combo in product(*cj_lists):
        seq = _build_aux_seq_from_combo(combo)
        key = tuple(seq)
        if key not in seen:
            seen.add(key)
            result.append(seq)
    return result or [[]]


# ============================================================
# 增量編碼（逐條處理）
# ============================================================

def _index_to_letters(idx):
    """0 -> 'a', 25 -> 'z', 26 -> 'aa', 27 -> 'ab', ...（全部小寫）"""
    result = ''
    n = idx + 1
    while n > 0:
        n -= 1
        result = chr(ord('a') + n % 26) + result
        n //= 26
    return result


def _extend_with_letters(code, used_codes):
    """在 code 後追加 a, b, c, ... 直到找到未佔用的編碼。"""
    letter_idx = 0
    while True:
        candidate = code + _index_to_letters(letter_idx)
        if candidate not in used_codes:
            return candidate
        letter_idx += 1


def _assign_code(full_code, aux_seqs, used_codes, min_length=1):
    """
    為一組屬於同一個 (word, toneless_seq) 的 aux_seq 搜索編碼。
    把 aux_seqs 概念上構建成 trie 結構，對每條路徑搜索一個滿足要求的
    最短無衝突編碼；並在返回結果中記錄該編碼與已搜索節點對應的剩餘 aux 樹。

    - 若多條路徑產生同一編碼，則合併到該 code 下（路徑尚未分叉）；
    - 若路徑在 trie 中已分叉、產生不同編碼，則各自獨立，不合併。

    full_code: 雙拼主碼（作為編碼前綴）
    aux_seqs: 該字詞的所有輔助碼序列（trie 中的路徑）
    used_codes: 已佔用編碼集合
    min_length: 最短要求的編碼長度（主碼默認 1，長碼為 4）

    返回：{code: [remaining_aux_seq, ...]}
    """
    result = defaultdict(list)
    for aux_seq in aux_seqs:
        code = full_code
        remaining = list(aux_seq)
        while len(code) < min_length or code in used_codes:
            if remaining:
                code += remaining.pop(0)
            else:
                code = _extend_with_letters(code, used_codes)
                break
        result[code].append(remaining)
    return result


def incremental_encode(entries, initial_used_codes=None):
    """
    增量編碼：對每個 (word, toneless_seq)，將其 aux_seqs 視為 trie 中的路徑，
    從根（full_code）出發，對每條路徑搜索一個無衝突的最短編碼。

    - 若多條路徑產生相同最短碼，則合併到該 code 下；
    - 若路徑在 trie 中已分叉、產生不同編碼，則各自視為獨立編碼，不合併。

    返回 (results, used_codes)。
    results 結構：{(word, toneless_seq): {code: [remaining_aux_seq, ...]}}
    """
    used_codes = set(initial_used_codes) if initial_used_codes else set()
    results = defaultdict(lambda: defaultdict(list))

    sorted_entries = sorted(entries, key=lambda e: e['freq'], reverse=True)

    for e in sorted_entries:
        base_key = (e['word'], tuple(e['toneless_seq']))
        code_to_remaining = _assign_code(
            e['full_code'], e['aux_seqs'], used_codes, min_length=1)
        for code, remaining_list in code_to_remaining.items():
            results[base_key][code] = remaining_list
            used_codes.add(code)

    return results, used_codes


# ============================================================
# 單字長碼
# ============================================================

def generate_long_codes_for_chars(encode_result, used_codes):
    """
    為單字生成至少 4 字符的長碼（額外編碼）。
    對每個 (word, toneless_seq) 的每個主碼：
      - 若主碼長度 >= 4，跳過。
      - 否則以主碼為根，在該字詞記錄的剩餘 aux 樹基礎上繼續遍歷，
        對每條路徑逐步追加 aux_seq 直至碼長 >= 4 且唯一；
        aux_seq 耗盡後追加 a, b, c, ... 直至唯一。

    返回 (long_codes, long_used)。
    long_codes 結構：{(word, toneless_seq): {long_code: [remaining_aux_seq, ...]}}
    """
    long_codes = defaultdict(dict)
    long_used = set(used_codes)

    for base_key, code_map in encode_result.items():
        word, toneless_seq = base_key
        if len(word) != 1:
            continue
        for main_code, remaining_list in code_map.items():
            if len(main_code) >= 4:
                continue
            long_code_to_remaining = _assign_code(
                main_code, remaining_list, long_used, min_length=4)
            for c, rem_list in long_code_to_remaining.items():
                long_codes[base_key][c] = rem_list
                long_used.add(c)

    return long_codes, long_used


# ============================================================
# 簡碼
# ============================================================

def generate_short_codes(entries, encode_result, used_codes):
    """
    為 1~3 字詞生成簡碼。
    - 簡碼長度 = 雙拼主碼 (full_code) 長度 - 1；長度 < 2 時無法生成。
    - 不得與任何主碼或已分配的簡碼衝突。
    - 按詞頻降序分配。
    - 簡碼只看雙拼主碼，與倉頡輔助碼無關。
      同一 (word, toneless_seq) 只需处理一次，分配一个简码。

    返回 (short_codes, short_used)。
    """
    seen = {}
    for e in entries:
        base_key = (e['word'], tuple(e['toneless_seq']))
        if base_key not in seen:
            seen[base_key] = e

    indexed = []
    for base_key, e in seen.items():
        if len(e['word']) > 3:
            continue
        full_code = e['full_code']
        if len(full_code) < 2:
            continue
        candidate = full_code[:-1]
        indexed.append((base_key, candidate, e['freq']))

    if not indexed:
        return {}, set(used_codes)

    indexed.sort(key=lambda x: x[2], reverse=True)

    short_codes = {}
    short_used = set(used_codes)

    for base_key, candidate, freq in indexed:
        if base_key in short_codes:
            continue
        if candidate in short_used:
            continue
        short_codes[base_key] = candidate
        short_used.add(candidate)

    return short_codes, short_used


# ============================================================
# 條目構建與輸出
# ============================================================

def build_entries(char_codes, char_nonstandard, phrase_dict, freq_dict):
    """
    構建所有待編碼的條目。
    頻率以 (word, toneless_seq) 為唯一鍵累加，與輔助碼序列無關。
    每個 (word, toneless_seq) 對應一個 entry，其 aux_seqs 為該字詞
    所有可能的輔助碼序列。
    """
    # 第一遍：按 (word, toneless_seq) 累加頻率
    freq_map = {}

    def collect(word, pinyin_seq):
        toneless_seq = get_toneless_pinyin_seq(pinyin_seq)
        toneless_code = ' '.join(toneless_seq)
        freq = get_freq_of_word(word, toneless_code, freq_dict)
        base_key = (word, tuple(toneless_seq))
        old_f, old_p = freq_map.get(base_key, (0, -sys.maxsize + 1))
        new_f, new_p = freq
        freq_map[base_key] = (old_f + new_f, max(old_p, new_p))

    for char, pinyins in char_codes.items():
        for pinyin in pinyins:
            collect(char, [pinyin])

    for char, pinyins in char_nonstandard.items():
        for pinyin in pinyins:
            collect(char, [pinyin])

    for word, pinyin_seqs in phrase_dict.items():
        if len(word) <= 1:
            continue
        for pinyin_seq in pinyin_seqs:
            collect(word, pinyin_seq)

    # 第二遍：為每個 (word, toneless_seq) 生成一個 entry
    entries = []
    skipped = 0
    for (word, toneless_seq), freq in freq_map.items():
        if not check_cangjie_availability(word):
            skipped += 1
            continue

        try:
            flypys = pinyin_to_shuangpin_seq(list(toneless_seq))
        except (ValueError, AssertionError) as ex:
            print(f"Error: Failed to convert {toneless_seq} for word '{word}': {ex}",
                  file=sys.stderr)
            skipped += 1
            continue

        full_code = ''.join(flypys).lower()
        aux_seqs = get_auxiliary_sequences(word)

        entries.append({
            'word': word,
            'toneless_seq': list(toneless_seq),
            'full_code': full_code,
            'freq': freq,
            'aux_seqs': aux_seqs,
        })

    print(f"Total entries: {len(entries)}, skipped: {skipped}", file=sys.stderr)
    return entries


def build_sorted_dict(entries, encode_result):
    """從主碼結果構建 {word_length: {code: {word: (freq, p)}}}。"""
    freq_index = {}
    for e in entries:
        base_key = (e['word'], tuple(e['toneless_seq']))
        freq_index[base_key] = e['freq']

    sorted_dict = defaultdict(lambda: defaultdict(dict))
    for (word, toneless_seq), code_map in encode_result.items():
        freq = freq_index.get((word, toneless_seq))
        if freq is None:
            continue
        for code in code_map:
            length = len(word)
            cell = sorted_dict[length][code]
            if word in cell:
                cell[word] = max(cell[word], freq)
            else:
                cell[word] = freq
    return {L: {c: dict(w) for c, w in d.items()} for L, d in sorted_dict.items()}


def build_short_dict(entries, short_codes):
    """從簡碼結果構建 {code_length: {code: {word: (freq, p)}}}。"""
    result = defaultdict(lambda: defaultdict(dict))
    for e in entries:
        base_key = (e['word'], tuple(e['toneless_seq']))
        if base_key not in short_codes:
            continue
        code = short_codes[base_key]
        code_len = len(code)
        word = e['word']
        freq = e['freq']
        cell = result[code_len][code]
        if word in cell:
            cell[word] = max(cell[word], freq)
        else:
            cell[word] = freq
    return {L: {c: dict(w) for c, w in d.items()} for L, d in result.items()}


# ============================================================
# 額外詞表
# ============================================================

def get_words_from_file(file, words=None, min_length=1, max_length=10):
    """讀取額外詞彙文件，每行 "word [frequency]"（空格分隔）。"""
    if words is None:
        words = {}
    lineno = 0
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            lineno += 1
            if not line or line[0] == '#':
                continue
            items = line.split()
            if not items:
                continue
            word = items[0]
            frequency = 0
            if len(items) >= 2:
                try:
                    frequency = int(items[-1])
                except ValueError:
                    pass
            if len(word) < min_length or len(word) > max_length:
                continue
            if word not in words:
                words[word] = (0, 0)
            f0, p0 = words[word]
            words[word] = (f0 + frequency, -lineno if p0 == 0 else p0)
    return words


def get_descartes_products(lists):
    """[[a1, a2], [b1, b2]] -> [[a1,b1],[a1,b2],[a2,b1],[a2,b2]]"""
    result = [[]]
    for lst in lists:
        new_result = []
        for r in result:
            for x in lst:
                new_result.append(r + [x])
        result = new_result
    return result


def get_pinyin_seq_for_words(words):
    """為每個詞查找無調拼音序列，僅使用標準拼音 (kCharacterCodes)。"""
    result = {}
    for word in words:
        if word in kTonelessPinyinPhrases:
            result[word] = [list(seq) for seq in kTonelessPinyinPhrases[word]]
            continue
        encodes = []
        ok = True
        for char in word:
            if char not in kCharacterCodes:
                ok = False
                break
            candidates = kCharacterCodes[char]
            toneless_candidates = [get_toneless_pinyin(p) for p in candidates]
            seen = set()
            uniq = []
            for c in toneless_candidates:
                if c not in seen:
                    seen.add(c)
                    uniq.append(c)
            encodes.append(uniq)
        if not ok:
            continue
        result[word] = get_descartes_products(encodes)
    return result


def build_extra_entries(words):
    """
    為額外詞表構建待編碼條目。
    頻率以 (word, toneless_seq) 為唯一鍵累加，與輔助碼序列無關。
    每個 (word, toneless_seq) 對應一個 entry。
    """
    extra_pinyin = get_pinyin_seq_for_words(words)

    # 第一遍：按 (word, toneless_seq) 累加頻率
    freq_map = {}
    for word, pinyin_seqs in extra_pinyin.items():
        freq = words[word]
        for pinyin_seq in pinyin_seqs:
            toneless_seq = get_toneless_pinyin_seq(pinyin_seq)
            base_key = (word, tuple(toneless_seq))
            old_f, old_p = freq_map.get(base_key, (0, -sys.maxsize + 1))
            new_f, new_p = freq
            freq_map[base_key] = (old_f + new_f, max(old_p, new_p))

    # 第二遍：為每個 (word, toneless_seq) 生成一個 entry
    entries = []
    skipped = 0
    for (word, toneless_seq), freq in freq_map.items():
        if not check_cangjie_availability(word):
            skipped += 1
            continue

        try:
            flypys = pinyin_to_shuangpin_seq(list(toneless_seq))
        except (ValueError, AssertionError) as ex:
            print(f"Error: Failed to convert {toneless_seq} for word '{word}': {ex}",
                  file=sys.stderr)
            skipped += 1
            continue

        full_code = ''.join(flypys).lower()
        aux_seqs = get_auxiliary_sequences(word)

        entries.append({
            'word': word,
            'toneless_seq': list(toneless_seq),
            'full_code': full_code,
            'freq': freq,
            'aux_seqs': aux_seqs,
        })

    print(f"Extra entries: {len(entries)}, skipped: {skipped}", file=sys.stderr)
    return entries


# ============================================================
# 輸出
# ============================================================

def get_header(name, import_tables=None):
    hdr = f"""# rime dictionary
# encoding: utf-8

---
name: {name}
version: "0.1"
sort: by_weight"""
    if import_tables:
        hdr += """
max_phrase_length: 10
min_phrase_weight: 100
encoder:
  exclude_patterns:
    - '^[a-z].?$'
    - '^[a-z]..$'
  rules:
    - length_equal: 2
      formula: "AaAbBaBbBcAdBd"
    - length_equal: 3
      formula: "AaAbBaBbCaCbCcAdBd"
    - length_equal: 4
      formula: "AaAbBaBbCaCbDaDb"
    - length_equal: 5
      formula: "AaAbBaBbCaCbDaDbEaEb"
    - length_equal: 6
      formula: "AaAbBaBbCaCbDaDbEaEbFaFb"
    - length_equal: 7
      formula: "AaAbBaBbCaCbDaDbEaEbFaFbGaGb"
import_tables:"""
        for t in import_tables:
            hdr += f"\n  - {t}"
    hdr += "\n...\n"
    return hdr


def print_word_codes(word_codes, outfile=sys.stdout, freq_base=0, max_length=10):
    for length in sorted(word_codes.keys()):
        for code in sorted(word_codes[length].keys()):
            for word in sorted(word_codes[length][code].keys()):
                if len(word) > max_length:
                    continue
                freq = word_codes[length][code][word]
                print(f"{word}\t{code}\t{freq[0] + freq_base}", file=outfile)


# ============================================================
# 命令行參數
# ============================================================

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert Pinyin to Shuangpin with incremental encoding.")
    parser.add_argument("--name", default="", help="Base name of output tables")
    parser.add_argument("--output-dir", default="../",
                        help="Output directory for dict files")
    parser.add_argument("--chinese-code", action="store_true",
                        help="Write Chinese character codes to file")
    parser.add_argument("--phrase", action="store_true",
                        help="Write phrase codes to file")
    parser.add_argument("--short-code", action="store_true",
                        help="Write short codes (簡碼) to file")
    parser.add_argument("--extra-table", action="store_true",
                        help="Write extra words (from input_files) to a separate table")
    parser.add_argument("--test", action="store_true",
                        help="Run unit tests")
    parser.add_argument("input_files", nargs='*', default=[],
                        help="Extra input files (one 'word [frequency]' per line)")
    return parser.parse_args(argv)


# ============================================================
# 主流程
# ============================================================

def main(argv=None):
    args = parse_args(argv)

    if args.test:
        unittest.main(argv=[sys.argv[0]], exit=False)
        return

    name = args.name.strip() if args.name else ''
    out_dir = args.output_dir

    entries = build_entries(
        kCharacterCodes,
        kCharacterCodesNonstandard,
        kTonelessPinyinPhrases,
        kWordsFreq,
    )

    encode_result, used_codes = incremental_encode(entries)
    sorted_dict = build_sorted_dict(entries, encode_result)

    char_dict = {L: c for L, c in sorted_dict.items() if L == 1}
    phrase_dict = {L: c for L, c in sorted_dict.items() if L >= 2}

    phrase_name = f"{name}_phrase" if name else "phrase"
    short_name = f"{name}_short" if name else "short"
    extra_name = f"{name}_extra" if name else "extra"

    import_tables = []
    if args.phrase:
        import_tables.append(phrase_name)
    if args.short_code:
        import_tables.append(short_name)
    if args.extra_table:
        import_tables.append(extra_name)

    if args.chinese_code:
        char_name = name if name else "char"

        long_codes, long_used = generate_long_codes_for_chars(encode_result, used_codes)
        used_codes |= long_used
        if 1 not in char_dict:
            char_dict[1] = {}

        freq_index = {}
        for e in entries:
            if len(e['word']) != 1:
                continue
            base_key = (e['word'], tuple(e['toneless_seq']))
            freq_index[base_key] = e['freq']

        for base_key, code_map in long_codes.items():
            freq = freq_index.get(base_key)
            if freq is None:
                continue
            word = base_key[0]
            for code in code_map:
                if code not in char_dict[1]:
                    char_dict[1][code] = {}
                if word in char_dict[1][code]:
                    char_dict[1][code][word] = max(char_dict[1][code][word], freq)
                else:
                    char_dict[1][code][word] = freq

        filename = f"{out_dir}{char_name}.dict.yaml"
        with open(filename, 'w', encoding='utf-8') as f:
            print(get_header(char_name, import_tables), file=f)
            print_word_codes(char_dict, f, freq_base=10000)
        print(f"Character codes written to {filename}", file=sys.stderr)

    if args.phrase:
        filename = f"{out_dir}{phrase_name}.dict.yaml"
        with open(filename, 'w', encoding='utf-8') as f:
            print(get_header(phrase_name), file=f)
            print_word_codes(phrase_dict, f)
        print(f"Phrase codes written to {filename}", file=sys.stderr)

    if args.short_code:
        short_codes, short_used = generate_short_codes(entries, encode_result, used_codes)
        used_codes |= short_used
        short_dict = build_short_dict(entries, short_codes)
        filename = f"{out_dir}{short_name}.dict.yaml"
        with open(filename, 'w', encoding='utf-8') as f:
            print(get_header(short_name), file=f)
            print_word_codes(short_dict, f)
        print(f"Short codes written to {filename}", file=sys.stderr)

    if args.input_files:
        extra_words = {}
        for input_file in args.input_files:
            extra_words = get_words_from_file(input_file, extra_words)
        total_read = len(extra_words)

        main_words = set(e['word'] for e in entries)
        extra_words = {w: f for w, f in extra_words.items() if w not in main_words}
        removed = total_read - len(extra_words)

        print(
            f"Read {total_read} extra words, removed {removed} already in main table, "
            f"{len(extra_words)} remain.",
            file=sys.stderr,
        )

        if extra_words:
            extra_entries = build_extra_entries(extra_words)
            extra_encode_result, extra_used_codes = incremental_encode(
                extra_entries, initial_used_codes=used_codes)
            used_codes |= extra_used_codes
            extra_sorted_dict = build_sorted_dict(extra_entries, extra_encode_result)

            if args.extra_table:
                filename = f"{out_dir}{extra_name}.dict.yaml"
                with open(filename, 'w', encoding='utf-8') as f:
                    print(get_header(extra_name), file=f)
                    print_word_codes(extra_sorted_dict, f)
                print(f"Extra words written to {filename}", file=sys.stderr)

# ============================================================
# 單元測試輔助
# ============================================================

def _find_code(encode_result, word, toneless_seq):
    """從 encode_result 中返回給定 (word, toneless_seq) 的第一個編碼。"""
    code_map = encode_result.get((word, tuple(toneless_seq)), {})
    if not code_map:
        return None
    return next(iter(code_map))


def _find_codes(encode_result, word, toneless_seq):
    """從 encode_result 中返回給定 (word, toneless_seq) 的所有編碼列表。"""
    code_map = encode_result.get((word, tuple(toneless_seq)), {})
    return list(code_map.keys())


def _find_long_code(long_codes, word, toneless_seq):
    """從 long_codes 中返回給定 (word, toneless_seq) 的第一個長碼。"""
    code_map = long_codes.get((word, tuple(toneless_seq)), {})
    if not code_map:
        return None
    return next(iter(code_map))


# ============================================================
# 單元測試
# ============================================================

class TestToneless(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(get_toneless_pinyin("mǎ"), "ma")
        self.assertEqual(get_toneless_pinyin("nǐ"), "ni")
        self.assertEqual(get_toneless_pinyin("hǎo"), "hao")
        self.assertEqual(get_toneless_pinyin("lǜ"), "lv")


class TestShuangpin(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(pinyin_to_shuangpin("a"), "aa")
        self.assertEqual(pinyin_to_shuangpin("o"), "oo")
        self.assertEqual(pinyin_to_shuangpin("e"), "ee")
        self.assertEqual(pinyin_to_shuangpin("fei"), "fw")
        self.assertEqual(pinyin_to_shuangpin("zhong"), "vs")
        self.assertEqual(pinyin_to_shuangpin("xue"), "xt")


class TestAuxSeq(unittest.TestCase):
    def test_single_char(self):
        seqs = get_auxiliary_sequences("你")
        self.assertTrue(any(s == ["f", "o", "n"] for s in seqs))

    def test_two_char(self):
        seqs = get_auxiliary_sequences("你好")
        self.assertTrue(any(s == ["d", "o", "v"] for s in seqs))

    def test_three_char(self):
        seqs = get_auxiliary_sequences("甲乙丙")
        self.assertTrue(all(len(s) <= 3 for s in seqs))

    def test_four_char(self):
        seqs = get_auxiliary_sequences("中華人民")
        self.assertEqual(seqs, [[]])

    def test_all_lowercase(self):
        for word in ["你", "你好", "長臂猿"]:
            for seq in get_auxiliary_sequences(word):
                for c in seq:
                    self.assertTrue(c.islower(), f"'{c}' from '{word}' is not lowercase")


class TestAssignCode(unittest.TestCase):
    def test_single_path_no_conflict(self):
        result = _assign_code('di', [['m', 'o', 'h']], set(), min_length=1)
        self.assertIn('di', result)
        self.assertEqual(result['di'], [['m', 'o', 'h']])

    def test_single_path_conflict(self):
        result = _assign_code('di', [['m', 'o', 'h']], {'di'}, min_length=1)
        self.assertIn('dim', result)
        self.assertEqual(result['dim'], [['o', 'h']])

    def test_two_paths_same_code_merge(self):
        result = _assign_code('di', [['m', 'o', 'h'], ['i', 'o', 'h']],
                              set(), min_length=1)
        self.assertEqual(list(result.keys()), ['di'])
        self.assertEqual(len(result['di']), 2)
        self.assertIn(['m', 'o', 'h'], result['di'])
        self.assertIn(['i', 'o', 'h'], result['di'])

    def test_two_paths_diverge_kept_independently(self):
        result = _assign_code('di', [['m', 'o', 'h'], ['i', 'o', 'h']],
                              {'di'}, min_length=1)
        self.assertIn('dim', result)
        self.assertIn('dii', result)
        self.assertEqual(result['dim'], [['o', 'h']])
        self.assertEqual(result['dii'], [['o', 'h']])

    def test_min_length_4(self):
        result = _assign_code('di', [['m', 'o', 'h'], ['i', 'o', 'h']],
                              set(), min_length=4)
        self.assertIn('dimo', result)
        self.assertIn('diio', result)
        self.assertEqual(result['dimo'], [['h']])
        self.assertEqual(result['diio'], [['h']])


class TestIncremental(unittest.TestCase):
    def test_unique_base_codes(self):
        entries = [
            {'word': '你', 'toneless_seq': ['ni'], 'full_code': 'ni',
             'freq': (100, -1), 'aux_seqs': [['f', 'o', 'n']]},
            {'word': '好', 'toneless_seq': ['hao'], 'full_code': 'hc',
             'freq': (90, -1), 'aux_seqs': [['d', 'v', 'n']]},
        ]
        result, used = incremental_encode(entries)
        self.assertEqual(_find_code(result, '你', ['ni']), 'ni')
        self.assertEqual(_find_code(result, '好', ['hao']), 'hc')

    def test_highest_freq_keeps_base_code(self):
        entries = [
            {'word': '你', 'toneless_seq': ['ni'], 'full_code': 'ni',
             'freq': (5000, -1), 'aux_seqs': [['f', 'o', 'n']]},
            {'word': '妮', 'toneless_seq': ['ni'], 'full_code': 'ni',
             'freq': (100, -1), 'aux_seqs': [['f', 'o', 'n']]},
        ]
        result, used = incremental_encode(entries)
        self.assertEqual(_find_code(result, '你', ['ni']), 'ni')
        self.assertEqual(_find_code(result, '妮', ['ni']), 'nif')

    def test_cross_length_freq_priority(self):
        entries = [
            {'word': '𤷒', 'toneless_seq': ['bi'], 'full_code': 'bwjk',
             'freq': (10000, -1), 'aux_seqs': [['f']]},
            {'word': '北京', 'toneless_seq': ['bei', 'jing'],
             'full_code': 'bwjk',
             'freq': (53178, -1), 'aux_seqs': [['g', 'b', 'j']]},
        ]
        result, used = incremental_encode(entries)
        self.assertEqual(_find_code(result, '北京', ['bei', 'jing']), 'bwjk')
        self.assertEqual(_find_code(result, '𤷒', ['bi']), 'bwjkf')

    def test_low_freq_group_extends_after_high_freq_cross(self):
        entries = [
            {'word': '被', 'toneless_seq': ['bei'], 'full_code': 'bw',
             'freq': (148131, -1), 'aux_seqs': [['d', 'o']]},
            {'word': '北京', 'toneless_seq': ['bei', 'jing'],
             'full_code': 'bwjk',
             'freq': (53178, -1), 'aux_seqs': [['g', 'b']]},
            {'word': '北', 'toneless_seq': ['bei'], 'full_code': 'bw',
             'freq': (25237, -1), 'aux_seqs': [['j', 'o']]},
            {'word': '𤷒', 'toneless_seq': ['bi'], 'full_code': 'bw',
             'freq': (10000, -1), 'aux_seqs': [['j', 'k', 'f']]},
        ]
        result, used = incremental_encode(entries)
        self.assertEqual(_find_code(result, '被', ['bei']), 'bw')
        self.assertEqual(_find_code(result, '北京', ['bei', 'jing']), 'bwjk')
        self.assertEqual(_find_code(result, '北', ['bei']), 'bwj')
        self.assertEqual(_find_code(result, '𤷒', ['bi']), 'bwjkf')

    def test_conflict_with_aux(self):
        entries = [
            {'word': '甲', 'toneless_seq': ['jia'], 'full_code': 'aa',
             'freq': (100, -1), 'aux_seqs': [['a', 'f']]},
            {'word': '乙', 'toneless_seq': ['yi'], 'full_code': 'aa',
             'freq': (90, -1), 'aux_seqs': [['a', 'f']]},
            {'word': '丙', 'toneless_seq': ['bing'], 'full_code': 'aa',
             'freq': (80, -1), 'aux_seqs': [['a', 'f']]},
        ]
        result, _ = incremental_encode(entries)
        self.assertEqual(_find_code(result, '甲', ['jia']), 'aa')
        self.assertEqual(_find_code(result, '乙', ['yi']), 'aaa')
        self.assertEqual(_find_code(result, '丙', ['bing']), 'aaaf')

    def test_aux_exhausted_letters(self):
        entries = [
            {'word': '甲', 'toneless_seq': ['jia'], 'full_code': 'aa',
             'freq': (100, -1), 'aux_seqs': [[]]},
            {'word': '乙', 'toneless_seq': ['yi'], 'full_code': 'aa',
             'freq': (90, -1), 'aux_seqs': [[]]},
            {'word': '丙', 'toneless_seq': ['bing'], 'full_code': 'aa',
             'freq': (80, -1), 'aux_seqs': [[]]},
        ]
        result, _ = incremental_encode(entries)
        self.assertEqual(_find_code(result, '甲', ['jia']), 'aa')
        self.assertEqual(_find_code(result, '乙', ['yi']), 'aaa')
        self.assertEqual(_find_code(result, '丙', ['bing']), 'aab')

    def test_aux_one_level_then_letters(self):
        entries = [
            {'word': '甲', 'toneless_seq': ['jia'], 'full_code': 'aa',
             'freq': (100, -1), 'aux_seqs': [['a']]},
            {'word': '乙', 'toneless_seq': ['yi'], 'full_code': 'aa',
             'freq': (90, -1), 'aux_seqs': [['a']]},
            {'word': '丙', 'toneless_seq': ['bing'], 'full_code': 'aa',
             'freq': (80, -1), 'aux_seqs': [['a']]},
        ]
        result, _ = incremental_encode(entries)
        self.assertEqual(_find_code(result, '甲', ['jia']), 'aa')
        self.assertEqual(_find_code(result, '乙', ['yi']), 'aaa')
        self.assertEqual(_find_code(result, '丙', ['bing']), 'aaaa')

    def test_initial_used_codes(self):
        entries = [
            {'word': 'X', 'toneless_seq': ['x'], 'full_code': 'ab',
             'freq': (100, -1), 'aux_seqs': [['f']]},
        ]
        result, used = incremental_encode(entries, initial_used_codes={'ab'})
        self.assertEqual(_find_code(result, 'X', ['x']), 'abf')
        self.assertIn('ab', used)
        self.assertIn('abf', used)

    def test_multi_aux_same_code_merge(self):
        entries = [
            {'word': '低', 'toneless_seq': ['di'], 'full_code': 'di',
             'freq': (100, -1), 'aux_seqs': [['m', 'o', 'h'], ['i', 'o', 'h']]},
        ]
        result, _ = incremental_encode(entries)
        code_map = result[('低', ('di',))]
        self.assertEqual(list(code_map.keys()), ['di'])
        self.assertEqual(len(code_map['di']), 2)

    def test_multi_aux_diverge_kept_independently(self):
        entries = [
            {'word': '低', 'toneless_seq': ['di'], 'full_code': 'di',
             'freq': (100, -1), 'aux_seqs': [['m', 'o', 'h'], ['i', 'o', 'h']]},
        ]
        result, _ = incremental_encode(entries, initial_used_codes={'di'})
        code_map = result[('低', ('di',))]
        self.assertEqual(len(code_map), 2)
        self.assertIn('dim', code_map)
        self.assertIn('dii', code_map)
        self.assertEqual(code_map['dim'], [['o', 'h']])
        self.assertEqual(code_map['dii'], [['o', 'h']])


class TestLongCode(unittest.TestCase):
    def test_single_variant_long_code(self):
        entries = [
            {'word': '你', 'toneless_seq': ['ni'], 'full_code': 'ni',
             'freq': (100, -1), 'aux_seqs': [['f', 'o', 'n']]},
        ]
        encode_result, used_codes = incremental_encode(entries)
        self.assertEqual(_find_code(encode_result, '你', ['ni']), 'ni')
        long_codes, _ = generate_long_codes_for_chars(encode_result, used_codes)
        self.assertEqual(_find_long_code(long_codes, '你', ['ni']), 'nifo')

    def test_multi_variant_long_codes_share_full_code_base(self):
        entries = [
            {'word': '低', 'toneless_seq': ['di'], 'full_code': 'di',
             'freq': (100, -1), 'aux_seqs': [['m', 'o', 'h'], ['i', 'o', 'h']]},
        ]
        encode_result, used_codes = incremental_encode(entries)
        code_map = encode_result[('低', ('di',))]
        self.assertEqual(list(code_map.keys()), ['di'])
        self.assertEqual(len(code_map['di']), 2)

        long_codes, _ = generate_long_codes_for_chars(encode_result, used_codes)
        lc_map = long_codes[('低', ('di',))]
        self.assertIn('dimo', lc_map)
        self.assertIn('diio', lc_map)

    def test_long_code_conflict_adds_letter(self):
        entries = [
            {'word': '你', 'toneless_seq': ['ni'], 'full_code': 'ni',
             'freq': (100, -1), 'aux_seqs': [['f', 'o', 'n']]},
        ]
        encode_result, used_codes = incremental_encode(entries)
        used_codes.add('nifo')
        used_codes.add('nifon')
        long_codes, _ = generate_long_codes_for_chars(encode_result, used_codes)
        self.assertEqual(_find_long_code(long_codes, '你', ['ni']), 'nifona')


class TestShortCode(unittest.TestCase):
    def test_basic(self):
        entries = [
            {'word': '你', 'toneless_seq': ['ni'], 'full_code': 'ni',
             'freq': (5000, -1), 'aux_seqs': [['f', 'o', 'n']]},
            {'word': '妮', 'toneless_seq': ['ni'], 'full_code': 'ni',
             'freq': (100, -1), 'aux_seqs': [['f', 'o', 'n']]},
        ]
        encode_result, used_codes = incremental_encode(entries)
        self.assertEqual(_find_code(encode_result, '你', ['ni']), 'ni')
        self.assertEqual(_find_code(encode_result, '妮', ['ni']), 'nif')

        short_codes, _ = generate_short_codes(entries, encode_result, used_codes)
        self.assertEqual(short_codes[('你', ('ni',))], 'n')
        self.assertNotIn(('妮', ('ni',)), short_codes)

    def test_no_short_code_for_long_words(self):
        entries = [
            {'word': '甲乙丙丁', 'toneless_seq': ['jia', 'yi', 'bing', 'ding'],
             'full_code': 'abcdefgh', 'freq': (1000, -1), 'aux_seqs': [[]]},
            {'word': '甲乙丙', 'toneless_seq': ['jia', 'yi', 'bing'],
             'full_code': 'abcdef', 'freq': (100, -1), 'aux_seqs': [[]]},
        ]
        encode_result, used_codes = incremental_encode(entries)
        short_codes, _ = generate_short_codes(entries, encode_result, used_codes)
        self.assertNotIn(('甲乙丙丁', ('jia', 'yi', 'bing', 'ding')), short_codes)
        self.assertEqual(short_codes[('甲乙丙', ('jia', 'yi', 'bing'))], 'abcde')

    def test_short_code_length_is_full_code_minus_one(self):
        entries = [
            {'word': '甲', 'toneless_seq': ['jia'], 'full_code': 'ab',
             'freq': (100, -1), 'aux_seqs': [[]]},
            {'word': '乙丙', 'toneless_seq': ['yi', 'bing'],
             'full_code': 'xyzabc', 'freq': (90, -1), 'aux_seqs': [[]]},
        ]
        encode_result, used_codes = incremental_encode(entries)
        short_codes, _ = generate_short_codes(entries, encode_result, used_codes)
        self.assertEqual(len(short_codes[('甲', ('jia',))]), 1)
        self.assertEqual(len(short_codes[('乙丙', ('yi', 'bing'))]), 5)

    def test_short_code_freq_priority(self):
        entries = [
            {'word': '甲', 'toneless_seq': ['jia'], 'full_code': 'abc',
             'freq': (100, -1), 'aux_seqs': [[]]},
            {'word': '乙', 'toneless_seq': ['yi'], 'full_code': 'abd',
             'freq': (200, -1), 'aux_seqs': [[]]},
        ]
        encode_result, used_codes = incremental_encode(entries)
        short_codes, _ = generate_short_codes(entries, encode_result, used_codes)
        self.assertEqual(short_codes[('乙', ('yi',))], 'ab')
        self.assertNotIn(('甲', ('jia',)), short_codes)


class TestExtraWords(unittest.TestCase):
    def test_get_words_from_file(self):
        import tempfile, os
        content = "你好 100\n世界 200\n你好 50\n# 註釋\n單 300\n"
        with tempfile.NamedTemporaryFile('w', encoding='utf-8',
                                         suffix='.txt', delete=False) as f:
            f.write(content)
            path = f.name
        try:
            words = get_words_from_file(path)
            self.assertIn('你好', words)
            self.assertIn('世界', words)
            self.assertEqual(words['你好'][0], 150)
            self.assertEqual(words['世界'][0], 200)
            self.assertIn('單', words)
        finally:
            os.unlink(path)

    def test_get_pinyin_seq_for_words(self):
        words = {'你': (100, -1)}
        result = get_pinyin_seq_for_words(words)
        self.assertIn('你', result)
        self.assertTrue(len(result['你']) > 0)

    def test_get_pinyin_seq_unknown_char(self):
        words = {'ꙮ': (100, -1)}
        result = get_pinyin_seq_for_words(words)
        self.assertNotIn('ꙮ', result)

    def test_extra_encode_uses_main_used_codes(self):
        extra_entries = [
            {'word': 'X', 'toneless_seq': ['x'], 'full_code': 'ab',
             'freq': (100, -1), 'aux_seqs': [['f']]},
        ]
        result, used = incremental_encode(extra_entries, initial_used_codes={'ab'})
        self.assertEqual(_find_code(result, 'X', ['x']), 'abf')

    def test_extra_words_dedup_against_main(self):
        main_entries = build_entries({'你': ['nǐ']}, {}, {}, {})
        main_words = set(e['word'] for e in main_entries)

        extra_words = {'你': (100, -1), '世界': (50, -1), '𠀀': (10, -1)}
        filtered = {w: f for w, f in extra_words.items() if w not in main_words}

        self.assertNotIn('你', filtered)
        self.assertIn('世界', filtered)
        self.assertIn('𠀀', filtered)

    def test_extra_words_use_only_standard_pinyin(self):
        test_char = '括'
        saved_std = kCharacterCodes.get(test_char)
        saved_nonstd = kCharacterCodesNonstandard.get(test_char)
        try:
            if test_char in kCharacterCodes:
                del kCharacterCodes[test_char]
            kCharacterCodesNonstandard[test_char] = ['guā']

            words = {test_char: (100, -1)}
            result = get_pinyin_seq_for_words(words)
            self.assertNotIn(test_char, result)
        finally:
            if saved_std is not None:
                kCharacterCodes[test_char] = saved_std
            if saved_nonstd is not None:
                kCharacterCodesNonstandard[test_char] = saved_nonstd
            else:
                kCharacterCodesNonstandard.pop(test_char, None)


class TestDeduplication(unittest.TestCase):
    def test_same_toneless_same_aux_dedup(self):
        """
        同一字詞的多個有調讀音，若無調形式相同，視為同一條目，頻率相加。
        每個 (word, toneless_seq) 對應一個 entry。
        """
        char_codes = {'你': ['nǐ', 'ni']}
        entries = build_entries(char_codes, {}, {}, {})
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['word'], '你')
        self.assertEqual(entries[0]['toneless_seq'], ['ni'])

    def test_different_words_not_dedup(self):
        char_codes = {'你': ['nǐ'], '好': ['hǎo']}
        entries = build_entries(char_codes, {}, {}, {})
        self.assertEqual(len(entries), 2)

    def test_dedup_sums_freq(self):
        """
        频率按 (word, toneless_seq) 累加，与辅助码序列无关。
        """
        char_codes = {'你': ['nǐ', 'ni']}
        freq_dict = {'你': {'ni': (500, -1)}}
        entries = build_entries(char_codes, {}, {}, freq_dict)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['freq'][0], 1000)
        self.assertEqual(entries[0]['freq'][1], -1)

    def test_dedup_sums_freq_different_sources(self):
        char_codes = {'你': ['nǐ']}
        char_nonstandard = {'你': ['ni']}
        freq_dict = {'你': {'ni': (300, -1)}}
        entries = build_entries(char_codes, char_nonstandard, {}, freq_dict)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['freq'][0], 600)


if __name__ == "__main__":
    main()
