#pragma once

#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <vector>

namespace qlaib::core {

// Lightweight pub-sub bus used to decouple acquisition threads from the UI.
template <typename Payload>
class EventBus {
public:
  using Callback = std::function<void(const Payload &)>;

  int subscribe(const std::string &topic, Callback cb) {
    std::scoped_lock lk(mutex_);
    int token = nextToken_++;
    subscribers_[topic].push_back({token, std::move(cb)});
    return token;
  }

  void publish(const std::string &topic, const Payload &payload) {
    std::vector<Callback> cbs;
    {
      std::scoped_lock lk(mutex_);
      auto it = subscribers_.find(topic);
      if (it == subscribers_.end())
        return;
      for (auto &sub : it->second)
        cbs.push_back(sub.cb);
    }
    for (auto &cb : cbs)
      cb(payload);
  }

private:
  struct Subscriber {
    int token;
    Callback cb;
  };
  std::map<std::string, std::vector<Subscriber>> subscribers_;
  int nextToken_{0};
  std::mutex mutex_;
};

} // namespace qlaib::core
