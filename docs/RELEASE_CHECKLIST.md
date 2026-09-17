# GitHub Release 发布检查清单

## 发布前

- [ ] 确认仓库根目录已经添加符合预期的 `LICENSE`。
- [ ] 检查 `git status`，不要提交 `settings.ini`、`settings.json`、日志、仿真文件或许可证信息。
- [ ] 检查 README 截图中没有真实科研路径或未公开数据。
- [ ] 更新 `version_info.txt` 中的版本号。

## 测试

```powershell
.\.build-venv\Scripts\python.exe -m unittest discover -s .\tests -v
.\.build-venv\Scripts\python.exe .\lumerical_runner_zh.py --self-test
.\.build-venv\Scripts\python.exe .\lumerical_runner_zh.py --gui-smoke-test
```

- [ ] 所有单元测试通过。
- [ ] GUI 可以启动和退出，无残留进程。
- [ ] 浅色、深色和窄窗口布局检查正常。
- [ ] 未在测试阶段启动真实 FDTD 或占用许可证。

## 构建

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

- [ ] `release\FDTD无界面一键运行.exe` 已生成。
- [ ] EXE 版本信息、产品名称和图标正确。
- [ ] `release\SHA256.txt` 与 EXE 实际哈希一致。
- [ ] 保留测试用的空白配置，不把个人 `settings.ini` 放进发布包。

## GitHub Release

建议为每个版本创建 Git tag，例如 `v2.0.0`，并在 GitHub Release 中上传：

```text
FDTD无界面一键运行.exe
SHA256.txt
README.md
```

Release notes 至少说明：

- 版本号与发布日期；
- 主要新增功能和修复；
- 支持的 Windows/Python 范围；
- 是否改变 FDTD 命令参数或停止机制；
- 已知限制；
- 本次验证是否包含真实 FDTD 仿真。
