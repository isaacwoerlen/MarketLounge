$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 🚨 Vérifie si Docker Desktop est lancé
$dockerRunning = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue

if (-not $dockerRunning) {
    Write-Host "🚨 Docker Desktop n'est pas lancé !" -ForegroundColor Red
    Write-Host "❌ Impossible de redémarrer la stack sans Docker." -ForegroundColor Yellow
    Pause
    exit
}

# 📁 Se placer dans le dossier du projet
Set-Location "C:\Users\isaac\Documents\GitHub\MarketLounge"

# 🛑 Arrêt de la stack
Write-Host "🛑 Arrêt de la stack MarketLounge..." -ForegroundColor Cyan
docker compose down --volumes --remove-orphans

# ⏳ Pause avant redémarrage
Write-Host "⏳ Attente de 5 secondes..."
Start-Sleep -Seconds 5

# 🚀 Redémarrage de la stack
Write-Host "🚀 Redémarrage de la stack MarketLounge..." -ForegroundColor Green
docker compose up -d

Write-Host "✅ Stack redémarrée ! Accède à http://localhost/" -ForegroundColor Green
Pause
