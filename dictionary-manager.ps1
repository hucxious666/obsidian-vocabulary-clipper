[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pythonPathFile = Join-Path $root 'python-path.txt'
if (Test-Path -LiteralPath $pythonPathFile) {
    $pythonPath = (Get-Content -Raw -LiteralPath $pythonPathFile).Trim()
}
else {
    $pythonPath = (Get-Command python -ErrorAction Stop).Source
}

& $pythonPath -m clipper.dictionary_manager_gui `
    --catalog (Join-Path $root 'dictionary-catalog.json') `
    --target (Join-Path $root 'data\dictionaries')
exit $LASTEXITCODE
