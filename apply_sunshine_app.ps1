# Run through Windows UAC once to save the Sunshine app and reload the service.
$ErrorActionPreference = 'Stop'
$logPath = Join-Path $PSScriptRoot 'sunshine-install.log'
Start-Transcript -LiteralPath $logPath -Force | Out-Null
try {
    & 'C:\Windows\py.exe' -B (Join-Path $PSScriptRoot 'install_sunshine_app.py')
    if ($LASTEXITCODE -ne 0) {
        throw "Sunshine app installer exited with code $LASTEXITCODE"
    }
    Restart-Service -Name SunshineService -Force
    $service = Get-Service -Name SunshineService
    if ($service.Status -ne 'Running') {
        throw "Sunshine service status after reload: $($service.Status)"
    }
    $apps = Get-Content -LiteralPath 'C:\Program Files\Sunshine\config\apps.json' -Raw | ConvertFrom-Json
    if (-not ($apps.apps | Where-Object { $_.name -eq 'Steam Deck' })) {
        throw 'Steam Deck app was not present after Sunshine reload.'
    }
    Write-Output 'Sunshine Steam Deck app installed; Sunshine service running.'
}
catch {
    Write-Error $_
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
