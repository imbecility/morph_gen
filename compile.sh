#!/usr/bin/env bash
set -euo pipefail
# пример: ./compile.sh /build/morph_gen_linux_x64
OUT_PATH="${1:-}"

if [[ -z "$OUT_PATH" ]]; then
    echo "нужно указать путь к выходному бинарнику."
    echo "пример: $0 /build/morph_gen_linux_x64"
    exit 1
fi

OUT_DIR="$(dirname "$OUT_PATH")"
OUT_FILE="$(basename "$OUT_PATH")"

echo "поиск словарей..."
DICT_PATH=$(python -c "import pymorphy3_dicts_ru, os; print(os.path.join(pymorphy3_dicts_ru.__path__[0], 'data'))")
echo "словари найдены в: $DICT_PATH"

echo "компиляция бинарника..."
python -m nuitka --standalone --onefile \
    --include-package=yaml \
    --include-package=pymorphy3 \
    --include-data-dir="$DICT_PATH"=pymorphy_data \
    --output-dir="$OUT_DIR" \
    --output-filename="$OUT_FILE" \
    --remove-output \
    morph_gen.py

echo "готово: $OUT_PATH"