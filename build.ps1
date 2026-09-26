$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Create .venv and install PyInstaller first: py -m venv .venv; .\.venv\Scripts\python.exe -m pip install pyinstaller'
}
Push-Location $PSScriptRoot
try {
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & $python -m PyInstaller --noconfirm --clean --onefile --console `
        --name MoonlightDeckMode --icon icons\SteamDeck.ico `
        --add-data 'icons\SteamDeckMoonlight.png;icons' deckmode.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    & (Join-Path $PSScriptRoot 'dist\MoonlightDeckMode.exe') --version
    if ($LASTEXITCODE -ne 0) { throw 'Executable smoke test failed.' }
}
finally {
    Pop-Location
}
