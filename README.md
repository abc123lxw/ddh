# LiteLLM 错误日志分析项目

这是一个用于分析 LiteLLM 错误日志的项目仓库，包含多个工作相关的代码模块。

## 📁 项目结构

```
ddh/
├── litellm_error_analyzer/          # LiteLLM 错误日志分析模块
│   ├── config.py                    # 配置文件
│   ├── jupyter_error_analyzer.py    # Jupyter 错误分析工具
│   ├── query_error_logs_docker.py   # Docker 环境下的日志查询工具
│   ├── requirements.txt             # Python 依赖包列表
│   └── run_analyzer.py              # 主运行脚本
├── README.md                        # 本文件
└── [其他工作模块目录]/              # 后续添加的其他工作代码模块
```

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/abc123lxw/ddh.git
cd ddh
```

### 2. 安装依赖

```bash
cd litellm_error_analyzer
pip install -r requirements.txt
```

### 3. 配置项目

编辑 `litellm_error_analyzer/config.py` 文件，配置数据库连接、API 密钥等必要参数。

### 4. 运行分析工具

```bash
python run_analyzer.py
```

## 📝 代码操作指南

### 如何添加新的工作代码模块

#### 方法一：使用 Git 命令行（推荐）

1. **确保在项目根目录**
   ```bash
   cd C:\Users\10279\Desktop\litellm\litellm_error_analyzer
   ```

2. **创建新的模块目录**
   ```bash
   # 例如：创建一个新的数据分析模块
   mkdir data_analysis_module
   ```

3. **将代码文件放入新目录**
   ```bash
   # 将你的代码文件复制到新目录
   copy your_code.py data_analysis_module\
   ```

4. **添加文件到 Git**
   ```bash
   git add data_analysis_module/
   ```

5. **提交更改**
   ```bash
   git commit -m "添加数据分析模块"
   ```

6. **推送到 GitHub**
   ```bash
   git push origin main
   ```

#### 方法二：使用 GitHub 网页界面

1. 访问 https://github.com/abc123lxw/ddh
2. 点击 "Add file" → "Create new file"
3. 输入路径，例如：`new_module/your_code.py`
4. 粘贴或编写代码
5. 点击 "Commit new file"

#### 方法三：批量添加多个文件

```bash
# 添加整个目录
git add new_module/

# 或者添加多个文件
git add file1.py file2.py file3.py

# 提交
git commit -m "添加新模块：包含多个功能文件"

# 推送
git push origin main
```

### 常用 Git 操作命令

#### 查看状态
```bash
git status                    # 查看当前更改状态
git log                       # 查看提交历史
git log --oneline             # 简洁的提交历史
```

#### 添加和提交
```bash
git add .                     # 添加所有更改
git add <文件或目录>          # 添加特定文件或目录
git commit -m "提交说明"      # 提交更改
```

#### 推送和拉取
```bash
git push origin main          # 推送到 GitHub
git pull origin main          # 从 GitHub 拉取最新代码
```

#### 创建新分支（用于开发新功能）
```bash
git checkout -b feature/new-feature    # 创建并切换到新分支
git push -u origin feature/new-feature # 推送新分支到 GitHub
```

#### 合并分支
```bash
git checkout main                      # 切换到主分支
git merge feature/new-feature          # 合并功能分支
git push origin main                   # 推送合并后的代码
```

### 更新现有代码

1. **修改文件后查看更改**
   ```bash
   git diff                    # 查看所有更改
   git diff <文件名>           # 查看特定文件的更改
   ```

2. **提交更改**
   ```bash
   git add <修改的文件>
   git commit -m "更新：描述你的更改"
   git push origin main
   ```

### 删除文件或目录

```bash
# 删除文件
git rm <文件名>
git commit -m "删除：文件名"
git push origin main

# 删除目录
git rm -r <目录名>
git commit -m "删除：目录名"
git push origin main
```

### 处理冲突

如果多人协作或在不同地方修改了代码，可能会遇到冲突：

```bash
# 拉取最新代码
git pull origin main

# 如果有冲突，Git 会提示
# 手动解决冲突后：
git add <解决冲突的文件>
git commit -m "解决合并冲突"
git push origin main
```

## 📦 模块说明

### litellm_error_analyzer

LiteLLM 错误日志分析工具集，包含：

- **config.py**: 项目配置文件，包含数据库连接、API 配置等
- **jupyter_error_analyzer.py**: 用于 Jupyter Notebook 环境的错误分析工具
- **query_error_logs_docker.py**: Docker 环境下的日志查询工具
- **run_analyzer.py**: 主运行脚本，执行错误日志分析
- **requirements.txt**: Python 依赖包列表

## 🔧 开发规范建议

### 目录命名规范
- 使用小写字母和下划线：`module_name`
- 使用有意义的名称：`data_analysis`、`report_generator` 等

### 文件命名规范
- Python 文件使用小写字母和下划线：`my_script.py`
- 配置文件统一命名为：`config.py` 或 `settings.py`
- 每个模块建议包含 `README.md` 说明该模块的用途

### 提交信息规范
- 使用中文或英文描述清楚
- 格式：`<类型>：<描述>`
- 类型示例：`添加`、`更新`、`修复`、`删除`、`重构`

示例：
```
添加：数据分析模块
更新：优化错误日志查询性能
修复：配置文件路径问题
```

## 🔐 安全注意事项

1. **不要提交敏感信息**
   - API 密钥
   - 密码
   - 数据库连接字符串（包含密码）
   - 个人隐私信息

2. **使用 .gitignore**
   - 创建 `.gitignore` 文件排除不需要版本控制的文件
   - 例如：`*.pyc`、`__pycache__/`、`.env`、`*.log`

3. **配置文件处理**
   - 使用 `config.example.py` 作为模板
   - 将实际的 `config.py` 添加到 `.gitignore`

## 📚 更多资源

- [Git 官方文档](https://git-scm.com/doc)
- [GitHub 使用指南](https://docs.github.com/)
- [Markdown 语法](https://www.markdownguide.org/)

## 🤝 协作流程

1. 从 GitHub 拉取最新代码：`git pull origin main`
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 开发并提交：`git add .` → `git commit -m "..."` → `git push origin feature/your-feature`
4. 在 GitHub 上创建 Pull Request
5. 代码审查后合并到主分支

## 📞 问题反馈

如有问题或建议，请在 GitHub Issues 中提交。

---

**最后更新**: 2025-12-31

