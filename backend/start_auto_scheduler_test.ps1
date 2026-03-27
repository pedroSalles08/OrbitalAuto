param(
    [ValidateSet("dry-run-manual", "dry-run-loop", "real-manual", "real-loop")]
    [string]$Mode = "dry-run-manual",
    [int]$Port = 8000,
    [string]$Cpf = $env:AUTO_SCHEDULE_CPF,
    [SecureString]$Password,
    [string]$AccessUser = $env:BASIC_AUTH_USER,
    [SecureString]$AccessPassword,
    [string]$Timezone = $(if ($env:AUTO_SCHEDULE_TIMEZONE) { $env:AUTO_SCHEDULE_TIMEZONE } else { "America/Sao_Paulo" }),
    [int]$LookaheadDays = $(if ($env:AUTO_SCHEDULE_LOOKAHEAD_DAYS) { [int]$env:AUTO_SCHEDULE_LOOKAHEAD_DAYS } else { 7 }),
    [string]$Meals = "AL",
    [ValidateSet("30d", "90d", "end_of_year")]
    [string]$DurationMode = "30d",
    [string]$ConfigPath = $(if ($env:AUTO_SCHEDULE_CONFIG_PATH) { $env:AUTO_SCHEDULE_CONFIG_PATH } else { (Join-Path $PSScriptRoot "data\\auto_schedule.json") }),
    [switch]$PrintOnly
)

function ConvertTo-PlainText {
    param([SecureString]$SecureValue)

    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

function Get-ActiveUntil {
    param([string]$Mode)

    $today = Get-Date
    switch ($Mode) {
        "30d" { return $today.AddDays(30).ToString("yyyy-MM-dd") }
        "90d" { return $today.AddDays(90).ToString("yyyy-MM-dd") }
        default { return (Get-Date -Year $today.Year -Month 12 -Day 31).ToString("yyyy-MM-dd") }
    }
}

$dryRun = "true"
$configEnabled = $false

switch ($Mode) {
    "dry-run-manual" {
        $dryRun = "true"
        $configEnabled = $false
    }
    "dry-run-loop" {
        $dryRun = "true"
        $configEnabled = $true
    }
    "real-manual" {
        $dryRun = "false"
        $configEnabled = $false
    }
    "real-loop" {
        $dryRun = "false"
        $configEnabled = $true
    }
}

$passwordValue = $env:AUTO_SCHEDULE_PASSWORD
if ($PSBoundParameters.ContainsKey("Password")) {
    $passwordValue = ConvertTo-PlainText -SecureValue $Password
}

$accessPasswordValue = $env:BASIC_AUTH_PASS
if ($PSBoundParameters.ContainsKey("AccessPassword")) {
    $accessPasswordValue = ConvertTo-PlainText -SecureValue $AccessPassword
}

if (-not $PrintOnly) {
    if (-not $Cpf) {
        $Cpf = Read-Host "CPF do Orbital"
    }

    if (-not $passwordValue) {
        $securePassword = Read-Host "Senha do Orbital" -AsSecureString
        $passwordValue = ConvertTo-PlainText -SecureValue $securePassword
    }
}

$mealList = @($Meals.Split(",") | ForEach-Object { $_.Trim().ToUpper() } | Where-Object { $_ })
$weeklyRules = [ordered]@{
    MON = @($mealList)
    TUE = @($mealList)
    WED = @($mealList)
    THU = @($mealList)
    FRI = @($mealList)
    SAT = @($mealList)
    SUN = @($mealList)
}
$activeUntil = Get-ActiveUntil -Mode $DurationMode
$updatedAt = (Get-Date).ToString("o")

$configPayload = [ordered]@{
    enabled = $configEnabled
    weekly_rules = $weeklyRules
    duration_mode = $DurationMode
    active_until = $activeUntil
    updated_at = $updatedAt
    last_successful_run_at = $null
    last_primary_attempt_at = $null
    last_fallback_attempt_at = $null
}

$env:DESKTOP_MODE = "true"
$env:DEBUG = "false"
$env:ENABLE_DEBUG_ROUTES = "false"
$env:PORT = "$Port"
$env:AUTO_SCHEDULE_DRY_RUN = $dryRun
$env:AUTO_SCHEDULE_TIMEZONE = $Timezone
$env:AUTO_SCHEDULE_LOOKAHEAD_DAYS = "$LookaheadDays"
$env:AUTO_SCHEDULE_CONFIG_PATH = $ConfigPath

if ($Cpf) {
    $env:AUTO_SCHEDULE_CPF = $Cpf
}

if ($passwordValue) {
    $env:AUTO_SCHEDULE_PASSWORD = $passwordValue
}

if ($AccessUser) {
    $env:BASIC_AUTH_USER = $AccessUser
}

if ($accessPasswordValue) {
    $env:BASIC_AUTH_PASS = $accessPasswordValue
}

if ($PrintOnly) {
    [pscustomobject]@{
        Mode = $Mode
        Port = $Port
        DryRun = $env:AUTO_SCHEDULE_DRY_RUN
        Timezone = $env:AUTO_SCHEDULE_TIMEZONE
        LookaheadDays = $env:AUTO_SCHEDULE_LOOKAHEAD_DAYS
        ConfigPath = $env:AUTO_SCHEDULE_CONFIG_PATH
        HasCpf = [bool]$env:AUTO_SCHEDULE_CPF
        HasPassword = [bool]$env:AUTO_SCHEDULE_PASSWORD
        SeededConfigEnabled = $configPayload.enabled
        SeededMeals = ($mealList -join ",")
        SeededDuration = $configPayload.duration_mode
        SeededActiveUntil = $configPayload.active_until
        AccessGateEnabled = [bool]($env:BASIC_AUTH_USER -and $env:BASIC_AUTH_PASS)
    } | Format-List
    exit 0
}

$configDir = Split-Path -Path $ConfigPath -Parent
if ($configDir) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
}
$configPayload | ConvertTo-Json -Depth 5 | Set-Content -Path $ConfigPath -Encoding UTF8

Push-Location $PSScriptRoot
try {
    python -m uvicorn app:app --reload --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}
