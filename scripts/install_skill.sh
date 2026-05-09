#!/usr/bin/env bash
# install_skill.sh — copy SKILL.md and src/ into a Hermes skills directory.
#
# Safe by default: runs as a dry-run unless --apply is passed. Never edits
# user config (e.g. ~/.hermes/config.yaml) and never installs Python
# packages — pip install is a separate, explicit step.
#
# Usage:
#   ./scripts/install_skill.sh               # dry-run, default destination
#   ./scripts/install_skill.sh --apply       # actually copy files
#   ./scripts/install_skill.sh --dest PATH   # custom destination
#   ./scripts/install_skill.sh -h            # help
set -euo pipefail

DEFAULT_DEST="${HOME}/.hermes/skills/software-development/hermes-swarm-benchmark"
APPLY=0
DEST="${DEFAULT_DEST}"

usage() {
    cat <<EOF
install_skill.sh — copy hermes-swarm-benchmark into a Hermes skills directory.

Options:
  --apply           Perform the copy. Without this, the script prints what it
                    would do and exits 0 (dry-run).
  --dest PATH       Destination directory. Default: ${DEFAULT_DEST}
  -h, --help        Show this help.

What gets copied:
  SKILL.md          → \$DEST/SKILL.md
  src/              → \$DEST/src/

What this script does NOT do:
  - It does not edit ~/.hermes/config.yaml or any other user config.
  - It does not run pip install. Run 'pip install -e .' yourself afterwards.
  - It does not delete or overwrite files outside \$DEST.

Examples:
  $0 --dry-run                    # default dry-run
  $0 --apply                      # install into the default location
  $0 --apply --dest ~/skills/bm   # install into a custom location
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --apply)
            APPLY=1
            shift
            ;;
        --dry-run)
            APPLY=0
            shift
            ;;
        --dest)
            if [ "$#" -lt 2 ]; then
                echo "error: --dest requires a path argument" >&2
                exit 2
            fi
            DEST="$2"
            shift 2
            ;;
        --dest=*)
            DEST="${1#--dest=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_SRC="${REPO_ROOT}/SKILL.md"
PKG_SRC="${REPO_ROOT}/src"

if [ ! -f "${SKILL_SRC}" ]; then
    echo "error: SKILL.md not found at ${SKILL_SRC}" >&2
    exit 2
fi
if [ ! -d "${PKG_SRC}" ]; then
    echo "error: src/ not found at ${PKG_SRC}" >&2
    exit 2
fi

# Refuse obviously hostile destination paths.
case "${DEST}" in
    ""|/|/etc|/etc/*|/usr|/usr/*|/bin|/bin/*|/sbin|/sbin/*)
        echo "error: refusing to install into '${DEST}'" >&2
        exit 2
        ;;
esac

mode_label="DRY-RUN"
if [ "${APPLY}" -eq 1 ]; then
    mode_label="APPLY"
fi

echo "Mode:        ${mode_label}"
echo "Source:      ${REPO_ROOT}"
echo "Destination: ${DEST}"
echo
echo "Would copy:"
echo "  ${SKILL_SRC}"
echo "    -> ${DEST}/SKILL.md"
echo "  ${PKG_SRC}/"
echo "    -> ${DEST}/src/"
echo

if [ "${APPLY}" -ne 1 ]; then
    echo "Dry-run only — no files changed. Re-run with --apply to install."
    exit 0
fi

mkdir -p "${DEST}"
cp -f "${SKILL_SRC}" "${DEST}/SKILL.md"
# Refresh src/ wholesale so stale files don't linger from a previous install.
rm -rf "${DEST}/src"
cp -R "${PKG_SRC}" "${DEST}/src"

echo "Installed:"
echo "  ${DEST}/SKILL.md"
echo "  ${DEST}/src/"
echo
echo "Next step: install the Python CLI so the skill can call it."
echo "  cd ${REPO_ROOT} && pip install -e ."
