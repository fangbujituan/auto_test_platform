# SaaS 私有化部署与源码保护方案

> 本文档描述如何在支持客户本地私有化部署的同时，保护产品源码不被二次售卖。  
> 核心思路：交付的不是源码，是"黑盒运行时"。

---

## 一、产品交付形态

| 形态 | 说明 | 目标客户 |
|------|------|---------|
| SaaS 版 | 云上多租户，客户直接使用 | 中小团队、个人开发者 |
| 私有化版 | 交付加密/编译后的制品 + License 授权，部署到客户环境 | 对数据安全有要求的企业客户 |

---

## 二、技术保护方案（三道防线）

### 2.1 第一道防线：Docker 镜像交付

客户拿到的是编译好的 Docker 镜像，不是源码。通过多阶段构建，最终镜像中只包含编译产物。

```dockerfile
# Dockerfile.production - 多阶段构建

# --- 阶段1: 编译 Python 为 .so（Cython）---
FROM python:3.11-slim AS builder

WORKDIR /build
COPY app/ ./app/
COPY requirements.txt .

RUN pip install cython
COPY build_script.py .
RUN python build_script.py

# --- 阶段2: 前端构建 ---
FROM node:18-slim AS frontend
WORKDIR /build
COPY client/ ./client/
RUN cd client && npm ci && npm run build

# --- 阶段3: 最终运行镜像（只有编译产物，没有源码）---
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /build/dist/ ./app/
COPY --from=frontend /build/client/dist/ ./static/
COPY --from=builder /build/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 删除所有 .py 源文件，只保留编译产物
RUN find /app -name "*.py" -delete 2>/dev/null; exit 0

EXPOSE 12048
CMD ["python", "-m", "gunicorn", "app.flask_app:create_app()"]
```

### 2.2 第二道防线：Cython 编译核心代码

将 Python 源码编译成 C 扩展（.so/.pyd），反编译难度大幅提升。

```python
# build_script.py
import os
from Cython.Build import cythonize
from setuptools import setup, Extension

def collect_py_files(base_dir):
    """收集所有需要编译的 .py 文件"""
    extensions = []
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.py') and f != '__init__.py':
                filepath = os.path.join(root, f)
                module = filepath.replace(os.sep, '.').replace('.py', '')
                extensions.append(Extension(module, [filepath]))
    return extensions

extensions = collect_py_files('app')

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={'language_level': "3"},
        build_dir="build"
    )
)
```

编译后客户拿到的是 `.so`（Linux）或 `.pyd`（Windows）二进制文件，不是 `.py`。

### 2.3 第三道防线：License 授权系统（最关键）

即使客户拿到了镜像，没有有效 License 就无法运行。

#### License 验证器（随产品交付）

```python
# app/license/license_manager.py
import json
import hashlib
import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

class LicenseManager:
    """License 授权管理器"""

    def __init__(self, public_key_path):
        with open(public_key_path, 'rb') as f:
            self.public_key = serialization.load_pem_public_key(f.read())

    def verify_license(self, license_path):
        """验证 License 文件"""
        with open(license_path, 'r') as f:
            license_data = json.load(f)

        payload = license_data['payload']
        signature = bytes.fromhex(license_data['signature'])

        # 1. 验证签名（用我方私钥签发，公钥验证）
        try:
            self.public_key.verify(
                signature,
                json.dumps(payload, sort_keys=True).encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        except Exception:
            return False, "License 签名无效"

        # 2. 检查过期时间
        expires = datetime.datetime.fromisoformat(payload['expires_at'])
        if datetime.datetime.now() > expires:
            return False, "License 已过期"

        # 3. 检查机器指纹（绑定部署环境）
        current_fingerprint = self._get_machine_fingerprint()
        if payload.get('machine_id') and payload['machine_id'] != current_fingerprint:
            return False, "License 与当前机器不匹配"

        # 4. 校验通过
        return True, payload

    def _get_machine_fingerprint(self):
        """获取机器指纹（MAC地址 + 主机名 + 架构的哈希）"""
        import uuid
        import platform
        raw = f"{uuid.getnode()}-{platform.node()}-{platform.machine()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
```

#### License 签发工具（内部持有，不交付给客户）

```python
# tools/license_generator.py（内部工具）
import json
import datetime
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

class LicenseGenerator:
    def __init__(self, private_key_path):
        with open(private_key_path, 'rb') as f:
            self.private_key = serialization.load_pem_private_key(f.read(), password=None)

    def generate(self, customer_name, machine_id, plan, duration_days, max_users):
        payload = {
            "customer": customer_name,
            "machine_id": machine_id,
            "plan": plan,
            "max_users": max_users,
            "max_projects": {"free": 3, "pro": 50, "enterprise": -1}[plan],
            "features": self._get_plan_features(plan),
            "issued_at": datetime.datetime.now().isoformat(),
            "expires_at": (
                datetime.datetime.now() + datetime.timedelta(days=duration_days)
            ).isoformat(),
        }

        signature = self.private_key.sign(
            json.dumps(payload, sort_keys=True).encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        return {"payload": payload, "signature": signature.hex()}

    def _get_plan_features(self, plan):
        features = {
            "free": ["basic_testing"],
            "pro": ["basic_testing", "api_management", "bug_tracking", "reports"],
            "enterprise": [
                "basic_testing", "api_management", "bug_tracking",
                "reports", "sso", "audit_log", "custom_roles"
            ],
        }
        return features.get(plan, [])
```


#### Flask 启动时校验 License

```python
# app/flask_app.py 改造
def create_app(config_name=None):
    app = Flask(__name__)
    # ... 现有配置 ...

    # 私有化部署时校验 License
    if os.getenv("DEPLOYMENT_MODE") == "private":
        from app.license.license_manager import LicenseManager
        lm = LicenseManager(public_key_path="/app/keys/public.pem")
        valid, result = lm.verify_license("/app/license/license.json")
        if not valid:
            print(f"License 校验失败: {result}")
            import sys
            sys.exit(1)

        # 把 License 信息存到 app config，后续用于功能开关和配额控制
        app.config['LICENSE'] = result
        app.config['MAX_USERS'] = result.get('max_users', 5)
        app.config['FEATURES'] = result.get('features', [])

    # ... 注册蓝图等 ...
    return app
```

#### License 文件示例（JSON 格式）

```json
{
  "payload": {
    "customer": "某某科技有限公司",
    "machine_id": "a1b2c3d4e5f6...",
    "plan": "enterprise",
    "max_users": 50,
    "max_projects": -1,
    "features": ["basic_testing", "api_management", "bug_tracking", "reports", "sso", "audit_log", "custom_roles"],
    "issued_at": "2026-02-13T10:00:00",
    "expires_at": "2027-02-13T10:00:00"
  },
  "signature": "3a4b5c6d..."
}
```

---

## 三、架构分层设计

```
┌─────────────────────────────────────────────┐
│          商业功能（编译交付，不开源）         │
│  SSO/LDAP │ 审计日志 │ 高级报表 │ 自定义角色  │
├─────────────────────────────────────────────┤
│          License 授权层（编译交付）          │
│  授权校验 │ 功能开关 │ 配额控制 │ 心跳上报    │
├─────────────────────────────────────────────┤
│          核心功能（可选择性开源）            │
│  项目管理 │ 用例管理 │ Bug管理 │ API测试     │
├─────────────────────────────────────────────┤
│          基础框架                            │
│  Flask │ SQLAlchemy │ Vue │ Element Plus    │
└─────────────────────────────────────────────┘
```

功能分层的好处：
- 核心功能可以选择性开源，吸引社区用户
- 商业功能只在付费版中提供，通过 License 中的 features 字段控制
- 授权层是独立模块，可以灵活调整策略

---

## 四、心跳机制（可选）

私有化部署的实例定期向授权服务器"报到"，用于掌握部署状态和使用情况。

```python
# app/license/heartbeat.py
import threading
import requests

def start_heartbeat(app):
    """后台线程定期上报心跳"""
    def _beat():
        while True:
            try:
                license_info = app.config.get('LICENSE', {})
                requests.post(
                    "https://license.yourcompany.com/heartbeat",
                    json={
                        "customer": license_info.get('customer'),
                        "machine_id": license_info.get('machine_id'),
                        "version": app.config.get('APP_VERSION'),
                        "users_count": _get_active_users_count(),
                    },
                    timeout=5
                )
            except Exception:
                pass  # 心跳失败不影响正常使用（离线环境友好）
            threading.Event().wait(3600 * 6)  # 每6小时一次

    t = threading.Thread(target=_beat, daemon=True)
    t.start()
```

> 注意：心跳失败不要阻断服务。有些客户是纯内网环境，心跳只是辅助监控手段，不是强制依赖。

---

## 五、技术方案对比

| 方案 | 保护强度 | 实施难度 | 适用阶段 |
|------|---------|---------|---------|
| Docker 镜像交付 | ★★★☆☆ | 低 | 快速起步，立即可用 |
| Cython 编译 .so | ★★★★☆ | 中 | 中期方案，显著提升反编译难度 |
| PyInstaller/Nuitka 打包 | ★★★☆☆ | 中 | 备选方案 |
| Go/Rust 重写核心模块 | ★★★★★ | 高 | 长期方案，终极保护 |
| License 授权（RSA 签名） | 配合使用 | 中 | 必须有，商业保护的核心 |

推荐组合：**Docker 镜像 + Cython 编译 + License 授权**

---

## 六、商业与法律保护

技术手段只是辅助，商业和法律手段才是根本保障：

1. **合同约束**：签署软件许可协议，明确禁止反编译、二次分发、转售，约定违约金
2. **按年授权**：License 设有效期（通常1年），到期需续费获取新 License
3. **功能分级**：免费版功能有限，高级功能需要更高级别的 License
4. **绑定机器**：License 绑定客户服务器指纹，不能随意迁移复制
5. **版本更新**：只有有效授权的客户才能获取新版本镜像

---

## 七、客户交付流程

```
客户购买
  → 签署软件许可协议
  → 客户运行指纹采集工具，提供机器指纹
  → 我方签发 License 文件
  → 交付 Docker 镜像（通过私有镜像仓库拉取）+ License 文件
  → 客户使用 docker compose up 启动
  → 系统校验 License 后正常运行
```

### 客户部署配置（docker-compose.yml）

```yaml
version: '3.8'
services:
  app:
    image: your-registry.com/atp:v3.0  # 私有镜像仓库
    ports:
      - "80:12048"
    volumes:
      - ./license.json:/app/license/license.json:ro  # 挂载 License（只读）
      - ./data:/app/data  # 数据持久化
    environment:
      - DEPLOYMENT_MODE=private
      - MYSQL_HOST=db
      - MYSQL_PASSWORD=${DB_PASSWORD}
    depends_on:
      - db

  db:
    image: mysql:8.0
    volumes:
      - mysql_data:/var/lib/mysql
    environment:
      - MYSQL_ROOT_PASSWORD=${DB_PASSWORD}
      - MYSQL_DATABASE=atp

volumes:
  mysql_data:
```

---

## 八、实施路线图

### 阶段一：基础保护（1-2 周）

- [ ] 搭建 Docker 多阶段构建流程
- [ ] 实现 License 签发与验证模块
- [ ] Flask 启动时集成 License 校验
- [ ] 搭建私有 Docker 镜像仓库

### 阶段二：增强保护（1-2 周）

- [ ] 集成 Cython 编译流程到 CI/CD
- [ ] 实现机器指纹采集工具（交付给客户运行）
- [ ] 实现功能开关（根据 License 中的 features 控制功能可用性）
- [ ] 实现配额控制（用户数、项目数限制）

### 阶段三：运营支撑（2-3 周）

- [ ] 实现心跳上报机制
- [ ] 搭建 License 管理后台（内部使用）
- [ ] 制定软件许可协议模板
- [ ] 编写客户部署手册

### 阶段四：持续优化

- [ ] 考虑核心模块用 Go/Rust 重写
- [ ] License 在线续期能力
- [ ] 远程诊断与支持通道
- [ ] 自动化升级推送机制

---

## 九、安全注意事项

1. **私钥保管**：RSA 私钥只在内部签发环境使用，绝不随产品交付
2. **公钥嵌入**：公钥编译进二进制产物中，不以明文 .pem 形式存在（进阶优化）
3. **镜像仓库**：使用带认证的私有镜像仓库（如 Harbor），按客户分配拉取权限
4. **License 文件**：建议客户妥善保管，丢失需重新签发
5. **数据库密码**：通过环境变量注入，不硬编码在配置中
