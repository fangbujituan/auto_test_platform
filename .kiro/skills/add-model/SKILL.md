---
name: add-model
description: 在 ATP 后端新增一个 ORM 模型（继承 BaseModel，含 id/created_at/updated_at），并写一次性 migration 脚本到 app/migrations/，更新 README 数据库表清单。
---

# 新增 ORM 模型

## 何时激活

用户说要"新增数据表 / 模型 / model / 实体"，或者 `add-route` skill 在执行中发现需要先建表。
典型触发词：「加一个 xxx 表」「新建 model」「需要存 xxx 数据」。

## 必要输入

确认（缺哪个问哪个）：

- 表名（snake_case，复数：`comments` / `test_runs`，对应 `__tablename__`）
- 类名（PascalCase 单数：`Comment` / `TestRun`）
- 字段清单（名称、类型、是否必填、是否外键、注释）
- 是否项目级（是否含 `project_id` 外键到 `projects.id`）
- 是否需要 `to_dict()`（默认是）

## 项目硬约束

1. **必须继承 `BaseModel`**（来自 `app/models/base.py`），自动获得 `id` / `created_at` / `updated_at`，**不要重复声明这三个字段**。
2. 文件 docstring 模板：
   ```
   """
   <资源中文名>模型。

   作者: yandc
   创建时间: YYYY-MM-DD
   """
   ```
3. 表名（`__tablename__`）用复数 snake_case，列定义按"业务语义分组 + 注释"，参考 `app/models/bug.py`。
4. 每列必须有 `comment="..."` 中文注释（迁移到 MySQL 时会落到 INFORMATION_SCHEMA，方便 DBA 查阅）。
5. **项目当前用 `db.create_all()` 建表**，没接 alembic。新加表会被自动建出，**新加字段不会**——必须写一次性 migration 脚本。
6. `to_dict()` 中 `datetime` 用 `.strftime("%Y-%m-%d %H:%M:%S")` 格式化；JSON 字段用 `or []` / `or {}` 兜底 None。
7. 外键命名 `<resource>_id`，加 `db.ForeignKey("<table>.id")`。
8. 状态 / 优先级类的字符串字段用 `db.String(20)` + `default="..."` + 在 `comment` 中列出可选值。

## 实现步骤

### 1. 读取相邻样例

读 `app/models/base.py` 和 `app/models/bug.py` 确认风格。

### 2. 写 Model

新建 `app/models/<resource>.py`：

```python
"""
<资源中文名>模型。

作者: yandc
创建时间: YYYY-MM-DD
"""
from app.models.base import db, BaseModel


class <Resource>(BaseModel):
    """<资源中文名>模型。"""

    __tablename__ = "<resources>"

    # ---- 业务字段 ----
    name = db.Column(db.String(200), nullable=False, comment="名称")
    description = db.Column(db.Text, comment="描述")

    # ---- 关联字段 ----
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id"), nullable=False
    )
    creator_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), comment="创建人ID"
    )

    # ---- 状态 ----
    status = db.Column(
        db.String(20), default="active",
        comment="状态: active, archived",
    )

    # ---- JSON / 扩展字段 ----
    tags = db.Column(db.JSON, comment="标签列表")
    extra = db.Column(db.JSON, comment="扩展字段")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "project_id": self.project_id,
            "creator_id": self.creator_id,
            "status": self.status,
            "tags": self.tags or [],
            "extra": self.extra or {},
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
```

### 3. 在初始化处导入（让 `db.create_all` 能感知到新表）

确认 `app/models/__init__.py` 或被 `flask_app.py` 间接导入的位置 import 了新 model。
如果项目惯用集中式 `__init__.py` 导出，需要追加；
如果惯例是 route 层 `from app.models.<resource> import <Resource>`，import 链建立后自动生效，跳过这一步。

### 4. 写 migration 脚本（仅当**修改已有表**或**需要回填默认值**时）

新建 `app/migrations/<verb>_<scope>_migration.py`，参考 `app/migrations/automation_folder_migration.py`：

```python
"""
<操作描述> migration 脚本。

适用场景：xxx
执行方式：python -m app.migrations.<filename>

作者: yandc
创建时间: YYYY-MM-DD
"""
from sqlalchemy import text
from app import create_app
from app.models.base import db


def upgrade():
    """正向迁移：加列 / 回填数据。"""
    with create_app().app_context():
        # 检查列是否已存在再添加，保证可重入
        result = db.session.execute(text("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = '<table>'
              AND column_name = '<column>'
        """)).scalar()
        if result == 0:
            db.session.execute(text(
                "ALTER TABLE <table> ADD COLUMN <column> <type> <constraint>"
            ))
            db.session.commit()
            print("✅ 加列成功")
        else:
            print("⏭ 列已存在，跳过")


def downgrade():
    """回滚（可选）。"""
    with create_app().app_context():
        db.session.execute(text("ALTER TABLE <table> DROP COLUMN <column>"))
        db.session.commit()


if __name__ == "__main__":
    upgrade()
```

**纯新建表不需要 migration**——`create_app()` 会调 `db.create_all()` 自动建出。

### 5. 更新 README 数据库表清单

在根目录 `README.md` 的"数据库设计"表格里追加一行（**仅当用户没有明确要求"不更 README"时**）：

```
| <resources>          | <资源中文名>表（一句话职责） |
```

## 验证

1. 启动一次后端：`python run.py`，确认无 ORM 报错且新表出现在 MySQL（`SHOW TABLES;`）。
2. 如果写了 migration：`python -m app.migrations.<filename>`，确认幂等（重跑不会报错）。
3. `python -c "from app.models.<resource> import <Resource>; print(<Resource>.__tablename__)"` 能 import。

## 反模式

- 在新 model 里重复定义 `id` / `created_at` / `updated_at` —— BaseModel 已经有了。
- 用 `Column` 不写 `comment` —— 中文注释是项目惯例。
- 直接 `ALTER TABLE` 不检查列存在 —— migration 必须可重入。
- 用 `datetime.utcnow` —— BaseModel 用的是 `datetime.now`（本地时区），保持一致。
