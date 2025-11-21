#pragma once

#include "qlaib/data/SampleBatch.h"
#include <string>
#include <unordered_map>

namespace qlaib::metrics {

class IMetric {
public:
  virtual ~IMetric() = default;
  virtual std::string name() const = 0;
  virtual double compute(const data::SampleBatch &batch) = 0;
};

} // namespace qlaib::metrics
