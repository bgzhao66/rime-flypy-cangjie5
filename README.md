# RIME flypy-cangjie5-simp -- 「双拼逆仓」输入法方案

## 说明
<code>flypy-cangjie5-simp</code> 是一个基于小鹤双拼和仓颉五代首尾码逆序的音形输入法方案，设计目标是让用户能够简单、快速、准确地统一输入汉语任意语言风格、各种文体的数百万字词，包括但不限于现代文、古诗文、以及文言文等等。

本方案的核心原则是**确定性编码**：在码表覆盖范围内，每一个合法编码串都唯一对应一个词条，熟练后可以完全盲打。

## 编码规则

### 主码
采用**小鹤双拼**，每字两码，逐字拼接。

### 辅助码：仓颉码「Last-First-Second」规则
所有词按词频由高到低分配**唯一编码**：主码未占用则直接使用；被占用时，依**仓颉码「Last-First-Second」规则**在其后逐次追加辅助码，直到获得未被占用的编码为止；辅助码用完后追加 `a, b, c, ...`。

| 字词长度 | 辅助码顺序（Last → First → Second） |
|---|---|
| 单字 | 尾码 → 首码 → 次码 |
| 双字词 | 尾字尾码 → 首字首码 → 尾字首码 |
| 三字词 | 尾字尾码 → 首字首码 → 次字首码 |
| 四字及以上 | 无辅助码，直接追加字母 |

### 简码
仅 1~3 字词有简码，长度 = 主码长度 - 1，按词频分配，不与已分配编码冲突。

## 学习资料
双拼和**仓颉速成**均有成熟的学习资料。仓颉速成码，实际为仓颉码取首尾。

- 双拼：[双拼练习（小鹤双拼）](https://api.ihint.me/shuang/);
- 仓颉：[五色仓颉（三代）](https://www.xn--0vqu8au0tro7d.com/)，[仓颉五代手册](https://zh.wikibooks.org/w/index.php?title=%E5%80%89%E9%A0%A1%E8%BC%B8%E5%85%A5%E6%B3%95&variant=zh)，[仓颉之友](https://www.chinesecj.com/)，[仓颉字根表（五代兼三代）](https://www.chinesecj.com/forum/data/attachment/forum/202111/24/154815fwe23wu3npzz172k.png)，[仓颉表（五代兼三代）](https://www.hkcards.com/img/cj-radical/cj-table-kel.png)，[仓颉网上输入法（五代）](https://www.chinesecj.com/ime/cj5.php);
- 字典：[汉语字典（含五代仓颉码）](https://www.hanyuguoxue.com/zidian/)。

## 安装
此输入法方案需要 [RIME | 中州韵输入法引擎](https://rime.im/)

default.custom.yaml 文件为用户重要配置文件，其中 schema_list 字段后是所有可选配方，可自行增删（行首用“#”号注释表示不引入）。

### 输入法码表
```
flypy_cangjie5_simp.schema.yaml
flypy_cangjie5_simp*.dict.yaml
```

### 通用方式
[安装 rime](https://rime.im/) 后，把码表复制到 Rime 用户设定目录，然后重新部署。
 部署位置：
##### Windows 10+
```
    %APPDATA%\Rime
```
##### Mac OSX
```
    ~/Library/Rime
```
##### Linux (部署后最好重启一次)
###### ibus-rime:
```
    ~/.config/ibus/rime
```
###### fcitx-rime:
```
    ~/.config/fcitx/rime
```
###### fcitx5-rime:
```
    ~/.local/share/fcitx5/rime
```

### 字体
为显示 CJK 扩展区数万汉字，可下载并安装 [HanaMin|花园明朝](https://glyphwiki.org/hanazono/hanazono-20170904.zip) 字体库。
