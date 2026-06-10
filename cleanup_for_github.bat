@echo off
echo ========================================
echo GitHub 上传前清理脚本
echo ========================================
echo.

echo [安全检查] 此脚本不会复制或删除 .env
echo 它只删除本地数据中的敏感配置，并检查敏感文件是否被 Git 忽略
echo.
pause

echo.
echo [1/4] 检查 .env 是否被 Git 忽略...
if exist .env (
    git check-ignore -q .env
    if errorlevel 1 (
        echo     [错误] .env 未被 Git 忽略，请勿上传！
        exit /b 1
    )
    echo     .env 已被 Git 忽略，不复制、不删除
) else (
    echo     .env 文件不存在，跳过
)

echo.
echo [2/4] 删除敏感文件...
if exist data\secrets.json del /f data\secrets.json
if exist data\chat_engines.json del /f data\chat_engines.json
if exist data\settings.json del /f data\settings.json
if exist data\translation_engines.json del /f data\translation_engines.json
echo     已删除敏感文件

echo.
echo [3/4] 创建模板文件...
echo # === AI Model Configuration === > .env.example
echo # Get your API key from: https://platform.openai.com/api-keys >> .env.example
echo LLM_API_KEY=sk-your-api-key-here >> .env.example
echo LLM_BASE_URL=https://api.openai.com/v1 >> .env.example
echo LLM_MODEL=gpt-4o-mini >> .env.example
echo LLM_TEMPERATURE=0.3 >> .env.example
echo. >> .env.example
echo # === Optional Providers === >> .env.example
echo NVIDIA_API_KEY= >> .env.example
echo NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1 >> .env.example
echo DEEPSEEK_API_KEY= >> .env.example
echo DEEPSEEK_BASE_URL=https://api.deepseek.com/v1 >> .env.example
echo     已创建 .env.example

echo.
echo [4/4] 完成！
echo.
echo 下一步：
echo 1. 检查 .gitignore 是否包含所有敏感文件
echo 2. 轮换所有已泄露的 API keys
echo 3. 运行 git status 确认没有敏感文件或 .env 备份
echo 4. 提交并推送到 GitHub
echo.
pause
