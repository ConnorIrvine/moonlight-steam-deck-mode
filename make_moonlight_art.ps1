# Regenerate the custom 600x800 cover shown for this app in Moonlight.
Add-Type -AssemblyName System.Drawing

$outputPath = Join-Path $PSScriptRoot 'icons\SteamDeckMoonlight.png'
$iconPath = Join-Path $PSScriptRoot 'icons\SteamDeck.png'
$bitmap = New-Object System.Drawing.Bitmap 600, 800
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

$background = New-Object System.Drawing.Drawing2D.LinearGradientBrush (
    [System.Drawing.Rectangle]::new(0, 0, 600, 800),
    [System.Drawing.Color]::FromArgb(11, 24, 38),
    [System.Drawing.Color]::FromArgb(27, 68, 85),
    [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
)
$graphics.FillRectangle($background, 0, 0, 600, 800)
$accent = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(0, 164, 239))
$white = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(242, 247, 252))
$muted = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(160, 202, 221))
$format = New-Object System.Drawing.StringFormat
$format.Alignment = [System.Drawing.StringAlignment]::Center
$fontTitle = New-Object System.Drawing.Font('Segoe UI', 43, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$fontSubtitle = New-Object System.Drawing.Font('Segoe UI', 27, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$fontDetail = New-Object System.Drawing.Font('Segoe UI', 18, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$icon = [System.Drawing.Image]::FromFile($iconPath)

try {
    $graphics.FillRectangle($accent, 250, 63, 100, 6)
    $graphics.DrawString('STEAM DECK', $fontTitle, $white, [System.Drawing.RectangleF]::new(30, 89, 540, 70), $format)
    $graphics.DrawImage($icon, [System.Drawing.Rectangle]::new(75, 183, 450, 450))
    $graphics.DrawString('BIG PICTURE', $fontSubtitle, $white, [System.Drawing.RectangleF]::new(30, 650, 540, 48), $format)
    $graphics.DrawString('1920 x 1200   |   ONE DISPLAY', $fontDetail, $muted, [System.Drawing.RectangleF]::new(30, 707, 540, 34), $format)
    $bitmap.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output $outputPath
}
finally {
    $icon.Dispose()
    $fontDetail.Dispose()
    $fontSubtitle.Dispose()
    $fontTitle.Dispose()
    $format.Dispose()
    $muted.Dispose()
    $white.Dispose()
    $accent.Dispose()
    $background.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
}
