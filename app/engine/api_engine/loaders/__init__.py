"""数据适配子包：数据库模型 / 前端 dict → spec。

各 Loader 阶段：
- ``InlineRequestLoader``    Phase 2 ✓
- ``ApiModelLoader``         Phase 2 ✓
- ``TestCaseLoader``         Phase 3 ✓
- ``AutomationTaskLoader``   Phase 3 ✓
"""
from app.engine.api_engine.loaders.api_model_loader import ApiModelLoader  # noqa: F401
from app.engine.api_engine.loaders.automation_task_loader import (  # noqa: F401
    AutomationTaskLoader,
)
from app.engine.api_engine.loaders.base import BaseLoader  # noqa: F401
from app.engine.api_engine.loaders.inline_request_loader import (  # noqa: F401
    InlineRequestLoader,
)
from app.engine.api_engine.loaders.test_case_loader import TestCaseLoader  # noqa: F401
