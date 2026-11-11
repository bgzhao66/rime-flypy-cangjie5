#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
把 userdb.txt 转换为 RIME 全拼词库格式（无文件头）。

支援同时输入多个 userdb.txt，所有条目合并处理：
相同 (word, py seq) 的权重会跨档案累加。

输入格式范例：
    zvee    罪恶    c=6 d=8.16794e-39 t=173161

输出格式：
    罪恶\tzui e\t6

规则：
- 只处理开头符合 ^[a-z] 的行，其余（空行、# 注释、空格开头等）一律忽略。
- 第一列为小鹤双拼编码（可能附带辅助码）。
- 第二列为词条，c= 为使用次数（作为 RIME 权重）。
- 若 c < 0，输出告警并忽略该条目。
- 若词长为 n，编码长度至少为 2n：正常解码，多余字符视为辅助码忽略。
- 若编码长度为 2n-1：前 n-1 个字正常解码；
  最后一个字优先采用普通话标准读音（若其声母与 code[-1] 相符），
  否则从所有异读音中筛选；若无法唯一确定，输出告警并忽略该行。
- 拼音获取优先采用普通话标准读音（pypinyin 的 heteronym=False）。
- 输出时，若 (word, py seq) 完全相同，则合并为一条，权重取 c 之和。
"""

import re
import sys
import argparse
from pypinyin import lazy_pinyin, pinyin, Style


# ---------------------------------------------------------------------------
# 小鹤双拼音节表（直接以字串形式嵌入，开机时解析为 dict）
# ---------------------------------------------------------------------------

XIAOHE_SYLLABLE_TABLE_RAW = r'''
"aa" : "a",
"ai" : "ai",
"an" : "an",
"ah" : "ang",
"ao" : "ao",
"ba" : "ba",
"bd" : "bai",
"bj" : "ban",
"bh" : "bang",
"bc" : "bao",
"bw" : "bei",
"bf" : "ben",
"bg" : "beng",
"bi" : "bi",
"bm" : "bian",
"bn" : "biao",
"bp" : "bie",
"bb" : "bin",
"bk" : "bing",
"bo" : "bo",
"bu" : "bu",
"ca" : "ca",
"cd" : "cai",
"cj" : "can",
"ch" : "cang",
"cc" : "cao",
"ce" : "ce",
"cf" : "cen",
"cg" : "ceng",
"ia" : "cha",
"id" : "chai",
"ij" : "chan",
"ih" : "chang",
"ic" : "chao",
"ie" : "che",
"if" : "chen",
"ig" : "cheng",
"ii" : "chi",
"is" : "chong",
"iz" : "chou",
"iu" : "chu",
"ix" : "chua",
"ik" : "chuai",
"ir" : "chuan",
"il" : "chuang",
"iv" : "chui",
"iy" : "chun",
"io" : "chuo",
"ci" : "ci",
"cs" : "cong",
"cz" : "cou",
"cu" : "cu",
"cr" : "cuan",
"cv" : "cui",
"cy" : "cun",
"co" : "cuo",
"da" : "da",
"dd" : "dai",
"dj" : "dan",
"dh" : "dang",
"dc" : "dao",
"de" : "de",
"dw" : "dei",
"df" : "den",
"dg" : "deng",
"di" : "di",
"dm" : "dian",
"dl" : "diang",
"dn" : "diao",
"dp" : "die",
"dk" : "ding",
"dq" : "diu",
"ds" : "dong",
"dz" : "dou",
"du" : "du",
"dr" : "duan",
"dv" : "dui",
"dy" : "dun",
"do" : "duo",
"ee" : "e",
"ei" : "ei",
"en" : "en",
"er" : "er",
"fa" : "fa",
"fj" : "fan",
"fh" : "fang",
"fw" : "fei",
"ff" : "fen",
"fg" : "feng",
"fo" : "fo",
"fz" : "fou",
"fu" : "fu",
"ga" : "ga",
"gd" : "gai",
"gj" : "gan",
"gh" : "gang",
"gc" : "gao",
"ge" : "ge",
"gw" : "gei",
"gf" : "gen",
"gg" : "geng",
"gs" : "gong",
"gz" : "gou",
"gu" : "gu",
"gx" : "gua",
"gk" : "guai",
"gr" : "guan",
"gl" : "guang",
"gv" : "gui",
"gy" : "gun",
"go" : "guo",
"ha" : "ha",
"hd" : "hai",
"hj" : "han",
"hh" : "hang",
"hc" : "hao",
"he" : "he",
"hw" : "hei",
"hf" : "hen",
"hg" : "heng",
"hs" : "hong",
"hz" : "hou",
"hu" : "hu",
"hx" : "hua",
"hk" : "huai",
"hr" : "huan",
"hl" : "huang",
"hv" : "hui",
"hy" : "hun",
"ho" : "huo",
"ji" : "ji",
"jx" : "jia",
"jm" : "jian",
"jl" : "jiang",
"jn" : "jiao",
"jp" : "jie",
"jb" : "jin",
"jk" : "jing",
"js" : "jiong",
"jq" : "jiu",
"ju" : "ju",
"jr" : "juan",
"jt" : "jue",
"jy" : "jun",
"ka" : "ka",
"kd" : "kai",
"kj" : "kan",
"kh" : "kang",
"kc" : "kao",
"ke" : "ke",
"kw" : "kei",
"kf" : "ken",
"kg" : "keng",
"ks" : "kong",
"kz" : "kou",
"ku" : "ku",
"kx" : "kua",
"kk" : "kuai",
"kr" : "kuan",
"kl" : "kuang",
"kv" : "kui",
"ky" : "kun",
"ko" : "kuo",
"la" : "la",
"ld" : "lai",
"lj" : "lan",
"lh" : "lang",
"lc" : "lao",
"le" : "le",
"lw" : "lei",
"lg" : "leng",
"li" : "li",
"lx" : "lia",
"lm" : "lian",
"ll" : "liang",
"ln" : "liao",
"lp" : "lie",
"lb" : "lin",
"lk" : "ling",
"lq" : "liu",
"lo" : "lo",
"ls" : "long",
"lz" : "lou",
"lu" : "lu",
"lr" : "luan",
"ly" : "lun",
"lo" : "luo",
"lv" : "lü",
"lt" : "lüe",
"ma" : "ma",
"md" : "mai",
"mj" : "man",
"mh" : "mang",
"mc" : "mao",
"me" : "me",
"mw" : "mei",
"mf" : "men",
"mg" : "meng",
"mi" : "mi",
"mm" : "mian",
"mn" : "miao",
"mp" : "mie",
"mb" : "min",
"mk" : "ming",
"mq" : "miu",
"mo" : "mo",
"mz" : "mou",
"mu" : "mu",
"na" : "na",
"nd" : "nai",
"nj" : "nan",
"nh" : "nang",
"nc" : "nao",
"ne" : "ne",
"nw" : "nei",
"nf" : "nen",
"ng" : "neng",
"ni" : "ni",
"nx" : "nia",
"nm" : "nian",
"nl" : "niang",
"nn" : "niao",
"np" : "nie",
"nb" : "nin",
"nk" : "ning",
"nq" : "niu",
"ns" : "nong",
"nz" : "nou",
"nu" : "nu",
"nr" : "nuan",
"ny" : "nun",
"no" : "nuo",
"nv" : "nü",
"nt" : "nüe",
"oo" : "o",
"ou" : "ou",
"pa" : "pa",
"pd" : "pai",
"pj" : "pan",
"ph" : "pang",
"pc" : "pao",
"pw" : "pei",
"pf" : "pen",
"pg" : "peng",
"pi" : "pi",
"pm" : "pian",
"pn" : "piao",
"pp" : "pie",
"pb" : "pin",
"pk" : "ping",
"po" : "po",
"pz" : "pou",
"pu" : "pu",
"qi" : "qi",
"qx" : "qia",
"qm" : "qian",
"ql" : "qiang",
"qn" : "qiao",
"qp" : "qie",
"qb" : "qin",
"qk" : "qing",
"qs" : "qiong",
"qq" : "qiu",
"qu" : "qu",
"qr" : "quan",
"qt" : "que",
"qy" : "qun",
"rj" : "ran",
"rh" : "rang",
"rc" : "rao",
"re" : "re",
"rf" : "ren",
"rg" : "reng",
"ri" : "ri",
"rs" : "rong",
"rz" : "rou",
"ru" : "ru",
"rr" : "ruan",
"rv" : "rui",
"ry" : "run",
"ro" : "ruo",
"sa" : "sa",
"sd" : "sai",
"sj" : "san",
"sh" : "sang",
"sc" : "sao",
"se" : "se",
"sw" : "sei",
"sf" : "sen",
"sg" : "seng",
"ua" : "sha",
"ud" : "shai",
"uj" : "shan",
"uh" : "shang",
"uc" : "shao",
"ue" : "she",
"uw" : "shei",
"uf" : "shen",
"ug" : "sheng",
"ui" : "shi",
"us" : "shong",
"uz" : "shou",
"uu" : "shu",
"ux" : "shua",
"uk" : "shuai",
"ur" : "shuan",
"ul" : "shuang",
"uv" : "shui",
"uy" : "shun",
"uo" : "shuo",
"si" : "si",
"ss" : "song",
"sz" : "sou",
"su" : "su",
"sr" : "suan",
"sv" : "sui",
"sy" : "sun",
"so" : "suo",
"ta" : "ta",
"td" : "tai",
"tj" : "tan",
"th" : "tang",
"tc" : "tao",
"te" : "te",
"tg" : "teng",
"ti" : "ti",
"tm" : "tian",
"tn" : "tiao",
"tp" : "tie",
"tk" : "ting",
"ts" : "tong",
"tz" : "tou",
"tu" : "tu",
"tr" : "tuan",
"tv" : "tui",
"ty" : "tun",
"to" : "tuo",
"wa" : "wa",
"wd" : "wai",
"wj" : "wan",
"wh" : "wang",
"ww" : "wei",
"wf" : "wen",
"wg" : "weng",
"wo" : "wo",
"wu" : "wu",
"xi" : "xi",
"xx" : "xia",
"xm" : "xian",
"xl" : "xiang",
"xn" : "xiao",
"xp" : "xie",
"xb" : "xin",
"xk" : "xing",
"xs" : "xiong",
"xq" : "xiu",
"xu" : "xu",
"xr" : "xuan",
"xt" : "xue",
"xy" : "xun",
"ya" : "ya",
"yj" : "yan",
"yh" : "yang",
"yc" : "yao",
"ye" : "ye",
"yi" : "yi",
"yb" : "yin",
"yk" : "ying",
"ys" : "yong",
"yz" : "you",
"yu" : "yu",
"yr" : "yuan",
"yt" : "yue",
"yy" : "yun",
"za" : "za",
"zd" : "zai",
"zj" : "zan",
"zh" : "zang",
"zc" : "zao",
"ze" : "ze",
"zw" : "zei",
"zf" : "zen",
"zg" : "zeng",
"va" : "zha",
"vd" : "zhai",
"vj" : "zhan",
"vh" : "zhang",
"vc" : "zhao",
"ve" : "zhe",
"vw" : "zhei",
"vf" : "zhen",
"vg" : "zheng",
"vi" : "zhi",
"vs" : "zhong",
"vz" : "zhou",
"vu" : "zhu",
"vx" : "zhua",
"vk" : "zhuai",
"vr" : "zhuan",
"vl" : "zhuang",
"vv" : "zhui",
"vy" : "zhun",
"vo" : "zhuo",
"zi" : "zi",
"zs" : "zong",
"zz" : "zou",
"zu" : "zu",
"zr" : "zuan",
"zv" : "zui",
"zy" : "zun",
"zo" : "zuo",
'''


def _parse_syllable_table(raw: str) -> dict:
    """把 '"code" : "pinyin",' 形式的字串解析为 dict。

    若同一 code 出现多次，后者覆盖前者（例如 "lo" 最终为 "luo"）。
    """
    table = {}
    for m in re.finditer(r'"([a-z]+)"\s*:\s*"([^"]+)"', raw):
        table[m.group(1)] = m.group(2)
    return table


XIAOHE_SYLLABLE_TABLE = _parse_syllable_table(XIAOHE_SYLLABLE_TABLE_RAW)


# ---------------------------------------------------------------------------
# 声母工具（仅用于 2n-1 情况的单字母声母匹配）
# ---------------------------------------------------------------------------

NORMAL_INITIALS = set('bpmfdtnlgkhjqxrzcsyw')
SPECIAL_INITIALS = {'v': 'zh', 'i': 'ch', 'u': 'sh'}

# 允许 c 为负数
LINE_RE = re.compile(r'^(\S+)\s+(\S+)\s+c=(-?\d+)\s+d=(\S+)\s+t=(\d+)\s*$')


def normalize_pinyin(p: str) -> str:
    """把 ü 统一替换为 v，方便比较。"""
    return p.replace('ü', 'v')


def get_initial(p: str) -> str:
    """取得拼音的声母，零声母返回空字串。"""
    p = normalize_pinyin(p)
    if p.startswith(('zh', 'ch', 'sh')):
        return p[:2]
    if p and p[0] in NORMAL_INITIALS:
        return p[0]
    return ''


def code_to_initial(code_char: str) -> str:
    """把小鹤双拼的单一字母映射为实际声母，零声母返回空字串。"""
    if code_char == 'v':
        return 'zh'
    if code_char == 'i':
        return 'ch'
    if code_char == 'u':
        return 'sh'
    if code_char in NORMAL_INITIALS:
        return code_char
    return ''  # 零声母


# ---------------------------------------------------------------------------
# 单音节解码（直接查表）
# ---------------------------------------------------------------------------

def decode_syllable(pair: str) -> list:
    """把一组 2 字符的小鹤双拼音节解码为候选全拼列表。

    返回的拼音已把 ü 正规化为 v。
    若输入不是 2 字符或表中无此码，返回空列表。
    """
    if len(pair) != 2:
        return []
    pinyin = XIAOHE_SYLLABLE_TABLE.get(pair)
    if pinyin is None:
        return []
    return [normalize_pinyin(pinyin)]


# ---------------------------------------------------------------------------
# 汉字拼音查询
# ---------------------------------------------------------------------------

def get_standard_pinyin(char: str) -> str:
    """取得单一汉字的普通话标准读音。"""
    result = lazy_pinyin(char, style=Style.NORMAL)
    return normalize_pinyin(result[0]) if result else ''


def get_all_pinyin(char: str) -> list:
    """取得单一汉字的所有读音（去重、正规化）。"""
    cands = pinyin(char, heteronym=True, style=Style.NORMAL)[0]
    seen = []
    for p in cands:
        p = normalize_pinyin(p)
        if p not in seen:
            seen.append(p)
    return seen


# ---------------------------------------------------------------------------
# 多音节解码
# ---------------------------------------------------------------------------

def decode_code_part(code_part: str, word_part: str):
    """解码完整的双拼编码部分（每个字两个字母），返回拼音列表。

    每个音节直接查表，结果唯一。
    注意：只使用 code_part 的前 2n 个字符，多余字符忽略。
    """
    n = len(word_part)
    if len(code_part) < 2 * n:
        return None
    code_part = code_part[:2 * n]
    result = []
    for i in range(n):
        pair = code_part[2 * i:2 * i + 2]
        cands = decode_syllable(pair)
        if not cands:
            return None
        result.append(cands[0])
    return result


# ---------------------------------------------------------------------------
# 转换主流程
# ---------------------------------------------------------------------------

def _iter_lines(input_paths):
    """依次读取多个输入档案，逐行 yield (path, raw_line)。"""
    for path in input_paths:
        with open(path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                yield path, line.rstrip('\n')


def convert(input_paths, output_path: str) -> None:
    """把一个或多个 userdb.txt 转换为 RIME 全拼词库格式。

    input_paths 可以是单一字串或字串序列。
    多个档案的条目会合并，相同 (word, pinyin) 的 c 累加。
    """
    if isinstance(input_paths, str):
        input_paths = [input_paths]

    # 使用 dict 保持插入顺序，并对相同 (word, py seq) 累加 c
    merged = {}  # key: (word, pinyin_str) -> c

    for path, raw in _iter_lines(input_paths):
        # 只处理开头符合 ^[a-z] 的行
        if not re.match(r'^[a-z]', raw):
            continue

        m = LINE_RE.match(raw)
        if not m:
            print(f'[警告] {path}: 无法解析行：{raw}', file=sys.stderr)
            continue

        code, word, c_str, d, t = m.groups()
        c = int(c_str)

        if c < 0:
            print(
                f'[警告] {path}: c 为负数（c={c}），忽略条目：{raw}',
                file=sys.stderr,
            )
            continue

        word_len = len(word)
        code_len = len(code)

        pinyin_list = []

        if code_len >= 2 * word_len:
            decoded = decode_code_part(code, word)
            if decoded is None:
                print(f'[警告] {path}: 无法解码：{raw}', file=sys.stderr)
                continue
            pinyin_list = decoded

        elif code_len == 2 * word_len - 1:
            if word_len > 1:
                front_word = word[:-1]
                front_code = code[:2 * (word_len - 1)]
                front_pinyin = decode_code_part(front_code, front_word)
                if front_pinyin is None:
                    print(
                        f'[警告] {path}: 无法解码前部分：{raw}',
                        file=sys.stderr,
                    )
                    continue
                pinyin_list.extend(front_pinyin)

            last_char = word[-1]
            last_code_char = code[-1]
            target_initial = code_to_initial(last_code_char)

            std_pinyin = get_standard_pinyin(last_char)
            if std_pinyin and get_initial(std_pinyin) == target_initial:
                pinyin_list.append(std_pinyin)
            else:
                all_cands = get_all_pinyin(last_char)
                matched = [p for p in all_cands if get_initial(p) == target_initial]
                if len(matched) == 1:
                    pinyin_list.append(matched[0])
                elif len(matched) > 1:
                    print(
                        f'[警告] {path}: 最后一个字「{last_char}」有多个拼音'
                        f'匹配声母「{target_initial}」：{matched}，忽略行：{raw}',
                        file=sys.stderr,
                    )
                    continue
                else:
                    print(
                        f'[警告] {path}: 最后一个字「{last_char}」没有拼音'
                        f'匹配声母「{target_initial}」，忽略行：{raw}',
                        file=sys.stderr,
                    )
                    continue

        else:
            print(
                f'[警告] {path}: 编码长度 {code_len} 不符合词长 {word_len} 的'
                f'预期，忽略行：{raw}',
                file=sys.stderr,
            )
            continue

        pinyin_str = ' '.join(pinyin_list)
        key = (word, pinyin_str)
        merged[key] = merged.get(key, 0) + c

    out = [f'{word}\t{pinyin_str}\t{c}' for (word, pinyin_str), c in merged.items()]

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')


# ---------------------------------------------------------------------------
# 内建自测：以小鹤双拼音节表作为测试用例
# ---------------------------------------------------------------------------

def _run_selftest() -> int:
    """只测试 decode_syllable 对标准小鹤双拼音节的还原。"""
    import unittest

    class TestDecodeSyllable(unittest.TestCase):

        def test_all_syllables(self):
            """遍历完整映射表，验证每个双拼码都能还原为对应全拼。"""
            for code, expected in XIAOHE_SYLLABLE_TABLE.items():
                with self.subTest(code=code, expected=expected):
                    self.assertEqual(
                        decode_syllable(code),
                        [normalize_pinyin(expected)],
                    )

        def test_table_size(self):
            """映射表应有数百个音节。"""
            self.assertGreater(len(XIAOHE_SYLLABLE_TABLE), 300)

        def test_umlaut_normalized_to_v(self):
            """ü 系列应正规化为 v。"""
            self.assertEqual(decode_syllable("lv"), ["lv"])
            self.assertEqual(decode_syllable("nv"), ["nv"])
            self.assertEqual(decode_syllable("lt"), ["lve"])
            self.assertEqual(decode_syllable("nt"), ["nve"])

        def test_duplicate_code_last_wins(self):
            """重复码 'lo' 后者覆盖前者，最终为 'luo'。"""
            self.assertEqual(decode_syllable("lo"), ["luo"])

        def test_invalid_length(self):
            self.assertEqual(decode_syllable(""), [])
            self.assertEqual(decode_syllable("a"), [])
            self.assertEqual(decode_syllable("abc"), [])
            self.assertEqual(decode_syllable("abcd"), [])

        def test_unknown_code(self):
            self.assertEqual(decode_syllable("z?"), [])
            self.assertEqual(decode_syllable("z1"), [])
            self.assertEqual(decode_syllable("zZ"), [])
            self.assertEqual(decode_syllable("??"), [])

    suite = unittest.TestLoader().loadTestsFromTestCase(TestDecodeSyllable)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='把 userdb.txt 转换为 RIME 全拼词库格式（无文件头）'
    )
    parser.add_argument(
        'inputs',
        nargs='*',
        help='一个或多个输入档案（userdb.txt）',
    )
    parser.add_argument(
        '-o', '--output',
        default='pinyin_userdb.dict.txt',
        help='输出档案，预设为 pinyin.dict.yaml',
    )
    parser.add_argument(
        '--selftest',
        action='store_true',
        help='只执行内建的小鹤双拼音节解码自测，不进行转换',
    )
    args = parser.parse_args()

    if args.selftest:
        sys.exit(_run_selftest())

    if not args.inputs:
        parser.error('未提供输入档案（或使用 --selftest）')

    convert(args.inputs, args.output)


if __name__ == '__main__':
    main()
