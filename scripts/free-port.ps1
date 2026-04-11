param(
  [Parameter(Mandatory = $true)]
  [int]$Port
)

$ErrorActionPreference = 'Stop'

function Get-PortProcessIds {
  param([int]$TargetPort)

  $output = cmd.exe /c ('netstat -ano | findstr ":{0}"' -f $TargetPort) 2>$null
  if (-not $output) {
    return @()
  }

  $processIds = @()
  foreach ($line in ($output -split "`r?`n")) {
    $trimmed = $line.Trim()
    if (-not $trimmed) {
      continue
    }

    $parts = $trimmed -split '\s+'
    if ($parts.Length -lt 5) {
      continue
    }

    $processId = $parts[-1]
    if ($processId -match '^\d+$') {
      $processIds += [int]$processId
    }
  }

  return $processIds | Sort-Object -Unique
}

$pids = Get-PortProcessIds -TargetPort $Port
if (-not $pids.Count) {
  Write-Host "[free-port] Port $Port is free."
  exit 0
}

foreach ($processId in $pids) {
  Write-Host "[free-port] Killing PID $processId on port $Port"
  taskkill /F /PID $processId | Out-Null
}

Write-Host "[free-port] Port $Port cleaned."
