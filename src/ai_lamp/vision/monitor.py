"""防唠叨节流 —— 把「逐帧检测」变成「该不该提醒」。零第三方依赖。

逐帧判定会抖动、会唠叨。这里加两道闸：
  - 持续(persistence)：问题要连续保持一段时间才第一次提醒，滤掉一闪而过。
  - 冷却(cooldown)   ：同一类问题两次提醒至少间隔一段时间，不烦人。

时钟通过参数 `now` 注入，因此可用假时钟做单测，无需真实等待。
这就是产品里「多久提醒一次才不烦人」的工程化。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .posture_rules import PostureIssue


@dataclass
class PostureMonitor:
    """对 judge() 的逐帧结果做时间维度的节流。

    用法：每帧把 issues 和当前时间喂给 update()，它只在「真正该提醒」时返回问题。
    """

    persistence_s: float = 3.0
    cooldown_s: float = 30.0

    def __post_init__(self) -> None:
        self._first_seen: Dict[str, float] = {}  # code -> 连续出现的起始时间
        self._last_alert: Dict[str, float] = {}  # code -> 上次提醒时间

    def reset(self) -> None:
        self._first_seen.clear()
        self._last_alert.clear()

    def update(self, issues: List[PostureIssue], now: float) -> List[PostureIssue]:
        """返回本帧真正需要触发提醒的问题列表（已通过持续+冷却两道闸）。"""
        active = {issue.code: issue for issue in issues}

        # 不再出现的问题：清掉它的连续计时（下次重新累计）
        for code in list(self._first_seen):
            if code not in active:
                del self._first_seen[code]

        alerts: List[PostureIssue] = []
        for code, issue in active.items():
            self._first_seen.setdefault(code, now)
            held = now - self._first_seen[code]
            if held < self.persistence_s:
                continue  # 还没持续够久
            last = self._last_alert.get(code)
            if last is not None and (now - last) < self.cooldown_s:
                continue  # 还在冷却期
            alerts.append(issue)
            self._last_alert[code] = now

        return alerts
