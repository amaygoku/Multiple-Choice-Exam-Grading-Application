param(
  [string]$FrontendPort = '3000',
  [string]$BackendPort = '8000'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendDir = Join-Path $repoRoot 'zipgrade-web'
$certDir = Join-Path $repoRoot 'dev-certs'
$certFile = Join-Path $certDir 'dev-cert.pem'
$keyFile = Join-Path $certDir 'dev-key.pem'
$logDir = Join-Path $repoRoot 'results\logs'
$backendOutLog = Join-Path $logDir 'dev-https-backend.out.log'
$backendErrLog = Join-Path $logDir 'dev-https-backend.err.log'
$frontendOutLog = Join-Path $logDir 'dev-https-frontend.out.log'
$frontendErrLog = Join-Path $logDir 'dev-https-frontend.err.log'

New-Item -ItemType Directory -Force -Path $certDir | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$openssl = (Get-Command openssl.exe -ErrorAction Stop).Source
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
  $pythonExe = (Get-Command python.exe -ErrorAction Stop).Source
}

$ips = @(
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -and $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
    Select-Object -ExpandProperty IPAddress -Unique
)

$sanDns = @('localhost', $env:COMPUTERNAME.ToLower()) | Where-Object { $_ }
$sanIps = @('127.0.0.1', '::1') + $ips
$sanDns = $sanDns | Select-Object -Unique
$sanIps = $sanIps | Select-Object -Unique

$needCert = -not (Test-Path $certFile) -or -not (Test-Path $keyFile)
if ($needCert) {
  $configPath = Join-Path $certDir 'dev-https-openssl.cnf'
  $configLines = @(
    '[req]'
    'default_bits = 2048'
    'prompt = no'
    'default_md = sha256'
    'distinguished_name = dn'
    'x509_extensions = v3_req'
    ''
    '[dn]'
    'CN = localhost'
    ''
    '[v3_req]'
    'subjectAltName = @alt_names'
    'basicConstraints = critical,CA:FALSE'
    'keyUsage = critical,digitalSignature,keyEncipherment'
    'extendedKeyUsage = serverAuth'
    ''
    '[alt_names]'
  )

  $index = 1
  foreach ($dns in $sanDns) {
    $configLines += "DNS.$index = $dns"
    $index++
  }
  foreach ($ip in $sanIps) {
    $configLines += "IP.$index = $ip"
    $index++
  }

  Set-Content -Path $configPath -Value $configLines -Encoding ascii

  & $openssl req -x509 -nodes -newkey rsa:2048 -days 825 `
    -keyout $keyFile -out $certFile -config $configPath -extensions v3_req | Out-Null
}

$env:VITE_HTTPS_CERT_FILE = $certFile
$env:VITE_HTTPS_KEY_FILE = $keyFile

$backendArgs = @(
  '-m', 'uvicorn',
  'backend.main:app',
  '--host', '0.0.0.0',
  '--port', $BackendPort,
  '--ssl-certfile', $certFile,
  '--ssl-keyfile', $keyFile
)

Start-Process -FilePath $pythonExe `
  -ArgumentList $backendArgs `
  -WorkingDirectory $repoRoot `
  -WindowStyle Hidden `
  -RedirectStandardOutput $backendOutLog `
  -RedirectStandardError $backendErrLog | Out-Null

$frontendArgs = @(
  'run', 'dev',
  '--', '--host', '0.0.0.0',
  '--port', $FrontendPort
)

Start-Process -FilePath 'npm.cmd' `
  -ArgumentList $frontendArgs `
  -WorkingDirectory $frontendDir `
  -WindowStyle Hidden `
  -RedirectStandardOutput $frontendOutLog `
  -RedirectStandardError $frontendErrLog | Out-Null

$primaryIp = ($ips | Select-Object -First 1)
if (-not $primaryIp) { $primaryIp = 'localhost' }

Write-Host "Frontend: https://${primaryIp}:$FrontendPort"
Write-Host "Backend:  https://${primaryIp}:$BackendPort"
Write-Host "Logs:"
Write-Host "  $frontendOutLog"
Write-Host "  $frontendErrLog"
Write-Host "  $backendOutLog"
Write-Host "  $backendErrLog"
