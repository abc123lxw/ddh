# 工作代码仓库

这个仓库用于存放工作中的各种代码模块。

## 📝 如何添加新的代码模块

### 方法一：使用 Git 命令行（推荐）

1. **在项目根目录创建新模块目录**
   ```bash
   mkdir your_module_name
   ```

2. **将代码文件放入新目录**
   ```bash
   copy your_code.py your_module_name\
   ```

3. **添加并提交**
   ```bash
   git add your_module_name/
   git commit -m "添加：your_module_name 模块"
   git push origin main
   ```

### 方法二：使用 GitHub 网页

1. 访问 https://github.com/abc123lxw/ddh
2. 点击 "Add file" → "Create new file"
3. 输入路径：`your_module_name/your_code.py`
4. 粘贴代码并提交

### 常用命令

```bash
# 查看状态
git status

# 添加文件
git add <文件或目录>

# 提交
git commit -m "提交说明"

# 推送
git push origin main

# 拉取最新代码
git pull origin main
```

## 📁 当前模块

- `litellm_error_analyzer/` - LiteLLM 错误日志分析工具

---

**提示**：每个模块的详细说明请查看对应模块目录中的 README.md
