param([switch]$SetupOnly, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
# Newly installed programs may not be in this terminal's PATH yet.
if (Test-Path "$env:ProgramFiles\nodejs\node.exe") { $env:Path = "$env:ProgramFiles\nodejs;$env:Path" }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js first: winget install --id OpenJS.NodeJS.LTS --exact --source winget' }
$pythonExe = $null
foreach ($candidate in @("$env:LOCALAPPDATA\Programs\Python\Python314\python.exe", "$env:ProgramFiles\Python314\python.exe")) {
    if (Test-Path $candidate) { $pythonExe = $candidate; break }
}
if (-not $pythonExe) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*WindowsApps*') { $pythonExe = $pythonCommand.Source }
}
if (-not $pythonExe) { throw 'Install Python first: winget install --id Python.Python.3.14 --exact --source winget' }
$nativeArgs = @('scripts/run_native.py')
if ($SetupOnly) { $nativeArgs += '--setup-only' }
if ($NoBrowser) { $nativeArgs += '--no-browser' }
& $pythonExe @nativeArgs
if ($LASTEXITCODE -ne 0) { throw 'Carepoint stopped. See the error above.' }
