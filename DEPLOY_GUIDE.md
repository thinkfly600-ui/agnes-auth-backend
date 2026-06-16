# Agnes AI 后端部署指南（宝塔面板 + Nginx）

## 一、服务器准备

### 1. 上传项目文件

将 `D:\agnes-backend` 整个文件夹上传到服务器，建议放在：

```
/www/wwwroot/agnes-backend/
```

宝塔面板 → 文件 → 进入 /www/wwwroot/ → 新建文件夹 agnes-backend → 上传所有文件

文件清单（确保以下文件都已上传）：
- server.py          Flask 主程序
- db.py              数据库操作
- auth.py            管理后台认证
- wsgi.py            WSGI 入口
- gunicorn_config.py Gunicorn 配置
- requirements.txt   依赖
- static/            静态文件（activate.html + admin/）

### 2. 安装 Python 依赖

宝塔面板 → 网站 → Python项目 → 添加Python项目

或通过 SSH：

```bash
cd /www/wwwroot/agnes-backend
pip3 install flask gunicorn
```

---

## 二、配置环境变量

### 宝塔面板方式：

宝塔 → 网站 → Python项目 → 找到本项目 → 设置 → 环境变量：

```
变量名: ADMIN_PASSWORD    值: 你的管理密码（如 MyAdmin@2026）
变量名: SECRET_KEY        值: 随机字符串（如 aB3xK9mQ7wR2pL5n）
```

### SSH 方式（如不用宝塔Python项目管理）：

```bash
echo 'export ADMIN_PASSWORD="你的密码"' >> ~/.bashrc
echo 'export SECRET_KEY="随机字符串"' >> ~/.bashrc
source ~/.bashrc
```

---

## 三、创建日志目录

```bash
mkdir -p /www/wwwroot/agnes-backend/logs
chmod 755 /www/wwwroot/agnes-backend/logs
```

---

## 四、启动服务（Gunicorn）

### 方式A：宝塔 Python 项目管理器（推荐）

1. 宝塔 → 网站 → Python项目 → 添加Python项目
2. 填写：
   - 项目名称: agnes-backend
   - 项目路径: /www/wwwroot/agnes-backend
   - 启动文件: wsgi.py
   - 运行方式: gunicorn
   - 端口: 5100
   - Python版本: 3.10+（服务器已安装的版本）
3. 点击确定 → 启动

### 方式B：SSH 命令行

```bash
cd /www/wwwroot/agnes-backend

# 先测试能否启动
gunicorn -w 2 -b 127.0.0.1:5100 wsgi:app

# Ctrl+C 停止测试后，使用 nohup 后台运行
nohup gunicorn -c gunicorn_config.py wsgi:app > /dev/null 2>&1 &

# 或使用 systemd 自启动（更稳定）
```

### 验证服务是否启动

```bash
curl http://127.0.0.1:5100/api/verify?code=TEST
# 应返回: {"valid":false,"reason":"invalid"}
```

---

## 五、配置 Nginx 反向代理

### 宝塔面板操作：

1. 宝塔 → 网站 → 添加站点
2. 域名: `你的域名`（如 ai.yourdomain.com）
3. 根目录: /www/wwwroot/agnes-backend/static
4. 点击提交

### 配置 HTTPS（推荐）：

宝塔 → 网站 → 站点设置 → SSL → Let's Encrypt → 申请

### 修改站点配置文件：

宝塔 → 网站 → 站点设置 → 配置文件 → 在 server 块中添加：

```nginx
# ===== 激活网页、管理后台（静态文件） =====
location / {
    root /www/wwwroot/agnes-backend/static;
    try_files $uri $uri/ =404;
}

location /activate.html {
    root /www/wwwroot/agnes-backend/static;
}

# ===== API 反向代理到 Gunicorn =====
location /api/ {
    proxy_pass http://127.0.0.1:5100;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
    proxy_connect_timeout 15s;
}

# ===== 管理后台反向代理 =====
location /admin {
    proxy_pass http://127.0.0.1:5100;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
}
```

保存后重载 Nginx：宝塔 → 网站 → 点击"重载"

---

## 六、修改桌面端配置

部署完成后，修改 `D:\agnes AI\activation_config.py` 中的后端地址：

```python
BACKEND_URL = "https://你的域名.com"   # 改为你的实际域名
```

例如：
```python
BACKEND_URL = "https://ai.yourdomain.com"
```

---

## 七、验证部署成功

### 1. 测试激活网页
浏览器打开：`https://你的域名.com/activate.html`
输入手机号点击获取 → 应显示激活码

### 2. 测试管理后台
浏览器打开：`https://你的域名.com/admin`
输入 ADMIN_PASSWORD → 应进入仪表盘

### 3. 测试 API
```bash
curl https://你的域名.com/api/verify?code=TEST
# → {"valid":false,"reason":"invalid"}
```

---

## 八、日常维护

### 查看日志
```bash
tail -f /www/wwwroot/agnes-backend/logs/error.log
tail -f /www/wwwroot/agnes-backend/logs/access.log
```

### 重启服务
宝塔 → Python项目 → 找到 agnes-backend → 重启

或：
```bash
pkill -f "gunicorn.*agnes"
cd /www/wwwroot/agnes-backend
nohup gunicorn -c gunicorn_config.py wsgi:app > /dev/null 2>&1 &
```

### 备份数据库
管理后台 → VIP码管理 → 点"备份数据库"
或手动复制：`cp codes.db codes.db.backup_$(date +%Y%m%d)`

### 修改管理员密码
SSH 登录服务器：
```bash
# 修改环境变量
export ADMIN_PASSWORD="新密码"
# 然后重启 Gunicorn 服务
```

---

## 九、群内激活链接

部署完成后，将激活链接发到微信群置顶：

```
🎬 AI视频创作工具 - 免费激活

1. 打开链接：https://你的域名.com/activate.html
2. 输入你的手机号
3. 获取激活码
4. 在软件中输入激活码即可免费使用

📌 激活后有效期1年，到期可重新激活
```

---

## 十、项目文件结构（确认已上传）

```
/www/wwwroot/agnes-backend/
├── server.py              # Flask 主程序
├── db.py                  # 数据库操作
├── auth.py                # 管理认证
├── wsgi.py                # WSGI 入口
├── gunicorn_config.py     # Gunicorn 配置
├── requirements.txt       # 依赖
├── codes.db               # SQLite 数据库（自动生成）
├── logs/                  # 日志目录（手动创建）
├── static/
│   ├── activate.html      # 用户激活页
│   └── admin/
│       ├── login.html     # 管理登录页
│       ├── dashboard.html # 仪表盘
│       ├── vip-codes.html # VIP码管理
│       └── free-users.html# 用户列表
```

---

如遇到问题，SSH 到服务器后执行以下排查步骤：

```bash
# 1. 检查 Gunicorn 是否运行
ps aux | grep gunicorn

# 2. 检查端口是否监听
netstat -tlnp | grep 5100

# 3. 直接测试 Flask
cd /www/wwwroot/agnes-backend
python3 wsgi.py  # Ctrl+C 停止

# 4. 查看错误日志
tail -100 /www/wwwroot/agnes-backend/logs/error.log
```