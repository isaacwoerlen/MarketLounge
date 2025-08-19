# 🔧 Configuration automatique pour le projet MarketLounge

$projectPath = "C:\Users\isaac\Documents\GitHub\MarketLounge"
$venvPath = "$projectPath\venv\Scripts"

if ($PWD.Path -eq $projectPath) {
    $env:Path += ";$venvPath"
    Set-Alias py "$venvPath\python.exe"
    Set-Alias dj "$venvPath\python.exe manage.py"
    Set-Alias test "$venvPath\pytest.exe"
    Write-Host "✅ Environnement virtuel prêt. Utilise 'py', 'dj' ou 'test'."
}
