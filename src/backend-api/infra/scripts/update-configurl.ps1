# Update APP Configuration Service URL in .env file (PowerShell)

Write-Host "Updating APP Configuration Service URL in .env file..."
# This script updates the deployed APP Configuration Service URL in .env file.

$envValue = azd env get-value APP_CONFIGURATION_URL

if (Test-Path "./src/.env") {
    (Get-Content ./src/.env) -replace '^(APP_CONFIGURATION_URL)=.*', "APP_CONFIGURATION_URL=`"$envValue`"" | Set-Content ./src/.env
}
else {
    Write-Host ".env file not found in ./src/"
}
