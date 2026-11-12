#!/usr/bin/env python3
"""Generate an isolated search entry point; never modify course source files."""
from pathlib import Path
import argparse
import hashlib
import json

p = argparse.ArgumentParser()
p.add_argument('--upstream', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
source = a.upstream / 'tests/search_disk_index_yfcc.cpp'
s = source.read_text()
original = hashlib.sha256(source.read_bytes()).hexdigest()

def replace(old, new):
    global s
    assert s.count(old) == 1, (old[:80], s.count(old))
    s = s.replace(old, new)

replace('#include <vector>', '#include <vector>\n#include "selectivity_budget.h"')
replace('  std::vector<uint64_t> Lvec;', '''  bool adaptive = false;
  double target = 32.0;
  uint64_t ceiling = 8192;
  std::string audit_path;
  std::vector<uint64_t> Lvec;''')
replace('''    uint64_t L = std::atoi(argv[c]);
    if (L >= recall_at) Lvec.push_back(L);''', '''    const std::string arg(argv[c]);
    if (arg == "--policy=adaptive") { adaptive = true; continue; }
    if (arg == "--policy=fixed") { adaptive = false; continue; }
    if (arg.rfind("--target=", 0) == 0) { target = std::stod(arg.substr(9)); continue; }
    if (arg.rfind("--ceiling=", 0) == 0) { ceiling = std::stoull(arg.substr(10)); continue; }
    if (arg.rfind("--audit=", 0) == 0) { audit_path = arg.substr(8); continue; }
    if (arg.find_first_not_of("0123456789") != std::string::npos)
      throw std::invalid_argument("unknown argument: " + arg);
    uint64_t L = std::stoull(arg);
    if (L >= recall_at) Lvec.push_back(L);''')
replace('  // Load data\n', '''  // Both fixed and adaptive controls load the same label table, so their
  // initialization and memory overhead remain comparable.
  auto frequency_start = std::chrono::steady_clock::now();
  course_lab::LabelFrequency frequency;
  frequency.load(base_meta_path);
  const double frequency_ms = std::chrono::duration<double, std::milli>(
      std::chrono::steady_clock::now() - frequency_start).count();
  if (adaptive) for (const auto &l : Lvec)
    course_lab::choose_budget(0.5, l, ceiling, target);
  std::cout << "INIT {\\"frequency_ms\\":" << frequency_ms
            << ",\\"frequency_bytes\\":" << frequency.bytes() << "}" << std::endl;
  // Load data
''')
replace('''    auto t0 = std::chrono::high_resolution_clock::now();''', '''    std::vector<uint64_t> chosen_L(query_num);
    std::vector<double> latency_us(query_num);
    auto t0 = std::chrono::high_resolution_clock::now();''')
replace('''      const void *ql = query_labels.get(i);
      if (is_fa) {''', '''      auto query_start = std::chrono::steady_clock::now();
      const void *ql = query_labels.get(i);
      const double sel = frequency.selectivity(query_labels.buffers[i].data());
      uint64_t query_L = adaptive ? course_lab::choose_budget(sel, L, ceiling, target) : L;
      chosen_L[i] = query_L;
      if (is_fa) {''')
assert s.count('recall_at, mem_L, L,') == 2
s = s.replace('recall_at, mem_L, L,', 'recall_at, mem_L, query_L,')
replace('''    }
    auto t1 = std::chrono::high_resolution_clock::now();''', '''      latency_us[i] = std::chrono::duration<double, std::micro>(
          std::chrono::steady_clock::now() - query_start).count();
    }
    auto t1 = std::chrono::high_resolution_clock::now();''')
replace('''              << std::endl;
  }

  delete[] query;''', '''              << std::endl;
    double mean_l = 0;
    for (const auto &l : chosen_L) mean_l += l / double(query_num);
    std::cout << "METRIC {\\"policy\\":\\"" << (adaptive ? "adaptive" : "fixed")
              << "\\",\\"floor_L\\":" << L << ",\\"ceiling_L\\":" << ceiling
              << ",\\"target\\":" << target << ",\\"mean_L\\":" << std::setprecision(8) << mean_l
              << ",\\"recall_percent\\":" << recall*100.0
              << ",\\"qps\\":" << qps
              << ",\\"mean_latency_us\\":" << elapsed_s*1e6/query_num
              << ",\\"mean_ios\\":" << mean_ios
              << ",\\"filter_skips\\":" << mean_filter_skip
              << ",\\"io_time_us\\":" << mean_bd_io
              << ",\\"tunnel_time_us\\":" << mean_bd_tunnel
              << ",\\"process_time_us\\":" << mean_bd_process << "}" << std::endl;
    if (!audit_path.empty()) {
      if (Lvec.size() != 1) throw std::invalid_argument("audit requires exactly one L");
      std::ofstream audit(audit_path);
      if (!audit) throw std::runtime_error("cannot create audit file");
      audit << "query_id,label_id,match_count,selectivity,effective_L,latency_us,recall_percent,logical_ios,filter_skips,valid_results\\n";
      for (size_t i = 0; i < query_num; ++i) {
        const auto &q = query_labels.buffers[i];
        const double sel = frequency.selectivity(q.data());
        unsigned valid = 0;
        std::set<uint32_t> seen;
        for (size_t k = 0; k < recall_at; ++k) {
          const uint32_t id = res_buf[i*recall_at+k];
          if (id < frequency.nodes() && seen.insert(id).second &&
              idx_->get_spmat_filter()->passes(id, q.data())) ++valid;
        }
        const double qr = compute_recall(gt_ids+i*gt_dim, gt_dim,
                                        res_buf.data()+i*recall_at, 1, recall_at)*100.0;
        audit << i << ',' << (q[0] ? q[1] : 0) << ','
              << (q[0] ? frequency.count(q[1]) : frequency.nodes()) << ','
              << std::setprecision(12) << sel << ',' << chosen_L[i] << ','
              << latency_us[i] << ',' << qr << ',' << stats[i].n_ios << ','
              << stats[i].n_filter_skip << ',' << valid << '\\n';
      }
    }
  }

  delete[] query;''')
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text('// Course extension of MIT-licensed GateANN YFCC entry point.\n' + s)
(a.output.parent / 'source_manifest.json').write_text(json.dumps({
    'base_file': 'tests/search_disk_index_yfcc.cpp',
    'base_commit': '71e87cbf0e25c0400c0109dd25a64a7c4dccc9dd',
    'base_sha256': original,
    'generated_sha256': hashlib.sha256(a.output.read_bytes()).hexdigest(),
}, indent=2) + '\n')
print(a.output)
