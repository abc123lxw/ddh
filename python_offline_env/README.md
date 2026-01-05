用于在离线 Linux 系统上构建 Python 运行环境。支持多个 `pyproject.toml` 文件的自动融合和冲突检测。

## 为什么使用 Conda？

- **离线环境**：目标机器是离线的 Linux 系统，系统 Python 版本可能很旧
- **完整环境**：Conda 提供完整的 Python 解释器、pip 等工具，不依赖系统 Python
- **版本控制**：可以指定任意 Python 版本（如 3.12、3.13），不受系统限制
- **即开即用**：打包后的环境解压即可使用

## 功能特性

- ✅ 多文件融合：自动合并多个 `pyproject.toml`，解决版本冲突
- ✅ 依赖管理：使用 `uv` 快速安装，自动选择更高版本
- ✅ 环境优化：清理缓存减少体积，生成锁定文件确保可重现
- ✅ 完整打包：包含 Python 解释器的完整 Conda 环境

## 快速开始

### 1. 准备工具

在联网机器上安装：
- `conda`（Miniconda/Anaconda）
- `uv`：`curl -LsSf https://astral.sh/uv/install.sh | sh`

### 2. 构建离线环境

```bash
cd utils/python_offline_env
python build_env.py pyproject.toml toolkit/pyproject.toml --force
```

**常用参数**：
- 位置参数：一个或多个 `pyproject.toml` 文件路径（必需）
- `--env-name`：环境名称，默认根据 Python 版本自动生成
- `--output`：离线包输出位置（默认 `dist/<env-name>.tar.gz`）
- `--force`：若目标环境已存在则删除后重建

### 3. 版本冲突处理

脚本自动处理：
- **Python 版本**：`>=3.12` 和 `>=3.13` 会选择 `3.13`
- **依赖版本**：相同包的不同版本自动选择更高版本
- **冲突警告**：检测到冲突时显示警告

### 4. 产出物

在 `dist` 目录生成：
- `<env-name>.tar.gz`：完整 Conda 环境（包含 Python 解释器）
- `install_<env-name>.sh`：安装脚本
- `<env-name>_requirements.txt`：依赖列表
- `<env-name>_manifest.txt`：构建信息
- `<env-name>_uv.lock`：锁定文件（如果成功生成）

### 5. 在离线机器安装

```bash
# 拷贝文件到离线机器
bash install_py313_offline.sh [压缩包路径] [目标环境路径]
source /path/to/envs/py313_offline/bin/activate
```

## 使用示例

```bash
# 融合多个项目的依赖
python build_env.py \
  utils/python_offline_env/pyproject.toml \
  toolkit/python_container/pyproject.toml \
  --env-name merged_offline \
  --force
```