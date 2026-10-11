# RIME flypy-cangjie5 -- 「雙拼逆倉」輸入法方案

## 說明
<code>flypy-cangjie5</code> 是一個基於小鶴雙拼和倉頡五代首尾碼逆序的音形輸入法方案，設計目標是讓用戶能夠簡單、快速、準確地統一輸入漢語任意語言風格、各種文體的數百萬字詞，包括但不限於現代文、古詩文、和文言文等等。

本方案的核心原則是**確定性編碼**：在碼表覆蓋範圍內，每一個合法編碼串都唯一對應一個詞條，熟練後可以完全盲打。

## 編碼規則

### 主碼
採用**小鶴雙拼**，每字兩碼，逐字拼接。  

### 輔助碼：倉頡碼「Last-First-Second」規則
所有詞按詞頻由高到低分配**唯一編碼**：主碼未佔用則直接使用；被佔用時，依**倉頡碼「Last-First-Second」規則**在其後逐次追加輔助碼，直到獲得未被佔用的編碼為止；輔助碼用完後追加 `a, b, c, ...`。

| 字詞長度 | 輔助碼順序（Last → First → Second） |
|---|---|
| 單字 | 尾碼 → 首碼 → 次碼 |
| 雙字詞 | 尾字尾碼 → 首字首碼 → 尾字首碼 |
| 三字詞 | 尾字尾碼 → 首字首碼 → 次字首碼 |
| 四字及以上 | 無輔助碼，直接追加字母 |

### 簡碼
僅 1~3 字詞有簡碼，長度 = 主碼長度 - 1，按詞頻分配，不與主碼或已分配簡碼衝突。

## 學習資料
雙拼和**倉頡速成**均有成熟的學習資料。倉頡速成碼，實際為倉頡碼取首尾。

- 雙拼：[雙拼練習（小鶴雙拼）](https://api.ihint.me/shuang/);
- 倉頡：[五色倉頡（三代）](https://www.xn--0vqu8au0tro7d.com/)，[倉頡五代手冊](https://zh.wikibooks.org/w/index.php?title=%E5%80%89%E9%A0%A1%E8%BC%B8%E5%85%A5%E6%B3%95&variant=zh)，[倉頡之友](https://www.chinesecj.com/)，[倉頡字根表（五代兼三代）](https://www.chinesecj.com/forum/data/attachment/forum/202111/24/154815fwe23wu3npzz172k.png)，[倉頡表（五代兼三代）](https://www.hkcards.com/img/cj-radical/cj-table-kel.png)，[倉頡網上輸入法（五代）](https://www.chinesecj.com/ime/cj5.php);
- 字典：[漢語字典（含五代倉頡碼）](https://www.hanyuguoxue.com/zidian/)。

## 安裝
此輸入法方案需要 [RIME | 中州韻輸入法引擎](https://rime.im/)

default.custom.yaml 文件為用戶重要配置文件，其中 schema_list 字段後是所有可選配方，可自行增刪（行首用“#”號註釋表示不引入）。

### 輸入法碼表
```
flypy_cangjie5.schema.yaml
flypy_cangjie5*.dict.yaml
```

### 通用方式
[安裝 rime](https://rime.im/) 後，把碼表複製到 Rime 用戶設定目錄，然後重新部署。
 部署位置：
##### Windows 10+
```
    %APPDATA%\Rime
```
##### Mac OSX
```
    ~/Library/Rime
```
##### Linux (部署後最好重啟一次)
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

### 字體
為顯示 CJK 擴展區數萬漢字，可下載並安裝 [HanaMin|花園明朝](https://glyphwiki.org/hanazono/hanazono-20170904.zip) 字體庫。
