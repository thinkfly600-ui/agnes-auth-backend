# Agnes AI 后端 - Render 免费部署指南

## 一、注册 Render

1. 打开 https://render.com
2. 点 "Get Started" → 选 "Sign up with GitHub"（用 GitHub 账号注册最简单）
3. 无需绑定信用卡

---

## 二、把代码推送到 GitHub

Render 通过 GitHub 仓库自动部署。在电脑上操作：

```powershell
# 进入后端目录
cd "D:\agnes-backend"

# 初始化 Git
git init
git add .
git commit -m "Initial commit"

# 在 GitHub 上新建仓库（如：agnes-auth-backend）
# 然后关联并推送
git remote add origin https://github.com/你的用户名/agnes-auth-backend.git
git branch -M main
git push -u origin main
```

---

## 三、创建启动命令文件

Render 需要一个启动命令。确保仓库里有 `wsgi.py`（已经有了），
然后创建 `render_start.sh`：

```bash
#!/bin/bash
gunicorn -w 2 -b 0.0.0.0:10000 wsgi:app --timeout 120
```

在 Windows 上创建这个文件：

```powershell
cd D:\agnes-backend
@"
#!/bin/bash
gunicorn -w 2 -b 0.0.0.0:10000 wsgi:app --timeout 120
"@ | Set-Content render_start.sh -Encoding ASCII
git add render_start.sh
git commit -m "Add Render start script"
git push
```

---

## 四、在 Render 上创建 Web Service

1. Render 控制台 → 点 "New +" → "Web Service"
2. 选择你的 GitHub 仓库 `agnes-auth-backend`
3. 配置：

| 配置项 | 值 |
|--------|-----|
| Name | agnes-auth-backend（或任意名） |
| Region | Singapore（离中国最近） |
| Branch | main |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `bash render_start.sh` |
| Instance Type | **Free** |

4. 点 "Advanced" → 添加环境变量：

```
ADMIN_PASSWORD = 你的管理密码
SECRET_KEY = 你的随机密钥（如 aB3xK9mQ7wR2pL5n）
```

5. 点 "Create Web Service" → 等待 3-5 分钟自动部署

---

## 五、获取免费域名

部署成功后，Render 会分配一个免费域名：
```
https://agnes-auth-backend.onrender.com
```

### 绑定自定义域名（可选）

1. Render → 你的服务 → Settings → Custom Domain
2. 添加你的域名（如 `ai.yourdomain.com`）
3. 去域名 DNS 管理添加 CNAME 记录指向 Render 给的地址
4. Render 自动签发 SSL 证书

---

## 六、修改桌面端配置

打包前修改 `D:\agnes AI\activation_config.py`：

```python
BACKEND_URL = "https://agnes-auth-backend.onrender.com"
```

---

## 七、验证

```bash
# 测试 API
curl https://agnes-auth-backend.onrender.com/api/verify?code=TEST

# 浏览器打开
https://agnes-auth-backend.onrender.com/activate.html
https://agnes-auth-backend.onrender.com/admin
```

---

## ⚠️ Render 免费版注意事项

| 限制 | 说明 |
|------|------|
| **休眠机制** | 15分钟无请求后自动休眠，下次请求需等待 30-60 秒唤醒 |
| **月额度** | 750小时/月（刚好跑满一个月） |
| **带宽** | 100GB/月，个人使用足够 |

### 防止休眠（可选）

用 UptimeRobot（免费）每 10 分钟 ping 一次你的 API：
1. 注册 https://uptimerobot.com（免费）
2. 添加监控 → URL: `https://你的域名.onrender.com/api/verify?code=ping`
3. 监控间隔设为 5 分钟

这样你的服务就不会休眠了，免费用户也秒开。

---

## 完整文件清单（推送到 GitHub 的）

```
agnes-auth-backend/
├── server.py
├── db.py
├── auth.py
├── wsgi.py
├── gunicorn_config.py
├── render_start.sh       ← 新增
├── requirements.txt
└── static/
    ├── activate.html
    └── admin/
        ├── login.html
        ├── dashboard.html
        ├── vip-codes.html
        └── free_users.html
```

---

## 后续更新

代码有改动后：

```powershell
git add .
git commit -m "更新说明"
git push
```

Render 会自动检测到 GitHub 推送并重新部署（约 2-3 分钟）。