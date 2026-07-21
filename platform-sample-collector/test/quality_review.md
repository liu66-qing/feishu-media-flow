# platform-sample-collector 质量验证记录

## 测试时间

2026-07-21

## 测试对象

```text
platform-sample-collector/test/fixtures/job1
```

## 测试命令

```powershell
python platform-sample-collector/main.py --job-dir platform-sample-collector/test/fixtures/job1
```

## 测试结果

- 运行状态：success
- raw_count：11
- valid_count：11
- by_platform：
  - wechat：3
  - douyin：5
  - xhs：3
- fetch_errors：空
- degraded_platforms：空
- cache_used：false

## 验证结论

本轮测试验证了以下能力：

- 能读取统一 input.json。
- 能归一化公众号、抖音、小红书三个平台的公开样本。
- 每条样本包含标题、摘要、封面、标签、发布时间、来源、来源链接、互动数据、质量状态、数据状态和采集时间。
- 能按平台统计有效样本数量。
- 能输出可供后续平台偏好分析直接使用的结构化样本库。
- 三个平台均已有真实可追溯样本，未触发平台降级。

## 注意事项

当前 fixture 已替换为公开可追溯候选样本，`data_status=live` 表示来源网页真实存在。

后续如需扩大样本库，可以继续追加同格式样本；不要把缓存、fixture 或 fallback 内容标记为 live。
