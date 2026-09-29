#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) { throw new Error("bgutil requires Node.js 22+ at build and runtime"); }'
python -m pip install -r requirements.txt

# Match the Python plugin to the official 2.0.0 generator, including its npm lockfile.
provider_dir="$PWD/vendor/bgutil-ytdlp-pot-provider"
provider_repo=https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git
provider_commit=37169ee2656e08c5c2e5dc9df4c598c0cb4c88a8

# Target this repository explicitly; never discover the application's parent repo.
provider_git() {
    git --git-dir="$provider_dir/.git" --work-tree="$provider_dir" "$@"
}
if [[ ! -d "$provider_dir/.git" ]]; then
    mkdir -p "$provider_dir"
    provider_git init
fi
[[ -z "$(provider_git status --porcelain --untracked-files=no)" ]] || {
    echo "bgutil source has local modifications" >&2
    exit 1
}

# Fetch the immutable commit on every build, including reused build directories.
provider_git fetch --depth 1 --no-tags "$provider_repo" "$provider_commit"
provider_git checkout --detach "$provider_commit"
actual_commit="$(provider_git rev-parse HEAD)"
[[ "$actual_commit" == "$provider_commit" ]] || {
    echo "Unexpected bgutil source revision: expected $provider_commit, got $actual_commit" >&2
    exit 1
}
[[ -z "$(provider_git status --porcelain --untracked-files=no)" ]] || {
    echo "bgutil source has local modifications" >&2
    exit 1
}
cd "$provider_dir/server"
npm ci --include=dev --no-audit --no-fund
npx --no-install tsc
[[ "$(node build/generate_once.js --version)" == "2.0.0" ]]
