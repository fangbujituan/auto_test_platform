"""
数据库迁移脚本 - 自动化目录与配置扩展。

修改表:
    1. api_folders          新增 type 列（区分 api/testcase/bug/automation 目录）
    2. automation_tasks     新增 folder_id / loop_count / fail_strategy /
                            interval_seconds 列
    3. automation_task_cases 新增 api_id 列（支持直接挂"接口"作为执行步骤）

兼容性: 所有新增列都带默认值；老数据不受影响：
    - api_folders.type 老行回填为 'api'
    - automation_tasks.folder_id 默认 NULL（未分类）
    - automation_tasks.loop_count 默认 1
    - automation_tasks.fail_strategy 默认 'continue'
    - automation_tasks.interval_seconds 默认 0
    - automation_task_cases.api_id 默认 NULL

幂等: 已存在的列将被跳过；可重复运行。

作者: yandc
创建时间: 2026-06-20
"""
from sqlalchemy import inspect, text

from app.flask_app import create_app
from app.models.base import db


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """检查表中是否已存在指定列。"""
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(inspector, table_name: str) -> bool:
    """检查表是否已存在。"""
    return table_name in inspector.get_table_names()


def index_exists(inspector, table_name: str, index_name: str) -> bool:
    """检查索引是否已存在。"""
    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def _alter_add_column(table: str, column_def: str, label: str):
    """执行 ALTER TABLE ADD COLUMN（不带 FK，避免老数据导致约束失败）。"""
    db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_def}"))
    db.session.commit()
    print(f"[OK] {label}")


def run_migration():
    """执行数据库迁移。"""
    app = create_app()

    with app.app_context():
        inspector = inspect(db.engine)

        # 1) 先创建尚未存在的表
        db.create_all()
        print("[OK] db.create_all 已同步未创建的表")

        # ----------------------------------------------------------------
        # 1. api_folders.type
        # ----------------------------------------------------------------
        if table_exists(inspector, "api_folders"):
            if not column_exists(inspector, "api_folders", "type"):
                _alter_add_column(
                    "api_folders",
                    "type VARCHAR(20) NOT NULL DEFAULT 'api'",
                    "api_folders 已添加 type 列（默认 'api'）",
                )
            else:
                print("[SKIP] api_folders.type 列已存在")

            # 回填老数据：MySQL ADD COLUMN 默认会用 DEFAULT 填充，
            # 但保险起见把空字符串/NULL 清掉
            updated = db.session.execute(text(
                "UPDATE api_folders "
                "SET type = 'api' "
                "WHERE type IS NULL OR type = ''"
            )).rowcount
            db.session.commit()
            if updated:
                print(f"[OK] api_folders.type 回填 {updated} 条老数据为 'api'")

            # 加索引
            inspector = inspect(db.engine)  # 重读 metadata
            if not index_exists(inspector, "api_folders", "idx_api_folders_type"):
                try:
                    db.session.execute(text(
                        "CREATE INDEX idx_api_folders_type "
                        "ON api_folders (type)"
                    ))
                    db.session.commit()
                    print("[OK] api_folders 已创建索引 idx_api_folders_type")
                except Exception as exc:  # noqa: BLE001
                    db.session.rollback()
                    print(f"[WARN] 创建索引 idx_api_folders_type 失败（可忽略）: {exc}")
            else:
                print("[SKIP] 索引 idx_api_folders_type 已存在")

        # ----------------------------------------------------------------
        # 2. automation_tasks 新列
        # ----------------------------------------------------------------
        inspector = inspect(db.engine)
        if table_exists(inspector, "automation_tasks"):
            specs = [
                (
                    "folder_id",
                    "folder_id INTEGER NULL",
                    "automation_tasks 已添加 folder_id 列",
                ),
                (
                    "loop_count",
                    "loop_count INTEGER NOT NULL DEFAULT 1",
                    "automation_tasks 已添加 loop_count 列",
                ),
                (
                    "fail_strategy",
                    "fail_strategy VARCHAR(20) NOT NULL DEFAULT 'continue'",
                    "automation_tasks 已添加 fail_strategy 列",
                ),
                (
                    "interval_seconds",
                    "interval_seconds DOUBLE NOT NULL DEFAULT 0",
                    "automation_tasks 已添加 interval_seconds 列",
                ),
            ]
            for col, ddl, label in specs:
                if column_exists(inspector, "automation_tasks", col):
                    print(f"[SKIP] automation_tasks.{col} 列已存在")
                    continue
                _alter_add_column("automation_tasks", ddl, label)
                # 重读，避免后续判断使用了旧 inspector
                inspector = inspect(db.engine)

            # 回填老数据兜底（默认值未生效时）
            db.session.execute(text(
                "UPDATE automation_tasks "
                "SET loop_count = 1 "
                "WHERE loop_count IS NULL OR loop_count < 1"
            ))
            db.session.execute(text(
                "UPDATE automation_tasks "
                "SET fail_strategy = 'continue' "
                "WHERE fail_strategy IS NULL OR fail_strategy = ''"
            ))
            db.session.execute(text(
                "UPDATE automation_tasks "
                "SET interval_seconds = 0 "
                "WHERE interval_seconds IS NULL OR interval_seconds < 0"
            ))
            db.session.commit()
            print("[OK] automation_tasks 老数据回填完成")

        # ----------------------------------------------------------------
        # 3. automation_task_cases.api_id
        # ----------------------------------------------------------------
        inspector = inspect(db.engine)
        if table_exists(inspector, "automation_task_cases"):
            if not column_exists(inspector, "automation_task_cases", "api_id"):
                _alter_add_column(
                    "automation_task_cases",
                    "api_id INTEGER NULL",
                    "automation_task_cases 已添加 api_id 列",
                )
            else:
                print("[SKIP] automation_task_cases.api_id 列已存在")

        print("\n[DONE] 自动化目录与配置迁移完成！")


if __name__ == "__main__":
    run_migration()
