# RIME flypy-cangjie5-simp —「双拼逆仓」输入法方案

## 方案简介

`flypy-cangjie5-simp`（双拼逆仓）是一套基于**小鹤双拼**与**仓颉五代逆序辅助码**的音形输入法方案，旨在简单、快速、准确地输入现代汉语、古诗词、文言文等数百万字词。

### 设计核心与特色

- **确定性编码**：每个词条均有唯一指定编码，无需依赖候选词排序消歧。熟练后可直接输入完整编码，减少选词对思路的干扰。
    
- **音形结合**：以小鹤双拼为主码，仓颉五代字形为辅助码。仅在主码冲突时追加形码，高频词优先获得短码。
    
- **双拼输入，全拼显示**：兼顾输入效率与拼音的直观呈现，便于阅读、校对与理解。
    
- **高扩展性**：不限定词库或语言风格，通过可扩展的编码与消歧机制，兼顾日常输入与低频字、古籍用语的准确定位。
    
## 编码规则

### 1. 主码：小鹤双拼

- **单字**：使用两个按键表示拼音。
    
- **词语**：依次拼接各字的双拼码。
    
主码能够唯一定位词条时，无需输入形码。

### 2. 辅助码：仓颉五代逆序

主码发生冲突时，依照 **Last（尾码）→ First（首码）→ Second（次码）** 的顺序追加仓颉辅助码。

|词条长度|辅助码追加顺序|
|---|---|
|单字|尾码 → 首码 → 次码|
|双字词|末字尾码 → 首字首码 → 次字首码|
|三字词|末字尾码 → 首字首码 → 次字首码|
|四字及以上|不追加仓颉辅助码|

一至三字词依序追加辅助码；仍有冲突时，追加字母序号。四字及以上词条直接使用字母序号消歧，避免长词编码过长。

### 3. 唯一编码与词频分配

词条按词频从高到低分配编码。优先使用主码，发生冲突时逐步追加辅助码，直至取得未使用的编码。因此，高频词优先获得短码。

### 4. 简码

仅一至三字词设有简码。简码比对应主码短一键，按词频分配，并避开已有编码。

## 学习与辅助资源

仓颉速成码可作为辅助码的入门参考，但本方案采用特定的逆序取码规则。

### 双拼练习

- [双拼练习（小鹤双拼）](https://api.ihint.me/shuang/)
    

### 仓颉资源

- [五色仓颉（三代）](https://www.xn--0vqu8au0tro7d.com/)
    
- [仓颉卡片（五代兼三代）](https://www.hkcards.com/)
    
- [仓颉五代手册（维基教科书）](https://zh.wikibooks.org/w/index.php?title=%E5%80%89%E9%A0%A1%E8%BC%B8%E5%85%A5%E6%B3%95&variant=zh)
    
- [仓颉之友](https://www.chinesecj.com/)
    
- [仓颉字根表（五代兼三代）](https://www.chinesecj.com/forum/data/attachment/forum/202111/24/154815fwe23wu3npzz172k.png)
    
- [仓颉表（五代兼三代）](https://www.hkcards.com/img/cj-radical/cj-table-kel.png)
    
- [仓颉网上输入法（五代）](https://www.chinesecj.com/ime/cj5.php)
    

### 字典

- [汉语字典（含五代仓颉码）](https://www.hanyuguoxue.com/zidian/)
    
### 字体

可安装 [HanaMin（花园明朝字体）](https://glyphwiki.org/hanazono/hanazono-20170904.zip)，以显示更多 CJK 扩展区汉字。实际显示范围取决于字体版本；能否输入则取决于码表收录情况。

## 安装步骤

首先安装 [RIME 中州韵输入法引擎](https://rime.im/)。以下将用户配置目录简称为 `<RIME>`。

- **Windows 10 及以上**：`%APPDATA%\Rime`
    
- **macOS**：`~/Library/Rime`
    
- **Linux**：
    
    - ibus-rime：`~/.config/ibus/rime`
        
    - fcitx-rime：`~/.config/fcitx/rime`
        
    - fcitx5-rime：`~/.local/share/fcitx5/rime`
        

Linux 若无法正常加载方案，可重启输入法前端后重新部署。

### 方法一：自动安装

需预先安装 Git 与 Make。在项目根目录执行：

```
git submodule update --init --recursive
cd tools
make install
```

脚本将自动识别 RIME 配置目录，安装码表与插件并注册方案。完成后重新部署 RIME，选择「双拼逆仓」即可使用。

若安装失败，请检查目录写入权限及 Git 子模块是否完整。

### 方法二：手动安装

#### 1. 注册方案

编辑 `<RIME>/default.custom.yaml`，将方案加入 `schema_list`。若已有其他方案，请保留原有条目。

```
patch:
  schema_list:
    - {schema: flypy_cangjie5_simp}
```

#### 2. 安装码表与方案配置

将以下文件复制到 `<RIME>`：

|来源文件|目标位置|
|---|---|
|`flypy_cangjie5_simp.schema.yaml`|`<RIME>/flypy_cangjie5_simp.schema.yaml`|
|`flypy_cangjie5_simp*.dict.yaml`|`<RIME>/flypy_cangjie5_simp*.dict.yaml`|

#### 3. 安装插件

复制以下文件，并保留所需目录结构：

|来源文件|目标位置|
|---|---|
|`plugins/lua/*.lua`|`<RIME>/lua/`|
|`plugins/lua/rime.lua`|`<RIME>/rime.lua`|
|`plugins/latex/latex.*.yaml`|`<RIME>/latex.*.yaml`|
|`plugins/flypy_cangjie5_simp.custom.yaml`|`<RIME>/flypy_cangjie5_simp.custom.yaml`|

#### 4. 重新部署

完成复制后，执行 RIME「重新部署」，使配置生效。
