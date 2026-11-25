#!/usr/bin/env bash
# Run bin/cloak_photo.py in a throwaway Python environment: everything it downloads goes to
# temporary folders that are deleted when it finishes, so nothing stays behind. With --no-cloak it
# needs only PyTorch, to find the face (a few minutes). With the cloak it also needs the
# face-recognition packages (about 1 GB in all) and models (about 1.5 GB), and builds dlib, which
# takes 10 to 15 minutes. Arguments go to cloak_photo.py; `bin/cloak_photo.sh --help` lists them.
#
#   bin/cloak_photo.sh ~/Downloads/IMG_1234.HEIC assets/img/profile/prof_pic.webp --no-cloak
set -euo pipefail
cd "$(dirname "$0")/.."

python="${PYTHON:-}"
if [ -z "$python" ]; then
  for candidate in .venv/bin/python python3.13 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      python="$candidate"
      break
    fi
  done
fi

case " $* " in
  *" -h "* | *" --help "*) exec "$python" bin/cloak_photo.py --help ;;
esac

work="$(mktemp -d "${TMPDIR:-/tmp}/cloak-photo.XXXXXX")"
trap 'rm -rf "$work"' EXIT
trap 'exit 1' INT TERM HUP # so Ctrl-C also runs the cleanup above

echo "Installing the packages into a temporary environment ($work)..."
"$python" -m venv "$work/venv"
pip=("$work/venv/bin/pip" install --quiet --no-cache-dir --disable-pip-version-check)
"${pip[@]}" torch torchvision numpy pillow-heif requests tqdm
"${pip[@]}" --no-deps facenet-pytorch
case " $* " in
  *" --no-cloak "*) ;;
  *)
    "${pip[@]}" onnx onnx2torch onnxruntime opencv-python-headless lpips
    "${pip[@]}" dlib || echo "dlib didn't install (building it needs CMake); its test will be skipped."
    ;;
esac

TMPDIR="$work" "$work/venv/bin/python" bin/cloak_photo.py "$@"
