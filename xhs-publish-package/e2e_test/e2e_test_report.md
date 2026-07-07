# xhs-publish-package 端到端集成测试报告

&gt; 测试日期: 2026-07-07  
&gt; 数据来源: content-generate-xhs (v3_test/round3) + image-compose (test results)  
&gt; 测试环境: Python 3.14, Windows

---

## 测试概述

使用上游两个 Skill 真实输出的样例数据，对 xhs-publish-package 进行端到端集成测试，验证完整工作流是否正常。

---

## 测试场景

### Test 01: 社团招新主题（单张封面图）

| 项 | 值 |
|----|-----|
| content_id | CNT-20260707-001 |
| 数据来源 | content-generate-xhs v3_test/round3/test_01 |
| 文案标题 | 招新没人来？学长掏心窝子给4条建议 |
| 标签数量 | 6个 |
| 图片数量 | 1张（image-compose test_01 封面） |
| 排期时间 | 2026-07-07T20:30:00+08:00 |

**验证结果**:
- ✅ 退出码: 0
- ✅ title.txt 内容正确
- ✅ body.txt 保留原始换行（长文约1500字，换行正确）
- ✅ hashtags.txt 6个标签，每行一个
- ✅ checklist.md:
  - 建议发布时间正确显示
  - 无残留 {xxx} 变量
  - 6个检查项完整
  - 话题标签空格分隔正确
- ✅ manifest.json 包含 package_created_at
- ✅ assets/ 有 cover.png（来自 image-compose 真实生成的封面图）
- ✅ xhs_publish_package.json status=success

---

### Test 02: 创业主题（3张图片，无排期）

| 项 | 值 |
|----|-----|
| content_id | CNT-20260707-003 |
| 数据来源 | content-generate-xhs v3_test/round3/test_03 |
| 文案标题 | 踩了几万的雷才明白，大学创业该怎么做 |
| 标签数量 | 7个 |
| 图片数量 | 3张（cover + card_01 + card_02） |
| 排期时间 | 空字符串（应显示"未设置"） |

**验证结果**:
- ✅ 退出码: 0
- ✅ title.txt 内容正确
- ✅ body.txt 约1300字，换行正确
- ✅ hashtags.txt 7个标签
- ✅ checklist.md:
  - 建议发布时间: **未设置** ✅（空字符串正确处理）
  - 检查项完整
  - 话题标签正确
- ✅ manifest.json: scheduled_at 为空字符串，package_created_at 存在
- ✅ assets/ 有 3 张图片:
  - cover.png（image-compose test_01）
  - card_01.png（image-compose test_04 xhs-card-01）
  - card_02.png（image-compose test_06 xhs-cover-03）
- ✅ 文件名保持原名，未重命名

---

### Test 03: 图片缺失场景

| 项 | 值 |
|----|-----|
| content_id | CNT-20260707-E2E3 |
| 图片数量 | 1张存在 + 1张故意缺失 |
| 排期时间 | 2026-07-08T12:00:00+08:00 |

**验证结果**:
- ✅ 退出码: 0（不中断流程）
- ✅ logs.txt 有 WARNING 级别日志
- ✅ assets/ 目录:
  - cover.png（存在，正常复制）✅
  - not_exists.png.missing（占位文件，有内容）✅
- ✅ 占位文件内容包含原始路径信息
- ✅ checklist.md 排期时间正确显示
- ✅ 流程未中断，其他文件正常生成

---

## 上游兼容性验证

### content-generate-xhs 输出字段映射

| content-generate-xhs 输出 | xhs-publish-package 输入 | 状态 |
|---------------------------|--------------------------|------|
| data.selected_title | title | ✅ 兼容 |
| data.body | body | ✅ 兼容（换行符正确处理） |
| data.hashtags | hashtags | ✅ 兼容（列表格式） |
| data.cover_text | cover_text | ✅ 兼容 |
| content_id | content_id | ✅ 兼容 |

### image-compose 输出集成

| image-compose 输出 | 集成方式 | 状态 |
|-------------------|----------|------|
| data.image_path (相对路径) | assets[].path = "./output/xxx.png" | ✅ 兼容 |
| 1080x1350 PNG 图片 | shutil.copy2 复制 | ✅ 兼容（图片完整复制） |

### 工作流串联验证

完整工作流：
```
content-generate-xhs → 生成文案 → output/ 目录放图片 → image-compose 生成图片
    ↓
input.json（整合文案+图片路径）
    ↓
xhs-publish-package --job-dir &lt;job_dir&gt;
    ↓
publish_package/（运营可直接使用）
```

✅ 工作流串联正常，无需格式转换。

---

## 问题修复记录

### Bug #1: .missing 占位文件为空

- **发现时间**: 端到端测试时
- **问题描述**: 图片不存在时创建的 .missing 占位文件内容为空
- **修复内容**: 写入原始路径和提示信息
- **修复位置**: main.py 第 198-204 行
- **修复后验证**: ✅ 占位文件包含"原始路径: ..."和"文件缺失..."提示

---

## 总结

| 测试项 | 结果 |
|--------|------|
| Test 01（单图） | ✅ 通过 |
| Test 02（多图+无排期） | ✅ 通过 |
| Test 03（图片缺失） | ✅ 通过 |
| 退出码正确性 | ✅ 全部为 0 |
| checklist 模板渲染 | ✅ 正确，无残留变量 |
| scheduled_at 空值处理 | ✅ 显示"未设置" |
| 换行符保留 | ✅ body.txt 格式正确 |
| 图片复制完整性 | ✅ 真实图片文件完整复制 |
| 缺失图片容错 | ✅ 创建占位文件，流程继续 |
| 日志输出 | ✅ INFO/WARNING 级别正确 |

**结论**: ✅ xhs-publish-package 与上游 content-generate-xhs 和 image-compose 的输出格式完全兼容，端到端集成测试全部通过。修复了一个占位文件内容为空的小问题后，功能完整可用。
