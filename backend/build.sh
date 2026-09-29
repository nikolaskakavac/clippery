#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) { throw new Error("bgutil requires Node.js 22+ at build and runtime"); }'
python -m pip install -r requirements.txt

# Match the Python plugin to the official 2.0.0 generator, including its npm lockfile.
provider_dir="$PWD/vendor/bgutil-ytdlp-pot-provider"
provider_commit=37169ee2656e08c5c2e5dc9df4c598c0cb4c88a8
if [[ ! -d "$provider_dir" ]]; then
    git clone --depth 1 --single-branch --branch 2.0.0 \
        https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git "$provider_dir"
fi
[[ "$(git -C "$provider_dir" rev-parse HEAD)" == "$provider_commit" ]] || {
    echo "Unexpected bgutil source revision" >&2
    exit 1
}
[[ -z "$(git -C "$provider_dir" status --porcelain --untracked-files=no)" ]] || {
    echo "bgutil source has local modifications" >&2
    exit 1
}
cd "$provider_dir/server"
npm ci --include=dev --no-audit --no-fund
npx --no-install tsc
[[ "$(node build/generate_once.js --version)" == "2.0.0" ]]
