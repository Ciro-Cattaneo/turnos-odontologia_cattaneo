#requires -Version 5.1
<#
.SYNOPSIS
  Demo local de un comando: migra, carga datos ficticios, compila la SPA y
  arranca API + SPA en el mismo origen (http://localhost:<Port>).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\iniciar-demo.ps1
  powershell -ExecutionPolicy Bypass -File .\iniciar-demo.ps1 -Port 8010 -NoBrowser
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

function Write-Paso([string]$mensaje) {
    Write-Host ""
    Write-Host "==> $mensaje" -ForegroundColor Cyan
}

function Write-Ok([string]$mensaje) {
    Write-Host "    OK  $mensaje" -ForegroundColor Green
}

function Fail([string]$mensaje) {
    Write-Host ""
    Write-Host "ERROR: $mensaje" -ForegroundColor Red
    exit 1
}

function Set-EnvKey {
    param(
        [string[]]$Lineas,
        [string]$Clave,
        [string]$Valor,
        [switch]$SoloSiFalta
    )
    $patron = "^\s*" + [regex]::Escape($Clave) + "\s*="
    $encontrada = $false
    $salida = New-Object 'System.Collections.Generic.List[string]'
    foreach ($linea in $Lineas) {
        if ($linea -match $patron) {
            $encontrada = $true
            if ($SoloSiFalta) {
                $salida.Add($linea)
            } else {
                $salida.Add("$Clave=$Valor")
            }
        } else {
            $salida.Add($linea)
        }
    }
    if (-not $encontrada) {
        $salida.Add("$Clave=$Valor")
    }
    return $salida.ToArray()
}

function Get-EnvKey {
    param([string[]]$Lineas, [string]$Clave)
    $patron = "^\s*" + [regex]::Escape($Clave) + "\s*="
    foreach ($linea in $Lineas) {
        if ($linea -match $patron) {
            return (($linea -split "=", 2)[1]).Trim().Trim('"').Trim("'")
        }
    }
    return ""
}

# ---------------------------------------------------------------------------
# 1) Precondiciones
# ---------------------------------------------------------------------------
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $raiz

Write-Paso "Verificando entorno"
if (-not (Test-Path -LiteralPath (Join-Path $raiz "backend/app/main.py"))) {
    Fail "no se encontro backend/app/main.py; ejecuta el script desde la raiz del repo."
}
try {
    & python --version > $null 2>&1
} catch {
    Fail "no se encontro 'python' en PATH."
}
if ($LASTEXITCODE -ne 0) {
    Fail "no se encontro 'python' en PATH."
}

$depsCode = "import fastapi, uvicorn, sqlalchemy, psycopg, alembic, pydantic_settings, argon2, jwt, apscheduler, yaml"
& python -c $depsCode 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "    Faltan dependencias del backend. Instalando backend/requirements.txt..." -ForegroundColor Yellow
    & python -m pip install -r backend/requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Fail "fallo la instalacion de dependencias (pip install -r backend/requirements.txt)."
    }
}
Write-Ok "python y dependencias del backend presentes"

# ---------------------------------------------------------------------------
# 2) .env (solo claves necesarias; no pisa secretos existentes)
# ---------------------------------------------------------------------------
$envPath = Join-Path $raiz ".env"
$envExample = Join-Path $raiz ".env.example"
if (-not (Test-Path -LiteralPath $envPath)) {
    if (-not (Test-Path -LiteralPath $envExample)) {
        Fail "no existe .env ni .env.example; no se puede preparar la demo."
    }
    Copy-Item -LiteralPath $envExample -Destination $envPath -Force
    Write-Ok ".env creado desde .env.example"
}

$lineas = @(Get-Content -LiteralPath $envPath -Encoding UTF8)
$lineas = @(Set-EnvKey -Lineas $lineas -Clave "ENV" -Valor "development" -SoloSiFalta)
$lineas = @(Set-EnvKey -Lineas $lineas -Clave "NOTIF_WORKER_ENABLED" -Valor "false")
$lineas = @(Set-EnvKey -Lineas $lineas -Clave "FRONTEND_URL" -Valor "http://localhost:$Port")
$utf8SinBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($envPath, (($lineas -join "`r`n") + "`r`n"), $utf8SinBom)
Write-Ok ".env listo (ENV, NOTIF_WORKER_ENABLED=false, FRONTEND_URL=http://localhost:$Port)"

# ---------------------------------------------------------------------------
# 3) Migraciones
# ---------------------------------------------------------------------------
Write-Paso "Aplicando migraciones (alembic upgrade head)"
$env:PYTHONPATH = "backend"
& python -m alembic -c backend/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) {
    Fail "fallo alembic upgrade head. Revisa DATABASE_URL en .env y que Postgres este corriendo."
}
Write-Ok "base de datos al dia"

# ---------------------------------------------------------------------------
# 4) Datos ficticios de demo
# ---------------------------------------------------------------------------
Write-Paso "Cargando datos ficticios (admin, profesionales, horarios y turnos)"
& python backend/scripts/demo_bootstrap.py
if ($LASTEXITCODE -ne 0) {
    Fail "fallo backend/scripts/demo_bootstrap.py."
}
Write-Ok "datos de demo listos (idempotente)"

# ---------------------------------------------------------------------------
# 5) Build de la SPA -> static/
# ---------------------------------------------------------------------------
$staticDir = Join-Path $raiz "static"
$staticIndex = Join-Path $staticDir "index.html"
$frontend = Join-Path $raiz "frontend"

$necesitaBuild = $Rebuild -or (-not (Test-Path -LiteralPath $staticIndex))
if (-not $necesitaBuild) {
    $ref = (Get-Item -LiteralPath $staticIndex).LastWriteTimeUtc
    $fuentes = @(
        Get-Item -LiteralPath (Join-Path $frontend "package.json")
        Get-Item -LiteralPath (Join-Path $frontend "index.html")
    ) + @(Get-ChildItem -LiteralPath (Join-Path $frontend "src") -Recurse -File)
    $masNuevo = $fuentes | Where-Object { $_.LastWriteTimeUtc -gt $ref } | Select-Object -First 1
    if ($null -ne $masNuevo) {
        $necesitaBuild = $true
    }
}

if ($necesitaBuild) {
    Write-Paso "Compilando la SPA (Vite)"
    if (-not (Test-Path -LiteralPath (Join-Path $frontend "node_modules"))) {
        Write-Host "    node_modules ausente: ejecutando npm install..." -ForegroundColor Yellow
        Push-Location -LiteralPath $frontend
        & npm install
        $installOk = ($LASTEXITCODE -eq 0)
        Pop-Location
        if (-not $installOk) {
            Fail "fallo npm install en frontend/."
        }
    }

    # La SPA se sirve same-origin: sin VITE_API_URL absoluto. Se neutraliza
    # temporalmente frontend/.env.local (si existe) para que no lo pise.
    $envLocal = Join-Path $frontend ".env.local"
    $envLocalExistia = Test-Path -LiteralPath $envLocal
    $envLocalBytes = $null
    if ($envLocalExistia) {
        $envLocalBytes = [System.IO.File]::ReadAllBytes($envLocal)
    }

    $buildOk = $false
    try {
        if ($envLocalExistia) {
            Remove-Item -LiteralPath $envLocal -Force
        }
        Remove-Item Env:VITE_API_URL -ErrorAction SilentlyContinue
        Push-Location -LiteralPath $frontend
        & npm run build
        $buildOk = ($LASTEXITCODE -eq 0)
        Pop-Location
    } finally {
        if (Test-Path -LiteralPath $frontend) {
            Set-Location -LiteralPath $raiz
        }
        if ($envLocalExistia -and $null -ne $envLocalBytes) {
            [System.IO.File]::WriteAllBytes($envLocal, $envLocalBytes)
        }
    }
    if (-not $buildOk) {
        Fail "fallo npm run build en frontend/."
    }

    if (Test-Path -LiteralPath $staticDir) {
        Remove-Item -LiteralPath $staticDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $staticDir | Out-Null
    Copy-Item -Path (Join-Path $frontend "dist/*") -Destination $staticDir -Recurse -Force
    if (-not (Test-Path -LiteralPath $staticIndex)) {
        Fail "no se genero static/index.html tras el build."
    }
    Write-Ok "SPA compilada y copiada a static/"
} else {
    Write-Ok "SPA ya compilada (static/index.html vigente)"
}

# ---------------------------------------------------------------------------
# 6) Banner + arranque foreground
# ---------------------------------------------------------------------------
$adminEmail = Get-EnvKey -Lineas $lineas -Clave "ADMIN_EMAIL"
$adminPassword = Get-EnvKey -Lineas $lineas -Clave "ADMIN_PASSWORD"
$url = "http://localhost:$Port"

$ocupado = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($null -ne $ocupado) {
    Fail "el puerto $Port ya esta en uso; cerra ese proceso o usa -Port <otro>."
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host " DEMO LOCAL - Turnos Odontologia Cattaneo" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host " URL:            $url"
Write-Host " Login staff:    $url/staff/login"
Write-Host " Usuario admin:  $adminEmail"
Write-Host " Password admin: $adminPassword"
Write-Host ""
Write-Host " Rutas de demo:"
Write-Host "   /                              home"
Write-Host "   /reservar                      reserva publica"
Write-Host "   /cancelar                      cancelacion por token"
Write-Host "   /staff/login                   login staff"
Write-Host "   /staff/agenda                  agenda"
Write-Host "   /staff/notificaciones          notificaciones"
Write-Host "   /staff/admin/profesionales     admin profesionales"
Write-Host "   /staff/admin/usuarios          admin usuarios"
Write-Host "   /staff/admin/reportes          admin reportes"
Write-Host ""
Write-Host " Datos 100% ficticios (Ley 25.326, regla dura 12)." -ForegroundColor DarkGray
Write-Host " Detener la demo: Ctrl+C o cerra esta ventana." -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host ""

$jobNavegador = $null
if (-not $NoBrowser) {
    $jobNavegador = Start-Job -ScriptBlock {
        param([string]$base)
        $limite = (Get-Date).AddSeconds(90)
        while ((Get-Date) -lt $limite) {
            try {
                $resp = Invoke-WebRequest -UseBasicParsing -Uri "$base/api/health" -TimeoutSec 2
                if ($resp.StatusCode -eq 200) {
                    Start-Process $base
                    return
                }
            } catch {
                Start-Sleep -Milliseconds 700
            }
        }
    } -ArgumentList $url
}

Write-Paso "Arrancando API + SPA en $url (foreground)"
$codigo = 0
try {
    & python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $Port
    $codigo = $LASTEXITCODE
} finally {
    if ($null -ne $jobNavegador) {
        Stop-Job $jobNavegador -ErrorAction SilentlyContinue
        Remove-Job $jobNavegador -Force -ErrorAction SilentlyContinue
    }
}

if ($codigo -ne 0) {
    Fail "uvicorn termino con codigo $codigo."
}
