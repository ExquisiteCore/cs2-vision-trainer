[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $OutputDir
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$packageSource = Join-Path $projectRoot 'src\cs2_vision_runtime'
$hidProjectRoot = Join-Path $projectRoot 'tools\rp2350_keymouse_bridge_firmware\sdk\python'
$templateRoot = Join-Path $projectRoot 'packaging\python-runtime-sdk'
$versionFile = Join-Path $packageSource '_version.py'
$hidVersionFile = Join-Path $hidProjectRoot 'rp2350_hid_bridge\_version.py'

$versionText = Get-Content -LiteralPath $versionFile -Raw
$versionMatch = [regex]::Match(
    $versionText,
    '__version__\s*=\s*["''](?<version>\d+\.\d+\.\d+)["'']'
)
if (-not $versionMatch.Success) {
    throw "Unable to read a three-part SDK version from $versionFile"
}
$sdkVersion = $versionMatch.Groups['version'].Value

$hidVersionText = Get-Content -LiteralPath $hidVersionFile -Raw
$hidVersionMatch = [regex]::Match(
    $hidVersionText,
    '__version__\s*=\s*["''](?<version>\d+\.\d+\.\d+)["'']'
)
if (-not $hidVersionMatch.Success) {
    throw "Unable to read a three-part HID SDK version from $hidVersionFile"
}
$hidSdkVersion = $hidVersionMatch.Groups['version'].Value

$outputFullPath = [IO.Path]::GetFullPath(
    $(if ([IO.Path]::IsPathRooted($OutputDir)) {
        $OutputDir
    }
    else {
        Join-Path (Get-Location).Path $OutputDir
    })
)
New-Item -ItemType Directory -Path $outputFullPath -Force | Out-Null

& uv build --wheel --out-dir $outputFullPath $hidProjectRoot
if ($LASTEXITCODE -ne 0) {
    throw "HID SDK uv build failed with exit code $LASTEXITCODE"
}

$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
    [IO.Path]::DirectorySeparatorChar,
    [IO.Path]::AltDirectorySeparatorChar
)
$stageName = "cs2-vision-runtime-sdk-$([guid]::NewGuid().ToString('N'))"
$stageRoot = Join-Path $temporaryRoot $stageName

New-Item -ItemType Directory -Path (Join-Path $stageRoot 'src') -Force | Out-Null
try {
    Copy-Item -LiteralPath $packageSource -Destination (Join-Path $stageRoot 'src') -Recurse
    Copy-Item -LiteralPath (Join-Path $templateRoot 'pyproject.toml') -Destination $stageRoot
    Copy-Item -LiteralPath (Join-Path $templateRoot 'README.md') -Destination $stageRoot

    & uv build --wheel --out-dir $outputFullPath $stageRoot
    if ($LASTEXITCODE -ne 0) {
        throw "uv build failed with exit code $LASTEXITCODE"
    }

    $runtimeWheels = @(
        Get-ChildItem -LiteralPath $outputFullPath -Filter 'cs2_vision_runtime_sdk-*.whl'
    )
    $hidWheels = @(
        Get-ChildItem -LiteralPath $outputFullPath -Filter 'rp2350_hid_bridge-*.whl'
    )
    $runtimeWheel = @(
        $runtimeWheels | Where-Object Name -Like "cs2_vision_runtime_sdk-$sdkVersion-*.whl"
    )
    $hidWheel = @(
        $hidWheels | Where-Object Name -Like "rp2350_hid_bridge-$hidSdkVersion-*.whl"
    )
    if ($runtimeWheels.Count -ne 1 -or $runtimeWheel.Count -ne 1) {
        throw "Expected exactly one SDK wheel for version $sdkVersion in $outputFullPath"
    }
    if ($hidWheels.Count -ne 1 -or $hidWheel.Count -ne 1) {
        throw "Expected exactly one HID SDK wheel for version $hidSdkVersion in $outputFullPath"
    }
    Write-Host "hid_python_sdk version=$hidSdkVersion wheel=$($hidWheel[0].FullName)"
    Write-Host "python_runtime_sdk version=$sdkVersion wheel=$($runtimeWheel[0].FullName)"
}
finally {
    if (Test-Path -LiteralPath $stageRoot) {
        $resolvedStage = [IO.Path]::GetFullPath($stageRoot)
        $temporaryPrefix = $temporaryRoot + [IO.Path]::DirectorySeparatorChar
        if (
            -not $resolvedStage.StartsWith(
                $temporaryPrefix,
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            -not (Split-Path -Leaf $resolvedStage).StartsWith(
                'cs2-vision-runtime-sdk-',
                [StringComparison]::OrdinalIgnoreCase
            )
        ) {
            throw "Refusing to remove unsafe SDK staging path: $resolvedStage"
        }
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}
