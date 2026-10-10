#!/usr/bin/env bash
# Build with the same pinned SDK and dependency ports as the Windows build.
set -euo pipefail
repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
dependency_root=${DEPENDENCY_ROOT:-"$repository/.deps"}
sdk=${SDK_DIRECTORY:-"$dependency_root/ida-sdk94"}
vcpkg_root=${VCPKG_DIRECTORY:-"$dependency_root/vcpkg"}
build=${BUILD_DIRECTORY:-"$repository/build-ida94-linux"}
parallel=${PARALLEL:-8}
ida_directory=${1:-}

pin() {
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' \
        "$repository/scripts/dependencies.json" "$1"
}
checkout() {
    local directory=$1 url=$2 revision=$3
    if [[ ! -d "$directory/.git" ]]; then
        git init "$directory"
        git -C "$directory" remote add origin "$url"
        git -C "$directory" fetch --depth 1 origin "$revision"
        git -C "$directory" checkout --detach FETCH_HEAD
    fi
    [[ $(git -C "$directory" rev-parse HEAD) == "$revision" ]] || {
        echo "Dependency revision mismatch: $directory" >&2
        exit 1
    }
}
if [[ -n "$ida_directory" && ! -x "$ida_directory/ida" ]]; then
    echo 'The optional installation directory must contain the Linux ida executable.' >&2
    exit 1
fi
checkout "$sdk" https://github.com/HexRaysSA/ida-sdk.git "$(pin sdkCommit)"
checkout "$vcpkg_root" https://github.com/microsoft/vcpkg.git "$(pin vcpkgCommit)"
export VCPKG_DISABLE_METRICS=1 VCPKG_MAX_CONCURRENCY="$parallel"
if [[ ! -x "$vcpkg_root/vcpkg" ]]; then
    "$vcpkg_root/bootstrap-vcpkg.sh" -disableMetrics
fi
triplet=x64-linux-static-release
"$vcpkg_root/vcpkg" install triton --triplet "$triplet" \
    "--overlay-triplets=$repository/cmake/triplets" \
    "--overlay-ports=$repository/cmake/ports"
cmake -S "$repository" -B "$build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release "-DIDASDK_ROOT_DIR=$sdk" \
    "-DCMAKE_TOOLCHAIN_FILE=$vcpkg_root/scripts/buildsystems/vcpkg.cmake" \
    "-DVCPKG_TARGET_TRIPLET=$triplet" \
    "-DVCPKG_OVERLAY_TRIPLETS=$repository/cmake/triplets" \
    "-DVCPKG_OVERLAY_PORTS=$repository/cmake/ports" \
    -DBUILD_EXAMPLES=OFF -DBUILD_HEXRAYS_SUPPORT=ON
cmake --build "$build" --target Ponce64 --parallel "$parallel"
echo "Built $build/Ponce64.so"
if [[ -n "$ida_directory" ]]; then
    install -m 644 "$build/Ponce64.so" "$ida_directory/plugins/Ponce64.so"
    echo 'Installed Ponce64.so. Restart IDA to load it.'
fi
