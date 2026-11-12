# -*- coding: utf-8 -*-

import re
import sys
import argparse

# 蔘 is kept in ginseng / sea-cucumber / herb names, e.g. 人蔘, 海蔘, 人蔘丸,
# 蔘茸, 蔘苓白朮散.  Everywhere else (蔘加, 蔘與, 蔘數, 蔘考, ...) it is a
# conversion error for 參.
#
# A word is treated as ginseng when 蔘 is
#   * preceded by a ginseng name ending (kShenTails), or
#   * followed by a herb / product character (kShenHeads), or
#   * part of 蔘三七,
# unless the ginseng name is directly followed by a character that turns the
# word into an ordinary 參 word (kShenBlockers), e.g. 工人蔘與, 上海蔘考.
#
# Multi-character words only; single-character 蔘 entries are left alone.

kShenTails = set("""
人
海
黨
沙
洋
丹
玄
苦
刺
血
蕭
山
野
紅
白
元
廣
長
直
遼
柱
園
塘
林
鮮
川
土
糖
高麗
花旗
太子
西洋
東洋
上黨
川黨
吉林
朝鮮
韓國
進口
林下
百濟
太白
長白
""".split())

kShenHeads = set("""
茸
芪
苓
附
麥
蘇
術
桂
杞
耆
赭
茯
蛤
棗
梅
竹
柏
藿
蟾
鎖
鞭
芝
花
鹿
味
七
須
蘆
葉
莖
雞
歸
丹
朮
芎
芍
龍
松
蓮
貝
陽
坤
仙
菊
連
果
茶
片
粉
精
湯
酒
膏
汁
肽
素
屬
科
根
條
菜
王
粥
羹
丸
寶
娃
皇
苗
農
類
枸
玉
車
橘
杏
烏
防
麻
杜
續
桑
秦
荊
羌
獨
細
蒼
厚
枳
砂
蔻
萊
蒲
葶
枇
瓜
膽
旋
磁
硃
琥
酸
夜
珍
牡
鉤
蜈
僵
麝
熊
羚
犀
龜
鱉
阿
當
赤
何
旱
扁
芡
薏
飴
蜂
蓯
蓉
淫
狗
菟
黃
""".split())

kShenBlockers = set("""
加
與
賽
選
戰
政
議
謀
軍
事
贊
拜
預
見
觀
展
考
照
數
差
閱
訪
評
演
訓
拍
股
驗
謁
劾
革
假
圖
辰
商
宿
橫
回
悟
禪
透
酌
本
領
讀
省
看
請
詳
訂
校
試
審
寥
伍
錯
綜
互
雜
院
暮
辭
""".split())

kNonGinsengPrefixes = set("""
內
總
自
曾
行
""".split())

def is_ginseng_word(word):
    n = len(word)
    if '蔘三七' in word:
        return True
    for i, c in enumerate(word):
        if c != '蔘':
            continue
        if i + 1 < n and word[i + 1] in kShenHeads:
            if i == 0 or word[i - 1] not in kNonGinsengPrefixes:
                return True
        if i > 0:
            for tail in kShenTails:
                if word.endswith(tail, 0, i):
                    if i + 1 == n or word[i + 1] not in kShenBlockers:
                        return True
                    break
    return False

def fix_shen_pattern(text):
    if '蔘' in text:
        if '\t' in text:
            word = text.split('\t', 1)[0]
        elif ':' in text:
            word = text.split(':', 1)[0]
        else:
            word = text
        word = word.strip()
        if '蔘' in word and len(word) >= 2 and not is_ginseng_word(word):
            text = re.sub(r'蔘', '參', text)
    return text

# Main processing
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='input file')
    parser.add_argument('output', help='output file')
    args = parser.parse_args()

    kActions = [fix_shen_pattern]

    with open(args.input, 'rb') as fin, open(args.output, 'wb') as fout:
        for line in fin:
            line = line.decode('utf-8')
            for action in kActions:
                line = action(line)
            fout.write(line.encode('utf-8'))
    print('Done')
