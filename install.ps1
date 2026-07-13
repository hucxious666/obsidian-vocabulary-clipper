[CmdletBinding()]
param(
    [switch]$SkipDictionary,
    [switch]$NoOpenChrome
)

$ErrorActionPreference = 'Stop'
$HOST_NAME = 'com.local.obsidian_vocabulary_clipper'
$EXTENSION_ID = 'mmjlnnjlmoladaommpnekimbpfmfdnmj'

function Write-Utf8NoBom {
    param([string]$Path, [string]$Value)
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Value, $encoding)
}

function Copy-ApplicationFiles {
    param([string]$SourceRoot, [string]$AppDirectory, [string]$PythonPath)

    New-Item -ItemType Directory -Path $AppDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $AppDirectory 'data\dictionaries') -Force | Out-Null
    Remove-Item -LiteralPath (Join-Path $AppDirectory 'clipper') -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $AppDirectory 'extension') -Recurse -Force -ErrorAction SilentlyContinue
    foreach ($file in @(
        'native_host.py', 'host.bat', 'dictionary-manager.ps1', 'dictionary-catalog.json',
        'ECDICT-LICENSE.txt', 'THIRD_PARTY_NOTICES.md'
    )) {
        Copy-Item -LiteralPath (Join-Path $SourceRoot $file) -Destination $AppDirectory -Force
    }
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'data\SOURCE.txt') -Destination (Join-Path $AppDirectory 'data') -Force
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'clipper') -Destination $AppDirectory -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'extension') -Destination $AppDirectory -Recurse -Force
    Write-Utf8NoBom -Path (Join-Path $AppDirectory 'python-path.txt') -Value $PythonPath
}

function Register-NativeHost {
    param([string]$AppDirectory)

    $manifestPath = Join-Path $AppDirectory "$HOST_NAME.json"
    $manifest = [ordered]@{
        name = $HOST_NAME
        description = 'Obsidian Vocabulary Clipper local host'
        path = (Join-Path $AppDirectory 'host.bat')
        type = 'stdio'
        allowed_origins = @("chrome-extension://$EXTENSION_ID/")
    }
    Write-Utf8NoBom -Path $manifestPath -Value ($manifest | ConvertTo-Json -Depth 4)

    $registryPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HOST_NAME"
    New-Item -Path $registryPath -Force | Out-Null
    Set-Item -Path $registryPath -Value $manifestPath
}

function Open-DictionaryManager {
    param([string]$AppDirectory)
    $script = Join-Path $AppDirectory 'dictionary-manager.ps1'
    Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script
    )
}

$sourceRoot = $PSScriptRoot
$installRoot = Join-Path $env:LOCALAPPDATA 'ObsidianVocabularyClipper'
$appDirectory = Join-Path $installRoot 'app'
$pythonPath = (Get-Command python -ErrorAction Stop).Source
$versionOk = & $pythonPath -c "import sys; print(int(sys.version_info >= (3, 11)))"
if ($versionOk -ne '1') { throw 'Python 3.11 or newer is required' }

Copy-ApplicationFiles -SourceRoot $sourceRoot -AppDirectory $appDirectory -PythonPath $pythonPath
Register-NativeHost -AppDirectory $appDirectory
if (-not $SkipDictionary) { Open-DictionaryManager -AppDirectory $appDirectory }

$extensionPath = Join-Path $appDirectory 'extension'
Write-Host ''
Write-Host 'Installation completed.' -ForegroundColor Green
Write-Host "Extension directory: $extensionPath"
Write-Host "Extension ID: $EXTENSION_ID"
Write-Host 'Dictionaries are downloaded on demand and are never copied from the Git repository.'
Write-Host 'Open chrome://extensions, enable Developer mode, click Load unpacked, and select the extension directory above.'
Write-Host 'Then open extension options, choose an installed dictionary, and configure translation credentials.'

if (-not $NoOpenChrome) {
    $chromeCandidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    $chrome = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($chrome) { Start-Process -FilePath $chrome -ArgumentList 'chrome://extensions' }
}
