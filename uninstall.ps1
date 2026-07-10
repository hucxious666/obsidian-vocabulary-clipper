[CmdletBinding()]
param([switch]$Purge)

$ErrorActionPreference = 'Stop'
$HOST_NAME = 'com.local.obsidian_vocabulary_clipper'
$installRoot = Join-Path $env:LOCALAPPDATA 'ObsidianVocabularyClipper'
$appDirectory = Join-Path $installRoot 'app'
$registryPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HOST_NAME"

Remove-Item -ErrorAction SilentlyContinue -Path $registryPath -Recurse -Force
if (Test-Path -LiteralPath $appDirectory) {
    Remove-Item -LiteralPath $appDirectory -Recurse -Force
}
if ($Purge -and (Test-Path -LiteralPath $installRoot)) {
    Remove-Item -LiteralPath $installRoot -Recurse -Force
    Write-Host 'Uninstalled and removed configuration and backups.'
}
else {
    Write-Host 'Program removed. Configuration and backups were preserved. Use -Purge to remove them.'
}
Write-Host 'Remove Obsidian Vocabulary Clipper from chrome://extensions.'
