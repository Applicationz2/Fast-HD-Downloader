$ErrorActionPreference = 'Stop'
$folder = Join-Path $PSScriptRoot 'fastdl'
$exe = Join-Path $folder 'fstdl.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Extract the entire Lite ZIP before registering.' }
$old = [Environment]::GetEnvironmentVariable('Path', 'User')
$parts = @($old -split ';' | Where-Object { $_ })
if ($parts -notcontains $folder) {
    [Environment]::SetEnvironmentVariable('Path', (($parts + $folder) -join ';'), 'User')
}
Write-Host 'Registered fstdl. Close and reopen CMD or Windows Terminal. Run fstdl.'
