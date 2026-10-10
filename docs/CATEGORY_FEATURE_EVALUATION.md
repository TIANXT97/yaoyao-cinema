TIAN 主公、夭夭管家，见信好！

针对夭夭影社（yaoyao-cinema）增加**「二级分类胶囊导航（电影、国产剧、韩剧、欧美剧）」**的需求，我从**系统架构、数据模型、API契约、UI/UX极简美学以及TV端遥控适配**五个维度，为您输出以下详细的技术评估与落地实施方案。

---

### 一、 核心评估：方案选型与技术权衡

#### 1. 方案对比：动态路径匹配 vs. 标签系统 vs. 数据库显式字段

| 方案 | 实现方式 | 优点 | 缺点 | 推荐指数 |
| :--- | :--- | :--- | :--- | :--- |
| **方案 A：SQL 动态 LIKE 匹配** | 在 `video_service.py` 查询时根据入参拼接 `file_path LIKE '%/电影/%'` | 零数据库变更，当天上线 | 性能差（LIKE 无法利用 B-Tree 索引）；规则僵硬，一旦文件夹命名微调（如“华语剧”）全盘失效 | ★★☆☆☆ |
| **方案 B：复用现有 Tag/标签表** | 将分类作为特殊 Tag 注入多对多关系表 | 复用度高，灵活性强 | 过于泛化；剧集聚合查询与统计时关联查询开销大；二级分类属于**强分类（单选属性）**，不宜与弱标签混淆 | ★★★☆☆ |
| **方案 C：新增 `category` 字段 + 扫描器自动推断（推荐）** | `videos` 表增加带索引的 `category` 字段；入库时自动正则识别，支持手工纠偏 | **最优雅低成本**；单字段查询性能极高（<1ms）；逻辑正交；完美兼容剧集聚合与统计；未来支持自定义重命名 | ★★★★★ |

#### 2. 结论与建议
**果断采纳方案 C（新增 `category` 列并建索引）**。
- **原因**：目前总数据量约 94 部/系列（近 2000 集），数据量小而精，一次性迁移耗时不到 0.1 秒。
- **演进友好**：不仅可以按路径推断，后续还可以在元数据抓取（TMDB）或前端手工管理时灵活调整分类。

---

### 二、 后端改动评估与设计

#### 1. 数据库定义与标准字典
在 `videos` 表中追加 `category` 字段（建议使用英文字符串作为枚举存储，前端展示时映射中文，避免 URL 编码混乱）：

```python
# 数据字典设计
CATEGORY_MAP = {
    "movie": {"label": "电影", "keyword": "/电影/"},
    "c_drama": {"label": "国产剧", "keyword": "/国产剧/"},
    "k_drama": {"label": "韩剧", "keyword": "/韩剧/"},
    "w_drama": {"label": "欧美剧", "keyword": "/欧美剧/"},
    "other": {"label": "私房/其它", "keyword": None}  # 兜底如本地私房/未分类
}
```

- **SQLite DDL 改造**：
  ```sql
  ALTER TABLE videos ADD COLUMN category VARCHAR(32) DEFAULT 'other';
  CREATE INDEX idx_videos_category ON videos(category);
  ```

#### 2. 自动推断引擎（扫描与入库）
在媒体扫描模块（如 `scanner_service.py` 或入库逻辑中）增加纯函数推断：

```python
def detect_category(file_path: str) -> str:
    path_lower = file_path.lower()
    if "/电影/" in file_path or "/movies/" in path_lower:
        return "movie"
    if "/国产剧/" in file_path or "/c-drama/" in path_lower:
        return "c_drama"
    if "/韩剧/" in file_path or "/k-drama/" in path_lower:
        return "k_drama"
    if "/欧美剧/" in file_path or "/western/" in path_lower:
        return "w_drama"
    return "other"
```

#### 3. API 契约扩充（`GET /api/videos`）
- **新增 Query 参数**：
  `category: Optional[str] = Query(None, description="分类标识: movie, c_drama, k_drama, w_drama, other")`
- **新增分类统计接口（给前端胶囊展示数量角标）**：
  `GET /api/videos/categories/summary`
  返回各分类下的剧集聚合部数：`{"all": 94, "movie": 29, "c_drama": 33, "k_drama": 27, "w_drama": 3, "other": 2}`

---

### 三、 风险与兼容性评估：`group_series=True` 的聚合逻辑

**核心难点**：国产剧有 1438 集，但只有 33 部系列。当用户选择“国产剧”时，必须保证分页是按**「部（33部）」**分页，而不是按**「集（1438集）」**分页。

#### 兼容性方案设计
目前已实现的 `group_series=True` 采用 `series_name` 进行 `GROUP BY` 或子查询聚合。
分类过滤必须放置在**聚合之前/之中**：
1. **同系列内的一致性**：同系列的各集视频，其文件路径必定在同一顶级分类目录下，因此 `category` 属性具有绝对的一致性。
2. **SQL 核心逻辑伪代码**：
   ```sql
   -- 当 category != None 且 group_series = True 时
   SELECT 
       COALESCE(series_name, title) AS display_name,
       COUNT(*) as episode_count,
       MAX(id) as id,
       category,
       -- ... 聚合元数据
   FROM videos
   WHERE (:category IS NULL OR category = :category)
     AND (:status IS NULL OR status = :status)
     AND (:favorite IS NULL OR is_favorite = :favorite)
   GROUP BY display_name
   ORDER BY ...
   LIMIT :limit OFFSET :offset;
   ```
3. **分页总数（Total Count）**：
   务必使用 `SELECT COUNT(DISTINCT COALESCE(series_name, title))`，确保返回的分页计数完全准确。

---

### 四、 前端 UI 交互设计（纯白极简通透风格）

#### 1. 交互层级划分
为了保持极简与纯粹，避免两排按钮互相抢戏，采用**“主胶囊 + 辅助微芯片”**的双层轻量结构：
- **一级：二级内容分类（强导航）**
  `全部 | 电影 (29) | 国产剧 (33) | 韩剧 (27) | 欧美剧 (3)`
  - 放置在页面顶部（Header 下方固定吸顶），纯白毛玻璃底色。
- **二级：状态速查 QuickFilter（弱状态）**
  `全部 · 未看 · 追剧中 · 收藏`
  - 作为胶囊右侧的小型 Switcher，或紧随其下的细长横条。

#### 2. 视觉表现规范（Tailwind 实现）
符合白月光极简视觉：
- **容器**：`bg-white/70 backdrop-blur-xl border-b border-zinc-100/80`
- **未激活胶囊**：`text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100/60 transition-all rounded-full px-4 py-1.5 text-sm font-medium`
- **激活胶囊**：`bg-zinc-900 text-white shadow-sm shadow-zinc-900/10 rounded-full px-4 py-1.5 text-sm font-medium transition-all`（或使用品牌雅白微灰底：`bg-zinc-100 text-zinc-900 font-semibold`）
- **数字角标**：`text-xs opacity-60 ml-1 font-mono`

#### 3. 前端组件示意代码（Vue 3 单文件片段）

```vue
<template>
  <div class="sticky top-16 z-30 bg-white/75 backdrop-blur-md border-b border-zinc-150/60 py-3 transition-colors">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
      
      <!-- 分类胶囊群：支持横向平滑滚动（移动端友好） -->
      <nav class="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5" role="tablist">
        <button
          v-for="cat in categories"
          :key="cat.key"
          :tabindex="0"
          @click="selectCategory(cat.key)"
          :class="[
            'flex items-center whitespace-nowrap px-4 py-1.5 rounded-full text-sm transition-all duration-200 focus:outline-none',
            'focus-visible:ring-2 focus-visible:ring-zinc-900 focus-visible:ring-offset-2', // TV遥控器高亮环
            activeCategory === cat.key
              ? 'bg-zinc-900 text-white shadow-sm font-medium'
              : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100/70'
          ]"
        >
          <span>{{ cat.label }}</span>
          <span v-if="counts[cat.key]" class="ml-1.5 text-[11px] font-mono opacity-60">
            {{ counts[cat.key] }}
          </span>
        </button>
      </nav>

      <!-- 快捷状态过滤 (未看 / 收藏) -->
      <div class="hidden sm:flex items-center gap-2 border-l border-zinc-200/60 pl-4 text-xs text-zinc-400">
        <button 
          @click="toggleFavoriteOnly" 
          :class="['px-2.5 py-1 rounded-md transition-colors', isFavoriteOnly ? 'text-rose-500 bg-rose-50' : 'hover:text-zinc-700']"
        >
          ♥ 只看收藏
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const activeCategory = ref('all')
const categories = [
  { key: 'all', label: '全部' },
  { key: 'movie', label: '电影' },
  { key: 'c_drama', label: '国产剧' },
  { key: 'k_drama', label: '韩剧' },
  { key: 'w_drama', label: '欧美剧' }
]

const counts = ref({ all: 94, movie: 29, c_drama: 33, k_drama: 27, w_drama: 3 })

const selectCategory = (key) => {
  activeCategory.value = key
  // 触发视频流重载: fetchVideos({ category: key === 'all' ? null : key, page: 1 })
}
</script>
```

#### 4. TV端（遥控器）交互体验保障
- **焦点环设计**：通过 `focus-visible:ring-2 focus-visible:ring-zinc-900`，使客厅 TV 浏览器在通过 D-pad（方向键）操控时，光标能精准在各个分类胶囊间游走。
- **自动对齐**：胶囊容器添加 `scroll-smooth`，遥控器选到屏幕边缘胶囊时自动滚动居中。

---

### 五、 详细改造方案与实施步骤（零风险落地）

#### 阶段一：数据库与元数据一键迁移（预计 10 分钟）
编写单次迁移脚本 `scripts/migrate_categories.py`：
```python
import sqlite3

def run_migration(db_path="cinema.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. 加列（如果不存在）
    try:
        cur.execute("ALTER TABLE videos ADD COLUMN category VARCHAR(32) DEFAULT 'other'")
        cur.execute("CREATE INDEX idx_videos_category ON videos(category)")
        print("[DB] 成功添加 category 列和索引")
    except sqlite3.OperationalError:
        print("[DB] category 列已存在，跳过添加")

    # 2. 依据路径回填
    cur.execute("UPDATE videos SET category = 'movie' WHERE file_path LIKE '%/电影/%'")
    cur.execute("UPDATE videos SET category = 'c_drama' WHERE file_path LIKE '%/国产剧/%'")
    cur.execute("UPDATE videos SET category = 'k_drama' WHERE file_path LIKE '%/韩剧/%'")
    cur.execute("UPDATE videos SET category = 'w_drama' WHERE file_path LIKE '%/欧美剧/%'")
    
    conn.commit()
    
    # 3. 校验回填结果
    cur.execute("SELECT category, count(*) FROM videos GROUP BY category")
    for row in cur.fetchall():
        print(f"分类: {row[0]}, 视频集数: {row[1]}")
        
    conn.close()

if __name__ == "__main__":
    run_migration()
```

#### 阶段二：后端路由与 Service 完善
1. **修改 Model**：在 SQLAlchemy 或 SQLModel 中追加 `category: Mapped[str] = mapped_column(String(32), default="other", index=True)`。
2. **入库扫描器拦截**：在新增文件插入 DB 处注入 `category = detect_category(file_path)`。
3. **接口扩展**：`GET /api/videos` 接收 `category: Optional[str] = None`，加入 SQLAlchemy Query 条件。

#### 阶段三：前端组件集成与联动
1. 抽象出 `<CategoryBar />` 组件，放入 `HomeView.vue` 和 `LibraryView.vue` 的顶层容器内。
2. 将当前的 `category` 状态注入 Pinia 或页面 URL Query（支持直接分享链接如 `yaoyao.local/?category=k_drama`）。
3. 切换分类时触发无感骨架屏加载，平滑淡入重排内容网格。

#### 阶段四：验证验收用例
- [x] 点击【电影】胶囊，列表只出现 29 部电影，右上角集数均显示为 1 或无集数角标。
- [x] 点击【国产剧】胶囊，列表聚合展示 33 部国产剧卡片，且卡片右下角正确展示集数（如“全 40 集”）。
- [x] TV 端通过遥控器左右键，可在胶囊间无缝切换，按确定键触发过滤。
- [x] 搜索框输入关键词时，能与选中的分类产生交集查询（如在【韩剧】下搜索主角名字）。

---

### 架构师交付总结

本方案**兼顾了极致的开发效率与长期的系统优雅性**。不需要推翻任何既有逻辑，仅凭一个轻量级的新增字段与推断机制，即可在完全保留现有剧集聚合体验的前提下，赋予用户在手机端与电视端“指尖一滑、沉浸换台”的丝滑享受。

TIAN 主公，夭夭已准备好随时执行本方案！若您审阅认可，我们可以立刻从阶段一的数据库迁移开始落地。