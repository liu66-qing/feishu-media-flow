# xhs-publish-package 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 上游输入
```
content-generate-xhs → 文案（title + body + hashtags）
image-compose → 图片（cover.png + card_XX.png）
         ↓ 整合为 input.json
xhs-publish-package
```

### 下游输出
```
xhs-publish-package → publish_package/ → app（发送到飞书 → 运营手动发布小红书）
```

### 字段映射（content-generate-xhs → xhs-publish-package）

| 上游输出 | 本模块输入 |
|----------|-----------|
| data.selected_title | title |
| data.body | body |
| data.hashtags | hashtags |
| data.cover_text | cover_text |

## 2. 内部工作流
```
input.json
  → load_input() — 读取 JSON
  → validate_input() — 校验必填字段
  → core_logic()
      → create_publish_directory() — 删除旧目录 + 重建
      → generate_text_files() — title.txt / body.txt / hashtags.txt
      → generate_checklist() — checklist.md（含内容预览 + 6项检查）
      → generate_manifest() — manifest.json（元数据 + 时间戳）
      → copy_assets() — 复制图片 / 创建 .missing 占位
  → xhs_publish_package.json（成功）/ error.json（失败）
```

## 3. 测试指南

### 单元测试（5 组）
```bash
cd xhs-publish-package
python test/run_tests.py
```

| 用例 | 场景 | 验证点 |
|------|------|--------|
| test_01 | 正常（2图） | 全部文件正确生成 |
| test_02 | 空 assets | 无 assets 目录 |
| test_03 | 多图（4图） | 全部图片复制 |
| test_04 | 无 scheduled_at | checklist 显示"未设置" |
| test_05 | 图片缺失 | .missing 占位文件 |

### 端到端测试（3 组）
```bash
python main.py --job-dir e2e_test/test_01  # 社团招新
python main.py --job-dir e2e_test/test_02  # 创业主题
python main.py --job-dir e2e_test/test_03  # 图片缺失
```

## 4. 调试技巧
- `logs.txt` 记录每一步文件操作，含 `[INFO]` / `[WARNING]` / `[ERROR]` 级别
- 图片路径问题：检查 `assets[].path` 是否相对于 `job_dir`，支持 `./` 前缀
- `manifest.json` 包含完整输入数据 + `package_created_at`，可用于排查数据传递问题
- `checklist.md` 中 `{variable}` 残留说明模板变量未替换，检查输入字段名
- 多次运行同一 job_dir 时，`publish_package/` 会被删除重建，`logs.txt` 追加写入

## 5. 扩展开发

### 支持视频资源
在 `copy_assets()` 中添加 `type: "video"` 分支，复制视频文件到 assets/。

### 自定义 checklist 模板
修改 `generate_checklist()` 中的 f-string 模板，可增减检查项或调整格式。

### 新增输出文件
在 `core_logic()` 中添加生成步骤，并更新 `files_count` 计算逻辑。

---

> Created by: 尹羿璇 | 2026-07-21
