#!/usr/bin/env bash
#
# Rewrite text files in place with OpenCC.
#
# Default targets: pinyin_*.txt and extra/*.txt next to this script.
#
# Usage:
#   ./opencc_rewrite.sh -c CONFIG [-n] [FILE...]
#
# Examples:
#   ./opencc_rewrite.sh -c s2t.json
#   ./opencc_rewrite.sh -c s2t.json -n
#   ./opencc_rewrite.sh -c s2t.json pinyin_*.txt extra/*.txt
#   ./opencc_rewrite.sh -c s2t.json other.txt

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

config=
dry_run=0

usage() {
    cat <<'EOF'
Usage: opencc_rewrite.sh -c CONFIG [-n] [FILE...]

Rewrite text files in place with OpenCC. With no FILE arguments, the default
targets are pinyin_*.txt and extra/*.txt next to this script.

Options:
  -c, --config CONFIG  OpenCC config passed to `opencc -c` (required)
  -n, --dry-run        Show files that would change; write nothing
  -h, --help           Show this help

Examples:
  ./opencc_rewrite.sh -c s2t.json
  ./opencc_rewrite.sh -c s2t.json -n
  ./opencc_rewrite.sh -c s2t.json pinyin_*.txt extra/*.txt
  ./opencc_rewrite.sh -c s2t.json other.txt
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

while (($# > 0)); do
    case $1 in
        -c|--config)
            (($# >= 2)) || die "option $1 requires an argument"
            config=$2
            shift 2
            ;;
        -n|--dry-run)
            dry_run=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*)
            die "unknown option: $1 (try --help)"
            ;;
        *)
            break
            ;;
    esac
done

[[ -n $config ]] || die "missing required option: -c CONFIG (try --help)"

command -v opencc >/dev/null 2>&1 \
    || die "opencc not found; install it in WSL (e.g. sudo apt install opencc)"

if (($# > 0)); then
    files=("$@")
else
    shopt -s nullglob
    files=("$script_dir"/pinyin_*.txt "$script_dir"/extra/*.txt)
    shopt -u nullglob
fi

((${#files[@]} > 0)) || die "no files matched"

tmp=
cleanup() {
    if [[ -n $tmp ]]; then
        rm -f -- "$tmp"
    fi
}
trap cleanup EXIT

changed=0
processed=0

for file in "${files[@]}"; do
    if [[ ! -f $file ]]; then
        printf 'skip (not a file): %s\n' "$file" >&2
        continue
    fi

    processed=$((processed + 1))
    tmp=$(mktemp --tmpdir="$(dirname -- "$file")" ".$(basename -- "$file").XXXXXX")

    if ! opencc -c "$config" -i "$file" -o "$tmp"; then
        die "opencc failed on: $file"
    fi

    if cmp -s -- "$file" "$tmp"; then
        printf 'unchanged: %s\n' "$file"
    elif ((dry_run)); then
        printf 'would change: %s\n' "$file"
        changed=$((changed + 1))
    else
        chmod --reference="$file" "$tmp"
        mv -- "$tmp" "$file"
        printf 'converted: %s\n' "$file"
        changed=$((changed + 1))
    fi

    rm -f -- "$tmp"
    tmp=
done

((processed > 0)) || die "no readable files"

printf 'Done: %d changed, %d processed.\n' "$changed" "$processed"
