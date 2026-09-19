# JSON Schemas

这些文件由后端 Pydantic 领域模型生成，不手工修改。

```powershell
.\.venv\Scripts\python.exe -m app.schema_export
```

运行命令时，工作目录应为 `backend/`，或设置 `PYTHONPATH=backend`。CI 会重新生成 Schema 并检查 Git 差异，避免模型与契约漂移。
