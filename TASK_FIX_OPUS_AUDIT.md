# Phase 7.5: Opus 4.6 终审 5 项低风险瑕疵微创修复任务书

请阅读 `docs/OPUS_FINAL_AUDIT_REPORT.md` 中第三节或终审裁决列出的 5 项微创瑕疵，对工程进行精准微创手术：

1. **瑕疵 A：多表写入事务包裹**
   - 检查 `server/scraper/pipeline.py`（以及 `server/database.py` 中被调用的方法），在写入视频元数据、演员关联、标签关联、系列关联等操作时，确保使用显式事务保护，一旦出错全部回滚，防止写入脏数据半成品。
2. **瑕疵 B：PIL 图像文件句柄显式释放**
   - 检查 `server/scraper/image_processor.py`，确保打开或处理 Image 对象后，无论成功或异常，都有 `img.close()` 或 `with Image.open(...) as img:` 保护，避免高并发长任务句柄泄漏。
3. **瑕疵 C：PlayerActivity 结果回传在 onPause 中补充兜底**
   - 检查 `android/app/src/main/java/com/yaoyao/cinema/PlayerActivity.kt`，在 `onPause()` 中增加 `if (isFinishing) { sendResult() }` 兜底保护，防极端系统强杀/分屏销毁丢失进度。
4. **瑕疵 D：安卓启动播放 URL 空值防御**
   - 检查 `android/app/src/main/java/com/yaoyao/cinema/PlayerActivity.kt`（及 `NativePlayerPlugin.kt`），当传入的 streamUrl 为空或格式非法时，增加安全防御判断与 Toast 友好提示，优雅退出而不是抛出崩溃。
5. **瑕疵 E：播放历史 completed 字段布尔转整型存储与清洗**
   - 检查 `server/services/history_service.py` 及相关数据落盘处，确保 `completed` 字段明确以 `1/0` 整型安全存储到 SQLite，避免类型混淆。

修复后要求：
- `python3 -m py_compile` 逐文件检查无语法错误；
- `python3 tests/test_scraper.py` 单测全过；
- `npm run build` 前端打包 0 错误；
- 保持代码干净微创，不要大拆大改。
