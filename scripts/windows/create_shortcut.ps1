$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Desktop = [Environment]::GetFolderPath("Desktop")

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut((Join-Path $Desktop "Paper Assistant.lnk"))
$Shortcut.TargetPath = Join-Path $ProjectRoot "start.bat"
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = "Paper Assistant"
$Shortcut.IconLocation = "C:\Windows\System32\shell32.dll,269"
$Shortcut.Save()
