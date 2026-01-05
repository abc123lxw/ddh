#!/usr/bin/env python3
"""
一键构建 Python 离线 Conda 环境、安装项目依赖并打包。
支持多个 pyproject.toml 文件的依赖融合和冲突检测。

用法示例：
    python build_env.py pyproject.toml toolkit/pyproject.toml --env-name py312_offline --force
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# 尝试使用标准库 tomllib (Python 3.11+)，否则使用 tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("错误: 需要 tomllib (Python 3.11+) 或 tomli 库来解析 TOML 文件")
        print("请运行: pip install tomli")
        sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ENV_ROOT = SCRIPT_DIR / "envs"
DEFAULT_DIST_DIR = SCRIPT_DIR / "dist"


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    """打印并执行命令。"""
    print(f"[RUN] {' '.join(str(part) for part in cmd)}")
    subprocess.run(cmd, check=True, env=env)


def parse_pyproject_toml(file_path: Path) -> dict[str, Any]:
    """解析 pyproject.toml 文件并提取项目信息。"""
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    with open(file_path, "rb") as f:
        data = tomllib.load(f)
    
    project = data.get("project", {})
    return {
        "requires_python": project.get("requires-python", ""),
        "dependencies": project.get("dependencies", []),
        "optional_dependencies": project.get("optional-dependencies", {}),
    }


def parse_version_spec(spec: str) -> tuple[str, str | None]:
    """
    解析版本规范字符串，返回 (包名, 版本要求)。
    例如: "pandas>=2.3.1" -> ("pandas", ">=2.3.1")
          "fastapi==0.127.0" -> ("fastapi", "==0.127.0")
          "requests" -> ("requests", None)
    """
    # 匹配包名和版本要求
    match = re.match(r"^([a-zA-Z0-9_-]+(?:\[[^\]]+\])?)(.*)$", spec.strip())
    if not match:
        return (spec.strip(), None)
    
    name, version = match.groups()
    version = version.strip() if version.strip() else None
    return (name, version)


def compare_versions(v1: str | None, v2: str | None) -> int:
    """
    比较两个版本要求，返回 -1 (v1 < v2), 0 (v1 == v2), 1 (v1 > v2)。
    如果无法比较，返回 0。
    """
    if v1 is None and v2 is None:
        return 0
    if v1 is None:
        return -1
    if v2 is None:
        return 1
    
    # 提取版本号部分进行比较
    def extract_version(ver_str: str) -> tuple[list[int], str]:
        # 移除操作符
        op_match = re.match(r"^([<>=!]+)", ver_str)
        op = op_match.group(1) if op_match else ""
        ver = ver_str[len(op):].strip()
        
        # 解析版本号
        parts = []
        for part in ver.split("."):
            try:
                parts.append(int(part))
            except ValueError:
                break
        return (parts, op)
    
    try:
        parts1, op1 = extract_version(v1)
        parts2, op2 = extract_version(v2)
        
        # 比较版本号
        for i in range(max(len(parts1), len(parts2))):
            p1 = parts1[i] if i < len(parts1) else 0
            p2 = parts2[i] if i < len(parts2) else 0
            if p1 < p2:
                return -1
            if p1 > p2:
                return 1
        
        # 版本号相同，比较操作符优先级: == > >= > > > < > <=
        op_priority = {"==": 3, ">=": 2, ">": 1, "<=": 0, "<": -1}
        priority1 = max([op_priority.get(op, 0) for op in re.findall(r"[<>=!]+", op1)], default=0)
        priority2 = max([op_priority.get(op, 0) for op in re.findall(r"[<>=!]+", op2)], default=0)
        
        if priority1 != priority2:
            return 1 if priority1 > priority2 else -1
        
        return 0
    except Exception:
        # 如果无法比较，返回 0
        return 0


def merge_dependencies(dep_lists: list[list[str]]) -> list[str]:
    """
    合并多个依赖列表，对于相同包的不同版本要求，选择更严格的版本。
    如果版本冲突（如 ==1.1 和 ==1.2），选择更高的版本号。
    保留包的 extras（如 markitdown[docx]）。
    """
    # 使用完整名称（包括 extras）作为键，但比较时使用基础名称
    dep_dict: dict[str, tuple[str, str | None]] = {}  # full_name -> (base_name, version)
    base_to_full: dict[str, str] = {}  # base_name -> full_name (用于查找)
    conflicts: list[tuple[str, str, str]] = []
    
    for deps in dep_lists:
        for dep in deps:
            full_name, version = parse_version_spec(dep)
            base_name = full_name.split("[")[0]  # 移除 extras 获取基础名称
            
            if base_name not in base_to_full:
                # 首次遇到这个包
                dep_dict[full_name] = (base_name, version)
                base_to_full[base_name] = full_name
            else:
                # 已存在相同基础名称的包
                existing_full_name = base_to_full[base_name]
                existing_base, existing_version = dep_dict[existing_full_name]
                
                if existing_version != version:
                    # 检查是否有明显冲突（如 ==1.1 vs ==1.2）
                    if existing_version and version:
                        if existing_version.startswith("==") and version.startswith("=="):
                            # 都是精确版本，选择更高的
                            if compare_versions(version, existing_version) > 0:
                                conflicts.append((base_name, existing_version, version))
                                # 更新版本，保留 extras（选择有 extras 的版本，如果都有则保留新的）
                                if "[" in full_name:
                                    dep_dict[full_name] = (base_name, version)
                                    base_to_full[base_name] = full_name
                                    if existing_full_name != full_name:
                                        del dep_dict[existing_full_name]
                                else:
                                    dep_dict[existing_full_name] = (base_name, version)
                            else:
                                conflicts.append((base_name, version, existing_version))
                        elif compare_versions(version, existing_version) > 0:
                            # 新版本更严格或更高，使用新版本
                            conflicts.append((base_name, existing_version, version))
                            if "[" in full_name:
                                dep_dict[full_name] = (base_name, version)
                                base_to_full[base_name] = full_name
                                if existing_full_name != full_name:
                                    del dep_dict[existing_full_name]
                            else:
                                dep_dict[existing_full_name] = (base_name, version)
                        # 否则保持现有版本
                else:
                    # 版本相同，但可能有不同的 extras，合并 extras
                    if "[" in full_name and "[" not in existing_full_name:
                        # 新版本有 extras，更新
                        dep_dict[full_name] = (base_name, version)
                        base_to_full[base_name] = full_name
                        del dep_dict[existing_full_name]
                    elif "[" in full_name and "[" in existing_full_name:
                        # 两个都有 extras，保留更完整的（更长的）
                        if len(full_name) > len(existing_full_name):
                            dep_dict[full_name] = (base_name, version)
                            base_to_full[base_name] = full_name
                            del dep_dict[existing_full_name]
    
    # 构建最终依赖列表
    merged_deps = []
    for full_name, (base_name, version) in sorted(dep_dict.items()):
        if version:
            merged_deps.append(f"{full_name}{version}")
        else:
            merged_deps.append(full_name)
    
    if conflicts:
        print("\n[WARN] 检测到以下依赖版本冲突（已选择更高版本）:")
        for name, old_ver, new_ver in conflicts:
            print(f"  {name}: {old_ver} -> {new_ver}")
        print()
    
    return merged_deps


def resolve_python_version(version_specs: list[str]) -> str:
    """
    解析多个 Python 版本要求，选择满足所有要求的最低版本。
    例如: [">=3.12", ">=3.13"] -> "3.13"
         [">=3.12,<3.13", ">=3.13"] -> "3.13" (冲突，选择更高的)
    """
    if not version_specs:
        return "3.12"  # 默认版本
    
    # 提取所有最低版本要求
    min_versions: list[float] = []
    max_versions: list[float | None] = []
    
    for spec in version_specs:
        if not spec:
            continue
        
        # 解析版本范围，如 ">=3.12,<3.13"
        parts = spec.split(",")
        min_ver = None
        max_ver = None
        
        for part in parts:
            part = part.strip()
            if part.startswith(">="):
                min_ver = float(part[2:].strip())
            elif part.startswith(">"):
                min_ver = float(part[1:].strip()) + 0.1
            elif part.startswith("<="):
                max_ver = float(part[2:].strip())
            elif part.startswith("<"):
                max_ver = float(part[1:].strip())
            elif part.startswith("=="):
                ver = float(part[2:].strip())
                min_ver = ver
                max_ver = ver
        
        if min_ver is not None:
            min_versions.append(min_ver)
        if max_ver is not None:
            max_versions.append(max_ver)
    
    if not min_versions:
        return "3.12"  # 默认版本
    
    # 选择最高的最低版本要求
    selected_min = max(min_versions)
    
    # 检查是否有最大版本限制冲突
    if max_versions:
        min_max = min([v for v in max_versions if v is not None])
        if selected_min >= min_max:
            # 冲突：最低要求 >= 最大限制，选择最低要求（向上兼容）
            print(f"[WARN] Python 版本要求冲突: 最低 {selected_min}, 最大 {min_max}")
            print(f"[INFO] 选择版本: {selected_min}")
            return str(int(selected_min)) if selected_min == int(selected_min) else str(selected_min)
    
    # 返回选择的版本（如果是整数则返回整数格式）
    version_str = str(int(selected_min)) if selected_min == int(selected_min) else str(selected_min)
    return version_str


def merge_pyproject_files(file_paths: list[Path]) -> dict[str, Any]:
    """
    合并多个 pyproject.toml 文件，返回合并后的配置。
    """
    all_configs = []
    python_versions = []
    
    print(f"[INFO] 解析 {len(file_paths)} 个 pyproject.toml 文件...")
    for file_path in file_paths:
        print(f"  - {file_path}")
        config = parse_pyproject_toml(file_path)
        all_configs.append(config)
        if config["requires_python"]:
            python_versions.append(config["requires_python"])
    
    # 合并 Python 版本要求
    selected_python = resolve_python_version(python_versions)
    print(f"[INFO] 选择的 Python 版本: {selected_python}")
    
    # 合并依赖
    all_dependencies = [config["dependencies"] for config in all_configs]
    merged_deps = merge_dependencies(all_dependencies)
    print(f"[INFO] 合并后共有 {len(merged_deps)} 个依赖包")
    
    return {
        "requires_python": selected_python,
        "dependencies": merged_deps,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="创建 Python Conda 环境并输出可离线安装的压缩包。支持多个 pyproject.toml 文件融合。"
    )
    parser.add_argument(
        "pyproject_files",
        nargs="+",
        type=Path,
        help="要融合的 pyproject.toml 文件路径（至少一个）。",
    )
    parser.add_argument(
        "--conda-exe",
        default=os.environ.get("CONDA_EXE", "conda"),
        help="Conda 可执行文件路径（默认读取 CONDA_EXE 或 conda）。",
    )
    parser.add_argument(
        "--uv-exe",
        default=os.environ.get("UV_EXE", "uv"),
        help="uv 可执行文件路径（默认读取 UV_EXE 或 uv）。",
    )
    parser.add_argument(
        "--env-name",
        default=None,
        help="新环境名称（默认：根据 Python 版本自动生成）。",
    )
    parser.add_argument(
        "--env-prefix",
        type=Path,
        help="自定义环境安装路径；缺省时自动放在 utils/python_offline_env/envs/<env-name>。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="离线压缩包输出路径；缺省为 dist/<env-name>.tar.gz。",
    )
    parser.add_argument(
        "--install-script",
        type=Path,
        help="信创电脑安装脚本输出路径；缺省为 dist/install_<env-name>.sh。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="若目标环境已存在则删除后重建。",
    )
    return parser.parse_args()


def ensure_env_absent(path: Path, force: bool) -> None:
    if not path.exists():
        return
    if not force:
        print(f"[SKIP] 环境已存在：{path}. 若需重建请添加 --force。")
        sys.exit(1)
    print(f"[CLEAN] 删除现有环境 {path}")
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        # 目录可能已经被删除或不存在，忽略错误
        print(f"[INFO] 环境目录已不存在，跳过删除")
    except Exception as e:
        print(f"[WARN] 使用 shutil.rmtree 删除失败: {e}")
        # 尝试使用系统命令强制删除（适用于 WSL 中 Windows 文件系统的锁定文件）
        print(f"[INFO] 尝试使用系统命令强制删除...")
        try:
            import platform
            if platform.system() == "Linux":
                # 在 Linux/WSL 中使用 rm -rf
                subprocess.run(["rm", "-rf", str(path)], check=True, timeout=60)
                print(f"[INFO] 使用 rm -rf 删除成功")
            else:
                # Windows 上使用 rmdir
                subprocess.run(["rmdir", "/s", "/q", str(path)], check=True, shell=True, timeout=60)
                print(f"[INFO] 使用 rmdir 删除成功")
        except Exception as e2:
            print(f"[ERROR] 无法删除环境目录: {e2}")
            print(f"[INFO] 请手动删除目录: {path}")
            print(f"[INFO] 然后重新运行脚本（不使用 --force）")
            sys.exit(1)


def generate_install_script(
    target: Path, tarball: Path, env_name: str, python_version: str
) -> None:
    script_content = f"""#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
TAR_FILE="${{1:-$SCRIPT_DIR/{tarball.name}}}"
TARGET_DIR="${{2:-$HOME/miniconda3/envs/{env_name}}}"
TARGET_PARENT="$(dirname "$TARGET_DIR")"
TARGET_NAME="$(basename "$TARGET_DIR")"

if [ ! -f "$TAR_FILE" ]; then
  echo "未找到压缩包: $TAR_FILE" >&2
  exit 1
fi

# 创建目标父目录
mkdir -p "$TARGET_PARENT"
rm -rf "$TARGET_PARENT/{env_name}"
rm -rf "$TARGET_DIR"

# 创建临时解压目录
TEMP_EXTRACT_DIR="$(mktemp -d)"
trap "rm -rf $TEMP_EXTRACT_DIR" EXIT

echo "[INFO] 解压 {tarball.name} 到临时目录"
tar -xzf "$TAR_FILE" -C "$TEMP_EXTRACT_DIR"

# 检查解压后的目录结构
# 如果使用了 --arcroot，解压后会有 {env_name} 目录
# 如果没有，解压后直接是环境文件
if [ -d "$TEMP_EXTRACT_DIR/{env_name}" ]; then
  # 使用了 --arcroot，解压后有目录层级
  SOURCE_DIR="$TEMP_EXTRACT_DIR/{env_name}"
  echo "[INFO] 检测到目录层级结构: {env_name}/"
else
  # 没有使用 --arcroot，解压后直接是环境文件
  SOURCE_DIR="$TEMP_EXTRACT_DIR"
  echo "[INFO] 检测到扁平结构，将移动到 {env_name} 目录"
  # 创建目录并移动文件
  mkdir -p "$TEMP_EXTRACT_DIR/{env_name}"
  mv "$TEMP_EXTRACT_DIR"/* "$TEMP_EXTRACT_DIR/{env_name}"/ 2>/dev/null || true
  mv "$TEMP_EXTRACT_DIR"/.[!.]* "$TEMP_EXTRACT_DIR/{env_name}"/ 2>/dev/null || true
  SOURCE_DIR="$TEMP_EXTRACT_DIR/{env_name}"
fi

# 移动到目标位置
echo "[INFO] 移动环境到目标位置: $TARGET_DIR"
mv "$SOURCE_DIR" "$TARGET_DIR"

echo "[INFO] 执行 conda-unpack 修正路径"
if [ -x "$TARGET_DIR/bin/conda-unpack" ]; then
  "$TARGET_DIR/bin/conda-unpack"
else
  echo "未找到 conda-unpack，可忽略或手动运行 pip install conda-pack && conda-unpack" >&2
fi

cat <<'EOF'
========================================================
环境已安装：
  路径: $TARGET_DIR
  Python: {python_version}

激活方式：
  source "$TARGET_DIR/bin/activate"

首次激活后建议运行：
  python -m ensurepip --upgrade
========================================================
EOF
"""
    target.write_text(script_content, encoding="utf-8")
    target.chmod(0o755)


def check_command_exists(cmd: str) -> bool:
    """检查命令是否存在。"""
    try:
        subprocess.run(
            [cmd, "--version"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, PermissionError, OSError):
        return False


def detect_platform() -> str:
    """检测当前运行平台。"""
    import platform
    system = platform.system().lower()
    if "linux" in system:
        # 检查是否在 WSL 中
        try:
            with open("/proc/version", "r") as f:
                version_info = f.read().lower()
                if "microsoft" in version_info or "wsl" in version_info:
                    return "wsl"
        except (FileNotFoundError, PermissionError):
            pass
        return "linux"
    elif "windows" in system:
        return "windows"
    elif "darwin" in system:
        return "macos"
    return "unknown"


def main() -> None:
    args = parse_args()
    
    # 检测平台
    platform = detect_platform()
    print(f"[INFO] 检测到平台: {platform}")
    
    if platform == "windows":
        print(f"[WARN] 在 Windows 上构建的环境包含 Windows 特定文件（.dll, .exe）")
        print(f"[WARN] 如果目标环境是 Linux，建议在 WSL 或 Linux 系统中构建")
        response = input("[INFO] 是否继续？(y/N): ").strip().lower()
        if response != "y":
            print("[INFO] 已取消构建")
            sys.exit(0)
    
    # 检查必需的工具
    print("[CHECK] 检查必需工具...")
    if not check_command_exists(args.conda_exe):
        print(f"[ERROR] Conda 未找到，请确保已安装 Conda 并添加到 PATH")
        sys.exit(1)
    print(f"  ✓ Conda: {args.conda_exe}")
    
    if not check_command_exists(args.uv_exe):
        print(f"[ERROR] uv 未找到，请先安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)
    print(f"  ✓ uv: {args.uv_exe}")
    
    # 解析并合并 pyproject.toml 文件
    print("\n[MERGE] 合并 pyproject.toml 文件...")
    merged_config = merge_pyproject_files(args.pyproject_files)
    python_version = merged_config["requires_python"]
    dependencies = merged_config["dependencies"]
    
    # 确定环境名称
    env_name = args.env_name or f"py{python_version.replace('.', '')}_offline"
    
    # 确定路径
    env_path = Path(args.env_prefix) if args.env_prefix else (DEFAULT_ENV_ROOT / env_name)
    env_path = env_path.resolve()
    tar_path = args.output.resolve() if args.output else (DEFAULT_DIST_DIR / f"{env_name}.tar.gz")
    install_script_path = (
        args.install_script.resolve()
        if args.install_script
        else (tar_path.parent / f"install_{env_name}.sh")
    )

    tar_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_env_absent(env_path, args.force)
    env_path.parent.mkdir(parents=True, exist_ok=True)

    # 创建 Conda 环境
    print(f"\n[CONDA] 创建 Python {python_version} 环境...")
    run(
        [
            args.conda_exe,
            "create",
            "-y",
            "-p",
            str(env_path),
            f"python={python_version}",
        ]
    )
    
    # 在新建的环境中安装 uv（如果系统中没有或无法访问）
    print(f"\n[INSTALL] 在环境中安装 uv...")
    try:
        # 先尝试使用 pip 安装 uv
        run(
            [
                args.conda_exe,
                "run",
                "-p",
                str(env_path),
                "pip",
                "install",
                "uv",
            ]
        )
        # 如果成功，使用环境中的 uv
        uv_cmd = "uv"
    except subprocess.CalledProcessError:
        # 如果失败，尝试使用系统路径中的 uv
        print(f"[WARN] 无法在环境中安装 uv，尝试使用系统 uv")
        uv_cmd = args.uv_exe
    
    # 使用 uv 安装依赖
    print(f"\n[UV] 使用 uv 安装 {len(dependencies)} 个依赖包...")
    
    # 保存 requirements.txt 文件以便追溯（不删除）
    requirements_file = tar_path.parent / f"{env_name}_requirements.txt"
    requirements_file.write_text("\n".join(dependencies), encoding="utf-8")
    print(f"[INFO] 依赖列表已保存到: {requirements_file}")
    
    # 使用 uv 在 Conda 环境中安装依赖
    # uv 需要在激活的环境中运行，所以我们使用 conda run
    run(
        [
            args.conda_exe,
            "run",
            "-p",
            str(env_path),
            uv_cmd,
            "pip",
            "install",
            "--system",
            "-r",
            str(requirements_file),
        ]
    )
    
    # 尝试生成 lockfile（如果 uv 支持）
    print(f"\n[LOCK] 生成依赖锁定文件...")
    lockfile_path = tar_path.parent / f"{env_name}_uv.lock"
    lockfile_generated = False
    
    try:
        # 尝试使用 uv lock 生成 lockfile
        # 注意：这需要在项目目录中运行，所以我们需要创建一个临时的 pyproject.toml
        temp_pyproject = tar_path.parent / f"{env_name}_pyproject.toml"
        
        # 格式化依赖列表为 TOML 数组格式
        deps_toml = "[\n"
        for dep in dependencies:
            deps_toml += f'    "{dep}",\n'
        deps_toml = deps_toml.rstrip(",\n") + "\n]"
        
        temp_pyproject.write_text(
            f"""[project]
name = "{env_name}"
version = "0.1.0"
requires-python = ">={python_version}"
dependencies = {deps_toml}
""",
            encoding="utf-8",
        )
        
        # 在 conda 环境中运行 uv lock
        # 注意：uv lock 需要在包含 pyproject.toml 的目录中运行
        run(
            [
                args.conda_exe,
                "run",
                "-p",
                str(env_path),
                uv_cmd,
                "lock",
                "--directory",
                str(temp_pyproject.parent),
            ]
        )
        
        # 检查是否生成了 lockfile（通常在项目根目录）
        potential_lockfile = temp_pyproject.parent / "uv.lock"
        if potential_lockfile.exists():
            potential_lockfile.rename(lockfile_path)
            lockfile_generated = True
            print(f"[INFO] Lockfile 已生成: {lockfile_path}")
        else:
            print(f"[WARN] uv lock 未生成预期的 lockfile")
    except (subprocess.CalledProcessError, FileNotFoundError, Exception) as e:
        print(f"[WARN] 无法生成 lockfile: {e}")
        print(f"[INFO] 将使用 requirements.txt 作为依赖记录")
    
    # 修复 conda 环境（解决 pip 覆盖 conda 文件的问题）
    # 必须在清理之前修复，避免 conda-pack 报错
    print(f"\n[FIX] 修复 conda 环境一致性...")
    print(f"[INFO] 重新安装被覆盖的 conda 包...")
    
    # 先修复被覆盖的包（使用 conda install 而不是 pip）
    fix_packages = ["python", "setuptools", "wheel"]
    if platform in ["wsl", "linux"]:
        fix_packages.append("ncurses")
    
    for pkg in fix_packages:
        try:
            print(f"[INFO] 修复 {pkg}...")
            # 先尝试使用 conda install --force-reinstall
            run(
                [
                    args.conda_exe,
                    "install",
                    "-p",
                    str(env_path),
                    "--force-reinstall",
                    "-y",
                    pkg,
                ]
            )
            print(f"[INFO] {pkg} 修复成功")
        except subprocess.CalledProcessError as e:
            print(f"[WARN] 无法修复 {pkg}: {e}")
            # 尝试使用 --no-deps 选项
            try:
                run(
                    [
                        args.conda_exe,
                        "install",
                        "-p",
                        str(env_path),
                        "--force-reinstall",
                        "-y",
                        "--no-deps",
                        pkg,
                    ]
                )
                print(f"[INFO] {pkg} 修复成功（无依赖）")
            except subprocess.CalledProcessError:
                print(f"[WARN] 无法修复 {pkg}，将在打包时使用 --ignore-missing-files")
    
    # 不清理缓存，避免触发 conda-pack 的错误
    # conda-pack 会检查文件完整性，删除缓存可能导致检查失败
    print(f"\n[INFO] 跳过缓存清理，保持环境完整性")
    
    # 安装 conda-pack 用于打包
    print(f"\n[INSTALL] 安装 conda-pack...")
    run(
        [
            args.conda_exe,
            "run",
            "-p",
            str(env_path),
            uv_cmd,
            "pip",
            "install",
            "--system",
            "conda-pack",
        ]
    )

    # 打包环境（使用 --arcroot 参数，让解压后有一个目录层级）
    print(f"\n[PACK] 打包环境到 {tar_path}...")
    print(f"[INFO] 使用 --arcroot 参数，解压后将在 {env_name} 目录中")
    
    # 使用 --arcroot 参数，让 tar.gz 解压后有一个目录层级
    # 这样解压时不会直接解压到当前目录，而是解压到 env_name 目录中
    # 直接运行 conda-pack（不使用 conda run），避免环境检查错误
    import os
    conda_pack_exe = env_path / "bin" / "conda-pack"
    if not conda_pack_exe.exists():
        # 如果在 Windows 上，可能是 Scripts/conda-pack.exe
        conda_pack_exe = env_path / "Scripts" / "conda-pack.exe"
    
    pack_success = False
    if conda_pack_exe.exists():
        # 直接运行 conda-pack，避免 conda run 的环境检查
        # 使用 --ignore-editable-packages 和 --ignore-errors 选项
        env = os.environ.copy()
        env["CONDA_PREFIX"] = str(env_path)
        
        # 尝试多种方式打包
        pack_attempts = [
            # 方式1：使用 --arcroot、--ignore-editable-packages 和 --ignore-missing-files
            [
                str(conda_pack_exe),
                "-p", str(env_path),
                "-o", str(tar_path),
                "--arcroot", env_name,
                "--ignore-editable-packages",
                "--ignore-missing-files",
            ],
            # 方式2：使用 --arcroot 和 --ignore-missing-files
            [
                str(conda_pack_exe),
                "-p", str(env_path),
                "-o", str(tar_path),
                "--arcroot", env_name,
                "--ignore-missing-files",
            ],
            # 方式3：只使用 --arcroot 和 --ignore-editable-packages
            [
                str(conda_pack_exe),
                "-p", str(env_path),
                "-o", str(tar_path),
                "--arcroot", env_name,
                "--ignore-editable-packages",
            ],
            # 方式4：只使用 --arcroot
            [
                str(conda_pack_exe),
                "-p", str(env_path),
                "-o", str(tar_path),
                "--arcroot", env_name,
            ],
            # 方式5：不使用 --arcroot，后续手动添加
            [
                str(conda_pack_exe),
                "-p", str(env_path),
                "-o", str(tar_path),
                "--ignore-missing-files",
            ],
        ]
        
        for i, pack_cmd in enumerate(pack_attempts, 1):
            try:
                print(f"[INFO] 尝试打包方式 {i}...")
                subprocess.run(pack_cmd, check=True, env=env, capture_output=True)
                pack_success = True
                
                # 如果方式5成功，需要手动添加目录层级
                if i == 5:
                    print(f"[INFO] 重新打包以添加目录层级...")
                    import tempfile
                    import tarfile
                    temp_tar = tar_path.parent / f"{tar_path.stem}_temp.tar.gz"
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_env_dir = Path(temp_dir) / env_name
                        temp_env_dir.mkdir()
                        with tarfile.open(tar_path, "r:gz") as tar:
                            tar.extractall(temp_env_dir)
                        with tarfile.open(temp_tar, "w:gz") as tar:
                            tar.add(temp_env_dir, arcname=env_name)
                        temp_tar.replace(tar_path)
                    print(f"[INFO] 已重新打包，添加目录层级 {env_name}/")
                else:
                    print(f"[INFO] 使用 --arcroot 参数打包成功")
                break
            except subprocess.CalledProcessError as e:
                if i < len(pack_attempts):
                    print(f"[WARN] 方式 {i} 失败，尝试下一种方式...")
                    continue
                else:
                    print(f"[ERROR] 所有打包方式都失败")
                    # 输出错误信息
                    if e.stderr:
                        print(f"[ERROR] 错误信息: {e.stderr.decode('utf-8', errors='ignore')}")
                    raise
    else:
        # 如果找不到 conda-pack，使用 conda run（可能报错但尝试）
        print(f"[WARN] 未找到 conda-pack 可执行文件，使用 conda run")
        pack_cmd = [
            args.conda_exe,
            "run",
            "-p",
            str(env_path),
            "conda-pack",
            "-p",
            str(env_path),
            "-o",
            str(tar_path),
            "--arcroot",
            env_name,
        ]
        try:
            run(pack_cmd)
            pack_success = True
        except subprocess.CalledProcessError:
            # 如果失败，尝试不使用 --arcroot，然后手动添加
            pack_cmd_simple = [
                args.conda_exe,
                "run",
                "-p",
                str(env_path),
                "conda-pack",
                "-p",
                str(env_path),
                "-o",
                str(tar_path),
            ]
            run(pack_cmd_simple)
            # 手动添加目录层级
            import tempfile
            import tarfile
            temp_tar = tar_path.parent / f"{tar_path.stem}_temp.tar.gz"
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_env_dir = Path(temp_dir) / env_name
                temp_env_dir.mkdir()
                with tarfile.open(tar_path, "r:gz") as tar:
                    tar.extractall(temp_env_dir)
                with tarfile.open(temp_tar, "w:gz") as tar:
                    tar.add(temp_env_dir, arcname=env_name)
                temp_tar.replace(tar_path)
            pack_success = True
            print(f"[INFO] 已重新打包，添加目录层级 {env_name}/")
    
    if not pack_success:
        raise RuntimeError("打包失败，请检查环境状态")

    # 生成安装脚本
    print(f"\n[SCRIPT] 生成安装脚本...")
    generate_install_script(install_script_path, tar_path, env_name, python_version)
    
    # 生成依赖清单文件
    import datetime
    manifest_file = tar_path.parent / f"{env_name}_manifest.txt"
    build_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write(f"Python 版本: {python_version}\n")
        f.write(f"环境名称: {env_name}\n")
        f.write(f"构建时间: {build_time}\n")
        f.write(f"\n依赖包列表 ({len(dependencies)} 个):\n")
        f.write("=" * 60 + "\n")
        for dep in sorted(dependencies):
            f.write(f"  - {dep}\n")
        f.write("\n")
        f.write("文件清单:\n")
        f.write("=" * 60 + "\n")
        f.write(f"  - {tar_path.name} (环境压缩包)\n")
        f.write(f"  - {install_script_path.name} (安装脚本)\n")
        f.write(f"  - {requirements_file.name} (依赖列表)\n")
        if lockfile_generated and lockfile_path.exists():
            f.write(f"  - {lockfile_path.name} (锁定文件)\n")
    
    print(f"[INFO] 依赖清单已生成: {manifest_file}")
    
    # 计算并显示打包大小
    tar_size_mb = tar_path.stat().st_size / (1024 * 1024)
    print(f"\n[DONE] 离线环境已打包：{tar_path}")
    print(f"[DONE] 打包大小: {tar_size_mb:.2f} MB")
    print(f"[DONE] 安装脚本已生成：{install_script_path}")
    print(f"[DONE] 依赖清单已生成：{manifest_file}")
    print(f"\n合并的依赖包列表 ({len(dependencies)} 个):")
    for dep in sorted(dependencies):
        print(f"  - {dep}")


if __name__ == "__main__":
    main()

