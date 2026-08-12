# deploy-usb.ps1 - package the game and stage it on a USB drive,
# ready to be copied onto the handheld's SD card.
#
# Produces this tree on the target:
#
#   <dest>\ports\RAY.sh          launcher, generated with LF endings
#   <dest>\ports\ray\game.love   the packaged game
#   <dest>\ports\ray\love        aarch64 engine   (from .\runtime, if present)
#   <dest>\ports\ray\libs\       engine libraries (from .\runtime, if present)
#
# You then copy the whole `ports` folder onto the card's roms partition
# and let it merge with what is already there.
#
# Usage:
#   .\deploy-usb.ps1                 auto-detect a single removable drive
#   .\deploy-usb.ps1 -List           show candidate drives and exit
#   .\deploy-usb.ps1 -Destination E:
#   .\deploy-usb.ps1 -Destination D:\staging -PortsPath ports
#   .\deploy-usb.ps1 -Destination E: -Clean -Eject

param(
    [string]$Destination,
    [string]$PortName   = "ray",     # folder name under ports\
    [string]$ScriptName = "RAY.sh",  # launcher name shown in the menu
    [string]$PortsPath  = "ports",         # subfolder on the target
    [string]$Runtime    = "runtime",       # local folder holding love + libs\
    [switch]$Clean,                        # wipe the port folder first
    [switch]$Eject,                        # safely remove the drive when done
    [switch]$List                          # list removable drives and exit
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

$root     = $PSScriptRoot
$loveFile = Join-Path $root "game.love"

# Never let these end up inside the .love
$excludeNames = @("game.love", "deploy-usb.ps1", "deploy.ps1", "log.txt", ".gitignore")
$excludeDirs  = @(".git", ".vscode", ".idea", "runtime", "dist", "build")
$excludeExts  = @(".love", ".ps1", ".sh", ".zip", ".md", ".bat")

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok  ($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# --- pick a target -------------------------------------------------------
function Get-CandidateDrives {
    [System.IO.DriveInfo]::GetDrives() | Where-Object {
        $_.IsReady -and $_.DriveType -eq [System.IO.DriveType]::Removable
    }
}

if ($List) {
    $drives = Get-CandidateDrives
    if (-not $drives) { Write-Warn "no removable drives found"; exit 0 }
    $drives | ForEach-Object {
        "{0}  {1,-14} {2,8:N1} GB free" -f $_.Name, $_.VolumeLabel, ($_.AvailableFreeSpace / 1GB)
    }
    exit 0
}

if (-not $Destination) {
    $drives = @(Get-CandidateDrives)
    if ($drives.Count -eq 0) {
        throw "No removable drive found. Plug one in, or pass -Destination E:"
    }
    if ($drives.Count -gt 1) {
        Write-Host "More than one removable drive:" -ForegroundColor Yellow
        $drives | ForEach-Object { Write-Host ("  " + $_.Name + "  " + $_.VolumeLabel) }
        throw "Pick one explicitly with -Destination"
    }
    $Destination = $drives[0].Name
    Write-Ok "using $Destination ($($drives[0].VolumeLabel))"
}

if (-not (Test-Path $Destination)) { throw "destination not found: $Destination" }
if (-not (Test-Path (Join-Path $root "main.lua"))) {
    throw "main.lua not found in $root - run this from the project root."
}

$portsDir = Join-Path $Destination $PortsPath
$portDir  = Join-Path $portsDir  $PortName
$shPath   = Join-Path $portsDir  $ScriptName

# --- stage ---------------------------------------------------------------
# Zipping $root into a file inside $root fails: the archive would contain
# itself. Copy the shippable files to a temp dir and zip that instead.
Write-Step "packaging game.love"

$stage = Join-Path ([System.IO.Path]::GetTempPath()) ("love_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stage | Out-Null

try {
    $staged = 0
    Get-ChildItem -Path $root -Recurse -File | Where-Object {
        $rel = $_.FullName.Substring($root.Length + 1)
        ($excludeNames -notcontains $_.Name) -and
        ($excludeExts  -notcontains $_.Extension.ToLower()) -and
        (-not ($excludeDirs | Where-Object { $rel -like "$_\*" }))
    } | ForEach-Object {
        $rel     = $_.FullName.Substring($root.Length + 1)
        $dest    = Join-Path $stage $rel
        $destDir = Split-Path $dest -Parent
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
        Copy-Item $_.FullName $dest
        $staged++
    }
    if ($staged -eq 0) { throw "nothing to package" }

    # ZipFile::CreateFromDirectory writes forward-slash entry names, which
    # PhysFS (and therefore LOVE) requires. Compress-Archive is not a safe
    # substitute.
    if (Test-Path $loveFile) { Remove-Item $loveFile -Force }
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $stage,
        $loveFile,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false      # false = contents at archive root, not nested in a folder
    )
}
finally {
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}

# --- verify the archive --------------------------------------------------
# A .love whose main.lua sits one folder down is the single most common
# reason for "no game" on the device. Catch it here, not there.
$zip = [System.IO.Compression.ZipFile]::OpenRead($loveFile)
try {
    $entries = @($zip.Entries | ForEach-Object { $_.FullName })
    $hasMain = $entries -contains "main.lua"
    $count   = $entries.Count
}
finally { $zip.Dispose() }

if (-not $hasMain) {
    Remove-Item $loveFile -Force
    throw "main.lua is not at the root of the archive - LOVE will refuse it."
}
$kb = [math]::Round((Get-Item $loveFile).Length / 1KB, 1)
Write-Ok "game.love: $count files, $kb KB"

# --- launcher ------------------------------------------------------------
# Single-quoted here-string: nothing in the shell script is interpolated
# by PowerShell. The port folder name is substituted afterwards.
$shTemplate = @'
#!/bin/bash
# {{SCRIPTNAME}} - self-contained LOVE port. Generated by deploy-usb.ps1.
# Expects, inside the port folder:
#   love          (aarch64 binary, e.g. Cebion/love2d_aarch64)
#   libs/         (liblove.so.0 and friends)
#   game.love
#
# PortMaster is used when present, but is NOT required: without it the
# script falls back to sane ArkOS defaults instead of dying on a missing
# control.txt.

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

controlfolder=""
for d in "/opt/system/Tools/PortMaster" "/opt/tools/PortMaster" \
         "$XDG_DATA_HOME/PortMaster" "/roms/ports/PortMaster"; do
  [ -d "$d" ] && { controlfolder="$d"; break; }
done

if [ -n "$controlfolder" ] && [ -f "$controlfolder/control.txt" ]; then
  source "$controlfolder/control.txt"
  [ -f "$controlfolder/mod_${CFW_NAME}.txt" ] && source "$controlfolder/mod_${CFW_NAME}.txt"
  command -v get_controls >/dev/null 2>&1 && get_controls
fi

# fallbacks if PortMaster did not define these
[ -z "$directory" ] && directory="roms"
if [ -z "$ESUDO" ]; then
  if [ "$(id -u)" -eq 0 ]; then ESUDO=""; else ESUDO="sudo"; fi
fi
command -v $ESUDO >/dev/null 2>&1 || ESUDO=""

GAMEDIR="/$directory/ports/{{PORTDIR}}"
# second card / alternate mount, if the port is not where we guessed
if [ ! -d "$GAMEDIR" ]; then
  for alt in /roms/ports/{{PORTDIR}} /roms2/ports/{{PORTDIR}} \
             /mnt/mmc/roms/ports/{{PORTDIR}} /mnt/sdcard/roms/ports/{{PORTDIR}}; do
    [ -d "$alt" ] && { GAMEDIR="$alt"; break; }
  done
fi

cd "$GAMEDIR" || exit 1

> "$GAMEDIR/log.txt" && exec > >(tee "$GAMEDIR/log.txt") 2>&1

echo "--- gamedir: $GAMEDIR"
ls -la "$GAMEDIR"

# Bundled engine, no runtime mounting
export LD_LIBRARY_PATH="$GAMEDIR/libs:$LD_LIBRARY_PATH"
export SDL_GAMECONTROLLERCONFIG="$sdl_controllerconfig"

# Some aarch64 LOVE builds need this to select the GLES backend
export LOVE_GRAPHICS_USE_OPENGLES=1

$ESUDO chmod +x "$GAMEDIR/love" 2>/dev/null
$ESUDO chmod 666 /dev/uinput 2>/dev/null

if [ ! -x "$GAMEDIR/love" ]; then
  echo "!!! $GAMEDIR/love is missing or not executable."
  echo "!!! Copy an aarch64 love binary and its libs/ into the port folder."
  sleep 5
  exit 1
fi

echo "--- launching love"
"$GAMEDIR/love" "$GAMEDIR/game.love"
echo "--- love exited with code $?"

printf "\033c" > /dev/tty0
'@

# --- copy to the target --------------------------------------------------
Write-Step "staging on $Destination"

if ($Clean -and (Test-Path $portDir)) {
    Remove-Item $portDir -Recurse -Force
    Write-Warn "cleaned $portDir"
}
New-Item -ItemType Directory -Path $portDir -Force | Out-Null

Copy-Item $loveFile (Join-Path $portDir "game.love") -Force
Write-Ok "game.love -> $portDir"

# The launcher MUST have LF endings and no BOM. Written with CRLF, the
# device reports: /bin/bash^M: bad interpreter.
$shText = $shTemplate.Replace("{{PORTDIR}}", $PortName).Replace("{{SCRIPTNAME}}", $ScriptName)
$shText = ($shText -replace "`r`n", "`n")
if (-not $shText.EndsWith("`n")) { $shText += "`n" }
[System.IO.File]::WriteAllText($shPath, $shText, (New-Object System.Text.UTF8Encoding($false)))
Write-Ok "$ScriptName -> $portsDir  (LF, no BOM)"

# --- engine --------------------------------------------------------------
$localRuntime = Join-Path $root $Runtime
$loveBin      = Join-Path $portDir "love"

if (Test-Path (Join-Path $localRuntime "love")) {
    Copy-Item (Join-Path $localRuntime "love") $loveBin -Force
    $libsSrc = Join-Path $localRuntime "libs"
    if (Test-Path $libsSrc) {
        Copy-Item $libsSrc $portDir -Recurse -Force
        $n = (Get-ChildItem (Join-Path $portDir "libs") -File).Count
        Write-Ok "engine + libs ($n files) copied from .\$Runtime"
    } else {
        Write-Warn "copied love, but .\$Runtime\libs is missing"
    }
}
elseif (Test-Path $loveBin) {
    Write-Ok "engine already present on target, left untouched"
}
else {
    Write-Warn "NO ENGINE. The port will not start."
    Write-Warn "Put an aarch64 love binary and its libs\ folder in .\$Runtime\"
    Write-Warn "(prebuilt: github.com/Cebion/love2d_aarch64), then re-run."
}

# --- summary -------------------------------------------------------------
Write-Step "done"
Get-ChildItem $portsDir -Recurse |
    ForEach-Object { "    " + $_.FullName.Substring($Destination.Length).TrimStart("\") } |
    Sort-Object

Write-Host ""
Write-Host "Next: copy '$portsDir' onto the card's roms partition," -ForegroundColor White
Write-Host "merging with the existing ports folder, then refresh the game list." -ForegroundColor White

if ($Eject) {
    Write-Step "ejecting $Destination"
    try {
        $letter = $Destination.Substring(0, 2)   # e.g. "E:"
        $shell  = New-Object -ComObject Shell.Application
        $item   = $shell.Namespace(17).ParseName($letter)   # 17 = My Computer

        if (-not $item) {
            throw "drive $letter not found in My Computer - already removed?"
        }

        # Verb text is locale/version-dependent ("Eject", "E&ject", ...).
        # Hardcoding "Eject" silently no-ops when it doesn't match exactly.
        $verb = $item.Verbs() | Where-Object { ($_.Name -replace '&', '') -ieq 'Eject' } |
                Select-Object -First 1

        if (-not $verb) {
            throw "no Eject verb exposed for $letter (unsupported device, or still in use)"
        }

        $verb.DoIt()

        # DoIt() is fire-and-forget - it queues the request but doesn't
        # report success. Poll for the drive to actually vanish.
        $removed = $false
        for ($i = 0; $i -lt 10; $i++) {
            Start-Sleep -Milliseconds 300
            if (-not (Test-Path $letter)) { $removed = $true; break }
        }

        if ($removed) {
            Write-Ok "ejected $letter"
        } else {
            Write-Warn "$letter still present after eject request - close any open files/Explorer windows on it and try again"
        }
    } catch {
        Write-Warn "could not eject: $($_.Exception.Message)"
    }
}