# Markdown 方括号问题并集

本文记录 YOLO、ViT、VGG 三篇解析后 Markdown 中和 `[]` 相关的问题模式。后续新增论文如果出现同类问题，可以继续补到这张表里。

## 问题并集

| 大类 | 上下文/前缀 | 典型形式 | 来源 |
|---|---|---|---|
| 正常数字引用 | 正文引用 | `[9]`、`[36, 21, 13, 10]` | YOLO |
| 数字引用被页链接污染 | 正文引用 | `[[10]](#page-8-0)`、`[\[35\]](#page-9-2)` | YOLO |
| 数字引用带转义 | 正文引用 | `[\\[35\\]](#page-9-2)` | YOLO |
| Figure 引用污染 | `Figure` | `Figure [1.](#page-0-0)`、`Figure [7,](#page-8-0)` | YOLO、ViT |
| Table 引用污染 | `Table` | `Table [2](#page-5-1)`、`Table [3.](#page-6-0)`、`Table [4)](#page-6-1)` | YOLO、ViT、VGG |
| Sect 引用污染 | `Sect.` | `Sect. [2.1)](#page-1-1)`、`Sect. [4]` | VGG |
| Appendix 引用污染 | `Appendix` | `Appendix [A,](#page-9-4)`、`Appendix [D.4)](#page-16-0)` | ViT、VGG |
| Eq/Equation 引用污染 | `Eq.` / `Equation` | `Eq. [1\)](#page-3-0)` | ViT |
| 作者年份引用整体被链接 | 作者年份引用 | `[\(Vaswani et al., 2017\)](#page-11-0)` | ViT |
| 作者年份引用被拆碎 | 作者年份引用 | `[Vaswani et al.](#page-11-0) [\(2017\)](#page-11-0)` | ViT |
| 作者年份引用半截链接 | 作者年份引用 | `[(Zeiler & Fergus,](#page-9-0) 2013; ...` | VGG |
| 年份残留方括号 | 作者年份结尾 | `Sermanet et al., [2014]))`、`Bell et al., [2014])` | VGG |
| 参考文献条目编号 | References 区域 | `- [10] P. F. Felzenszwalb...` | YOLO |
| 参考文献条目前缀带 span | References 区域 | `- <span id="page-8-0"></span>[10] ...` | YOLO |
| 参考文献尾部回链 | References 区域尾部 | `2010. [1,](#page-0-1) [4](#page-3-0)` | YOLO |
| URL 链接 | 外部链接 | `[https://github.com/](https://...)` | ViT |
| 图片空 alt | 图片 | `![](_page_0_Picture_12.jpeg)` | YOLO、ViT |
| 表格/正文数值范围 | 数值范围 | `[256;512]`、`[256; 512]`、`[Smin, Smax]` | VGG |
| Markdown 链接标点污染 | 各类交叉引用 | `[1.]`、`[2,]`、`[1)]`、`[D.4)]` | 三篇都有 |

## 核心分类

1. 数字引用问题：YOLO 最明显，正文引用、转义引用、双层括号、参考文献回链都混在一起。
2. 交叉引用问题：Figure / Table / Sect / Appendix / Eq 被错误做成 `#page-*` 链接，且标点混进 `[]`。
3. 作者年份引用问题：ViT 和 VGG 最明显，作者、年份、括号被拆成多个 Markdown 链接或残留方括号。

## 需要保护的正常情况

以下内容虽然包含 `[]`，但不是引用污染，处理时不能误删：

| 类型 | 例子 | 说明 |
|---|---|---|
| 数值范围 | `[256;512]`、`[256; 512]` | 表格或正文里的尺度范围 |
| 变量范围 | `[Smin, Smax]` | 数学/实验设置里的变量区间 |
| 正常 URL 链接 | `[google-research/vision_transformer](https://...)` | 真正的外部链接，应保留 |
| 图片语法 | `![](_page_0_Picture_12.jpeg)` | 图片本身不是引用，但可单独处理 alt |

## 判断优先级

1. `[]` 前面是 `!`：优先判断为图片。
2. 位于 References 区域：区分参考文献条目编号和尾部回链。
3. 前缀是 `Figure`：判断为图引用。
4. 前缀是 `Table`：判断为表引用。
5. 前缀是 `Sect.`：判断为章节引用。
6. 前缀是 `Eq.` / `Equation`：判断为公式引用。
7. 前缀是 `Appendix`：判断为附录引用。
8. 链接目标是 `http` / `https`：判断为外部链接。
9. 正文纯数字且无链接：多半是正常数字引用。
10. 正文数字链接到 `#page-*`：多半是脏数字引用。
11. 正文作者/年份链接到 `#page-*`：多半是脏作者年份引用。
12. 位于 Markdown 表格行内：先判断是否为数值范围或表格内容。
