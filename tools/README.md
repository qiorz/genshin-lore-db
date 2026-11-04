# tools · 本地工具链

这个目录放便携工具，**不提交到版本库**。当前已安装：

```text
tools/python/python.exe    Python 3.13.17（embeddable + pip）
tools/sqlite/sqlite3.exe   SQLite 3.54.1 CLI
```

Python 包：

```text
requests beautifulsoup4 markdownify PyYAML jieba jsonschema mwparserfromhell
```

## 使用

```powershell
.\tools\python\python.exe --version
.\tools\python\python.exe -m pip list
.\tools\python\python.exe scripts\fetch_obc.py --entry-page-id 399 --force
.\tools\python\python.exe scripts\search.py 钟离
```

## 说明

- `tools/python` 是隔离环境，不依赖系统 Python，也不改系统 PATH；
- 如果需要重装 pip：

```powershell
.\tools\python\python.exe <path-to-get-pip.py>
```

- 在这台机器上，pip 的默认缓存目录曾被拒绝写入；遇到 wheel 构建失败时用：

```powershell
.\tools\python\python.exe -m pip install --no-cache-dir <package>
```

- 不用把 `tools/`、`.venv/` 提交到 git；
- 不把 Cookie/Token 写进脚本；
- 升级 Python/包后，重跑：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_env.ps1
```
