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

$pythonwPath = Join-Path (Split-Path -Parent $pythonPath) 'pythonw.exe'
$managerPython = if (Test-Path -LiteralPath $pythonwPath) { $pythonwPath } else { $pythonPath }
$catalog = '"{0}"' -f (Join-Path $root 'dictionary-catalog.json')
$target = '"{0}"' -f (Join-Path $root 'data\dictionaries')
Start-Process -FilePath $managerPython -WorkingDirectory $root -ArgumentList @(
    '-m', 'clipper.dictionary_manager_gui', '--catalog', $catalog, '--target', $target
)
exit 0
