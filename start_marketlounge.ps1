$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 🚨 Vérifie si Docker Desktop est lancé
$dockerRunning = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue

if (-not $dockerRunning) {
    Write-Host "🚨 Docker Desktop n'est pas lancé !" -ForegroundColor Red
    $choice = Read-Host "👉 Veux-tu le lancer maintenant ? (O/N)"

    if ($choice -eq "O" -or $choice -eq "o") {
        Write-Host "🐳 Lancement de Docker Desktop..." -ForegroundColor Cyan
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        Write-Host "⏳ Attends quelques secondes que Docker démarre..."
        Start-Sleep -Seconds 15
    } else {
        Write-Host "❌ Docker doit être lancé pour démarrer la stack." -ForegroundColor Yellow
        Pause
        exit
    }
}

# 📁 Se placer dans le dossier du projet
Set-Location "C:\Users\isaac\Documents\GitHub\MarketLounge"

# 🚀 Lancer la stack Docker
Write-Host "🚀 Lancement de la stack MarketLounge..." -ForegroundColor Green
docker compose up -d
Write-Host "✅ Stack lancée ! Accède à http://localhost/" -ForegroundColor Green
Pause
