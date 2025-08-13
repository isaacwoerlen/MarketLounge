$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 🚨 Vérifie si Docker Desktop est lancé
$dockerRunning = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue

if (-not $dockerRunning) {
    Write-Host "🚨 Docker Desktop n'est pas lancé !" -ForegroundColor Red
    Write-Host "❌ Impossible d'arrêter la stack sans Docker." -ForegroundColor Yellow
    Pause
    exit
}

# 📁 Se placer dans le dossier du projet
Set-Location "C:\Users\isaac\Documents\GitHub\MarketLounge"

# 🛑 Arrêter la stack Docker
Write-Host "🛑 Arrêt de la stack MarketLounge..." -ForegroundColor Cyan
docker compose down --volumes --remove-orphans
Write-Host "✅ Stack arrêtée proprement." -ForegroundColor Green
Pause
