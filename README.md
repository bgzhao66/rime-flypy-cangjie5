# RIME flypy-cangjie5 —「雙拼逆倉」輸入法方案

## 方案簡介

`flypy-cangjie5`（雙拼逆倉）是一套基於**小鶴雙拼**與**倉頡五代逆序輔助碼**的音形輸入法方案，旨在以簡單、快速、準確且可控的方式，統一輸入現代漢語、古詩詞及文言文等百萬字詞。

### 設計核心與特色

- **確定性編碼（盲打體驗）**：每個詞條皆有唯一指定編碼，無需依賴候選詞排序消歧。熟練後可直接完整輸入，減少選詞對思路的干擾。
    
- **音形結合**：以小鶴雙拼為主碼，倉頡五代字形為輔助碼。僅在主碼衝突時追加形碼，高頻詞優先取得短碼，兼顧效率與學習成本。
    
- **雙拼輸入，全拼顯示**：保留雙拼的輸入效率，同時呈現直觀易讀的全拼結果，有助於閱讀、校對與理解。
    
- **高擴展性**：不以限定詞庫或特定語言風格為前提，透過可擴展的編碼與消歧機制，兼顧日常輸入與低頻字、古籍用語的精準定位。

## 編碼規則

### 1. 主碼：小鶴雙拼

- **單字**：使用兩個按鍵表示其拼音。
    
- **詞語**：將各字雙拼碼依次拼接。
    
若主碼已能唯一定位詞條，則無須輸入形碼。

### 2. 輔助碼：倉頡五代逆序

當主碼發生編碼衝突時，依照 **「Last（尾碼）→ First（首碼）→ Second（次碼）」** 次序逐步追加倉頡輔助碼消歧：

|**詞條長度**|**輔助碼追加順序**|**衝突後續處理**|
|---|---|---|
|**單字**|尾碼 → 首碼 → 次碼|倉頡碼不足時，追加未使用的字母序號|
|**雙字詞**|末字尾碼 → 首字首碼 → 次字首碼|倉頡碼不足時，追加未使用的字母序號|
|**三字詞**|末字尾碼 → 首字首碼 → 次字首碼|倉頡碼不足時，追加未使用的字母序號|
|**四字及以上**|**不追加倉頡輔助碼**|直接追加未使用的字母序號（避免長詞過長）|

### 3. 唯一編碼與詞頻分配

- 所有詞條依**詞頻由高到低**進行編碼分配。
    
- 優先分配主碼；若已被佔用，則按輔助碼規則逐步追加，直到取得未使用的編碼（高頻詞短碼，低頻詞長碼）。

### 4. 簡碼

- **僅設於一至三字詞**。
    
- 長度比主碼少一碼，依詞頻分配並避開既有編碼，用以進一步縮短高頻詞輸入長度。

## 學習與輔助資源

_倉頡速成碼（取首尾碼）可作為輔助碼學習的入門途徑，但需注意本方案採用特定的逆序取碼規則。_

### 雙拼練習

- [雙拼練習（小鶴雙拼）](https://api.ihint.me/shuang/)
    
### 倉頡資源

- [五色倉頡（三代）](https://www.xn--0vqu8au0tro7d.com/)
	
- [倉頡卡片（五代兼三代）](https://www.hkcards.com/)
	
- [倉頡五代手冊（維基教科書）](https://zh.wikibooks.org/w/index.php?title=%E5%80%89%E9%A0%A1%E8%BC%B8%E5%85%A5%E6%B3%95&variant=zh)
	
- [倉頡之友](https://www.chinesecj.com/)
	
- [倉頡字根表（五代兼三代）](https://www.chinesecj.com/forum/data/attachment/forum/202111/24/154815fwe23wu3npzz172k.png)
	
- [倉頡表（五代兼三代）](https://www.hkcards.com/img/cj-radical/cj-table-kel.png)
	
- [倉頡網上輸入法（五代）](https://www.chinesecj.com/ime/cj5.php)

### 字典

- [漢語字典（含五代倉頡碼）](https://www.hanyuguoxue.com/zidian/)

### 字體
- **CJK 擴展區字體**：可安裝 [HanaMin 花園明朝字體](https://glyphwiki.org/hanazono/hanazono-20170904.zip) 以完整顯示罕用字形（字庫支援度取決於安裝版本；可否輸入仍視碼表收錄而定）。

## 安裝步驟

需先安裝 [RIME 中州韻輸入法引擎](https://rime.im/)。用戶配置目錄記為 `<RIME>`：

  

- **Windows 10+**: `%APPDATA%\Rime`
    
- **macOS**: `~/Library/Rime`
    
- **Linux**:
  
    - ibus-rime: `~/.config/ibus/rime`
        
    - fcitx-rime: `~/.config/fcitx/rime`
        
    - fcitx5-rime: `~/.local/share/fcitx5/rime`
        
        _(Linux 若載入異常，請重啟輸入法前端後重新部署)_

### 方法一：自動配置（需 Git 與 Make）

在專案根目錄執行：
  
Bash

```bash
git submodule update --init --recursive
cd tools
make install
```

腳本將自動識別 `<RIME>` 目錄、複製碼表與插件並註冊方案。完成後執行 RIME **重新部署** 並選擇 `雙拼逆倉` 即可。若失敗請檢查目錄寫入權限與 Git 子模組完整性。

### 方法二：手工配置

#### 1. 註冊輸入法方案

編輯 `<RIME>/default.custom.yaml`（若已有其他方案請追加於 `schema_list` 下，勿直接覆蓋）：
  
YAML

```yaml
patch:
  schema_list:
    - {schema: flypy_cangjie5}
```

#### 2. 安裝碼表與方案配置

複製專案檔案至 `<RIME>`：

| **來源檔案**                     | **目標位置**                            |
| ---------------------------- | ----------------------------------- |
| `flypy_cangjie5.schema.yaml` | `<RIME>/flypy_cangjie5.schema.yaml` |
| `flypy_cangjie5*.dict.yaml`  | `<RIME>/flypy_cangjie5*.dict.yaml`  |

#### 3. 安裝插件（請保留原有子目錄結構）

| **來源檔案**                             | **目標位置**                            |
| ------------------------------------ | ----------------------------------- |
| `plugins/lua/*.lua`                  | `<RIME>/lua/*.lua`                  |
| `plugins/lua/rime.lua`               | `<RIME>/rime.lua`                   |
| `plugins/latex/latex.*.yaml`         | `<RIME>/latex.*.yaml`               |
| `plugins/flypy_cangjie5.custom.yaml` | `<RIME>/flypy_cangjie5.custom.yaml` |

#### 4. 重新部署

完成上述複製後，執行 RIME 的「重新部署」使配置生效。
