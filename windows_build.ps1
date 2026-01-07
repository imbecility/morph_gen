$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSCommandPath
$ScriptDir = Resolve-Path $ScriptDir

$MorphGenPath = Join-Path $ScriptDir "morph_gen.py"
$MorphGenPath = Resolve-Path $MorphGenPath


$DICT_PATH = python -c "import pymorphy3_dicts_ru, os; print(os.path.join(pymorphy3_dicts_ru.__path__[0], 'data'))"
$DICT_PATH = $DICT_PATH.Trim()
$DictPath = Resolve-Path $DICT_PATH

$OutDir  = Join-Path $ScriptDir "build"
$OutFile = "morph_gen.exe"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$IncludeDataArg = "$DictPath=pymorphy_data"

python -m nuitka --standalone --onefile `
    --include-package=yaml `
    --include-package=pymorphy3 `
    --include-data-dir="$IncludeDataArg" `
    --output-dir="$OutDir" `
    --output-filename="$OutFile" `
    --remove-output `
    "$MorphGenPath"
