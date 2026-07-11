[CmdletBinding()]
param(
    [switch]$SkipDictionary,
    [switch]$NoOpenChrome
)

$ErrorActionPreference = 'Stop'
$EXPECTED_ECDICT_SHA256 = '1a6947e04785db63613a92e14903cdae7954f7e84860b10e68e5c7cbb3f9c3cf'
$ECDICT_URL = 'https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv'
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
    New-Item -ItemType Directory -Path (Join-Path $AppDirectory 'data') -Force | Out-Null
    Remove-Item -LiteralPath (Join-Path $AppDirectory 'clipper') -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $AppDirectory 'extension') -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'native_host.py') -Destination $AppDirectory -Force
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'host.bat') -Destination $AppDirectory -Force
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'ECDICT-LICENSE.txt') -Destination $AppDirectory -Force
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'THIRD_PARTY_NOTICES.md') -Destination $AppDirectory -Force
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'data\SOURCE.txt') -Destination (Join-Path $AppDirectory 'data') -Force
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'clipper') -Destination $AppDirectory -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'extension') -Destination $AppDirectory -Recurse -Force
    Write-Utf8NoBom -Path (Join-Path $AppDirectory 'python-path.txt') -Value $PythonPath
}

function Install-Dictionary {
    param([string]$SourceRoot, [string]$AppDirectory, [string]$PythonPath)

    $destination = Join-Path $AppDirectory 'data\ecdict.sqlite3'
    $packaged = Join-Path $SourceRoot 'data\ecdict.sqlite3'
    if (Test-Path -LiteralPath $packaged) {
        Copy-Item -LiteralPath $packaged -Destination $destination -Force
        return
    }
    if ($SkipDictionary) {
        Write-Warning 'Offline dictionary skipped. Lookup will fail until it is installed.'
        return
    }

    $download = Join-Path ([IO.Path]::GetTempPath()) 'obsidian-vocabulary-ecdict.csv'
    try {
        & curl.exe --location --fail --retry 3 --connect-timeout 20 --output $download $ECDICT_URL
        if ($LASTEXITCODE -ne 0) { throw 'ECDICT download failed' }
        $actualHash = (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $EXPECTED_ECDICT_SHA256) {
            throw "ECDICT hash mismatch. Expected $EXPECTED_ECDICT_SHA256, got $actualHash"
        }
        & $PythonPath -m clipper.dictionary_builder $download $destination
        if ($LASTEXITCODE -ne 0) { throw 'ECDICT SQLite build failed' }
    }
    finally {
        Remove-Item -LiteralPath $download -Force -ErrorAction SilentlyContinue
    }
}

function Register-NativeHost {
    param([string]$AppDirectory)

    $manifestPath = Join-Path $AppDirectory "$HOST_NAME.json"
    $hostPath = (Join-Path $AppDirectory 'host.bat')
    $manifest = [ordered]@{
        name = $HOST_NAME
        description = 'Obsidian Vocabulary Clipper local host'
        path = $hostPath
        type = 'stdio'
        allowed_origins = @("chrome-extension://$EXTENSION_ID/")
    }
    Write-Utf8NoBom -Path $manifestPath -Value ($manifest | ConvertTo-Json -Depth 4)

    $registryPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HOST_NAME"
    New-Item -Path $registryPath -Force | Out-Null
    Set-Item -Path $registryPath -Value $manifestPath
}

$sourceRoot = $PSScriptRoot
$installRoot = Join-Path $env:LOCALAPPDATA 'ObsidianVocabularyClipper'
$appDirectory = Join-Path $installRoot 'app'
$pythonCommand = Get-Command python -ErrorAction Stop
$pythonPath = $pythonCommand.Source
$versionOk = & $pythonPath -c "import sys; print(int(sys.version_info >= (3, 11)))"
if ($versionOk -ne '1') { throw 'Python 3.11 or newer is required' }

Copy-ApplicationFiles -SourceRoot $sourceRoot -AppDirectory $appDirectory -PythonPath $pythonPath
Push-Location $appDirectory
try {
    Install-Dictionary -SourceRoot $sourceRoot -AppDirectory $appDirectory -PythonPath $pythonPath
}
finally {
    Pop-Location
}
Register-NativeHost -AppDirectory $appDirectory

$extensionPath = Join-Path $appDirectory 'extension'
Write-Host ''
Write-Host 'Installation completed.' -ForegroundColor Green
Write-Host "Extension directory: $extensionPath"
Write-Host "Extension ID: $EXTENSION_ID"
Write-Host 'Open chrome://extensions, enable Developer mode, click Load unpacked, and select the extension directory above.'
Write-Host 'Then open extension options, configure Baidu credentials, and optionally configure Youdao translation credentials.'

if (-not $NoOpenChrome) {
    $chromeCandidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    $chrome = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($chrome) { Start-Process -FilePath $chrome -ArgumentList 'chrome://extensions' }
}
