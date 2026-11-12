#pragma once
// Course extension: an exact single-label selectivity table and bounded budget.
// Counts come only from base metadata, never Ground Truth or workload buckets.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace course_lab {
class LabelFrequency {
 public:
  void load(const std::string &path) {
    std::ifstream head(path, std::ios::binary);
    int64_t h[3];
    head.read(reinterpret_cast<char *>(h), sizeof(h));
    if (!head || h[0] <= 0 || h[0] > std::numeric_limits<uint32_t>::max() ||
        h[1] <= 0 || h[2] < 0) throw std::runtime_error("invalid CSR header");
    nodes_ = static_cast<uint64_t>(h[0]);
    std::vector<int64_t> ptr(nodes_ + 1);
    head.read(reinterpret_cast<char *>(ptr.data()), ptr.size() * sizeof(int64_t));
    if (!head || ptr.front() != 0 || ptr.back() != h[2])
      throw std::runtime_error("invalid CSR row pointers");
    for (size_t i = 1; i < ptr.size(); ++i)
      if (ptr[i] < ptr[i-1]) throw std::runtime_error("unordered CSR row pointers");
    frequency_.assign(static_cast<size_t>(h[1]), 0);
    std::vector<uint64_t> last_seen(frequency_.size(), nodes_);
    const uint64_t index_offset = sizeof(h) + ptr.size() * sizeof(int64_t);
    std::ifstream inds(path, std::ios::binary), values(path, std::ios::binary);
    inds.seekg(index_offset);
    values.seekg(index_offset + static_cast<uint64_t>(h[2]) * sizeof(int32_t));
    constexpr size_t chunk = 16384;
    std::vector<int32_t> labels(chunk);
    std::vector<float> data(chunk);
    for (uint64_t row = 0; row < nodes_; ++row) {
      int64_t left = ptr[row+1] - ptr[row];
      while (left > 0) {
        size_t n = static_cast<size_t>(std::min<int64_t>(left, chunk));
        inds.read(reinterpret_cast<char *>(labels.data()), n*sizeof(int32_t));
        values.read(reinterpret_cast<char *>(data.data()), n*sizeof(float));
        if (!inds || !values) throw std::runtime_error("truncated CSR metadata");
        for (size_t j = 0; j < n; ++j) {
          if (labels[j] < 0 || static_cast<size_t>(labels[j]) >= frequency_.size() ||
              !std::isfinite(data[j])) throw std::runtime_error("invalid CSR entry");
          const size_t label = static_cast<size_t>(labels[j]);
          if (data[j] != 0 && last_seen[label] != row) {
            ++frequency_[label];
            last_seen[label] = row;
          }
        }
        left -= n;
      }
    }
  }
  double selectivity(const uint32_t *query) const {
    if (!query || query[0] == 0) return 1.0;
    // The course has one selected label per query. Do not silently estimate
    // multi-label intersections from marginal frequencies.
    if (query[0] != 1) throw std::invalid_argument("adaptive policy requires one label");
    return query[1] < frequency_.size() ? double(frequency_[query[1]]) / nodes_ : 0.0;
  }
  uint64_t count(uint32_t label) const {
    return label < frequency_.size() ? frequency_[label] : 0;
  }
  uint64_t nodes() const { return nodes_; }
  size_t bytes() const { return frequency_.size()*sizeof(uint32_t); }
 private:
  uint64_t nodes_ = 0;
  std::vector<uint32_t> frequency_;
};

inline uint64_t choose_budget(double selectivity, uint64_t floor,
                              uint64_t ceiling, double target = 32.0,
                              uint64_t quantum = 64) {
  if (!std::isfinite(selectivity) || selectivity < 0 || selectivity > 1 ||
      !std::isfinite(target) || target <= 0 || !floor || ceiling < floor || !quantum)
    throw std::invalid_argument("invalid search-budget parameters");
  if (selectivity == 0) return ceiling;
  double estimate = std::ceil(target / selectivity);
  if (estimate >= ceiling) return ceiling;
  uint64_t raw = std::max(floor, static_cast<uint64_t>(estimate));
  uint64_t rounded = ((raw + quantum - 1) / quantum) * quantum;
  return std::min(ceiling, rounded);
}
}  // namespace course_lab
