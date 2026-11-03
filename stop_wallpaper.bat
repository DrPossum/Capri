@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -match '^(pythonw?|pyw?)\.exe$') -and ($_.CommandLine -match '--wallpaper') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
