#!/usr/bin/env bash
set -euo pipefail
opt_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$opt_dir/.." && pwd)"
gateann_source="${1:-$repo_root/systems/GateANN-public}"
test "$(git -C "$gateann_source" rev-parse HEAD)" = "71e87cbf0e25c0400c0109dd25a64a7c4dccc9dd"
test -f "$gateann_source/build/src/libgateann.a"
mkdir -p "$opt_dir/build"
python3 "$opt_dir/prepare_source.py" --upstream "$gateann_source" --output "$opt_dir/build/search_yfcc_adaptive.cpp"
flags=(-std=c++17 -O3 -DNDEBUG -DUSE_AIO -DUSE_AVX2 -DBG_IO_THREAD -DOVERLAP_INIT -march=native -mtune=native -fopenmp)
includes=(-I"$opt_dir/include" -I"$gateann_source/include" -I"$gateann_source/include/tsl/include" -I"$gateann_source/third_party/liburing/src/include")
c++ "${flags[@]}" "${includes[@]}" "$opt_dir/build/search_yfcc_adaptive.cpp" \
  "$gateann_source/build/src/libgateann.a" -laio -ltcmalloc -lopenblas -pthread \
  -o "$opt_dir/build/search_yfcc_adaptive"
c++ -std=c++17 -O2 -I"$opt_dir/include" "$opt_dir/tests/test_budget.cpp" -o "$opt_dir/build/test_budget"
"$opt_dir/build/test_budget"
echo "ADAPTIVE_BUILD_AND_TEST_PASS"
