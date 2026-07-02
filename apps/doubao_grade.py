#!/usr/bin/env python3
"""批改冒烟测试（真相层）：喂一张做完的作业照片，让豆包逐题判分，输出结构化清单。

用法：
    python3 apps/doubao_grade.py                       # 默认用 data/samples 里第一张图
    python3 apps/doubao_grade.py data/samples/xxx.jpeg # 指定图片

这一步只验证「批改准不准」——把豆包判的结果打印出来，人工和原图逐条核对。
面向孩子的鼓励/渐进提示/记错题，是后面的"表现层"，不在本脚本里。
"""

import glob
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ai_lamp.env import load_env  # noqa: E402
from ai_lamp.tutor.doubao_client import DoubaoClient, DoubaoConfigError  # noqa: E402
from ai_lamp.tutor.prompts import GRADER_SYSTEM  # noqa: E402


def _extract_json(text: str) -> dict:
    """从模型回复里抠出 JSON（容忍 ```json 代码块或前后多余文字）。"""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.lstrip().lower().startswith("json"):
            s = s.lstrip()[4:]
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1:
        s = s[start : end + 1]
    return json.loads(s)


def main() -> int:
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        found = sorted(glob.glob(os.path.join(_REPO_ROOT, "data", "samples", "*")))
        found = [f for f in found if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        if not found:
            print("[没图] 请把作业照片放到 data/samples/ 或用参数指定路径", file=sys.stderr)
            return 2
        image_path = found[0]

    if not os.path.isfile(image_path):
        print(f"[找不到图片] {image_path}", file=sys.stderr)
        return 2

    try:
        # 批改可单独指定更快的小模型（环境变量 ARK_GRADER_MODEL），不影响多轮陪聊用的 ARK_MODEL
        # 先加载 .env，再读 ARK_GRADER_MODEL（否则此刻 .env 还没加载，读到 None 会退回 pro）
        load_env()
        grader_model = os.environ.get("ARK_GRADER_MODEL") or None
        client = DoubaoClient(model=grader_model)
    except DoubaoConfigError as exc:
        print(f"[配置缺失] {exc}", file=sys.stderr)
        return 2

    print(f"→ 批改图片：{image_path}\n（模型：{client.model}，逐题辨认+计算中，稍候…）\n")
    try:
        raw = client.ask(
            "请批改这张作业，按系统要求只输出 JSON。",
            image_path=image_path,
            system=GRADER_SYSTEM,
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[调用失败] {exc}", file=sys.stderr)
        return 1

    try:
        data = _extract_json(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"[JSON 解析失败] {exc}\n---- 原始回复 ----\n{raw}", file=sys.stderr)
        return 1

    # 总评不信模型的顶层字段（实测它会自相矛盾）——一律从每道小题的 ok 自己算
    problems = data.get("problems", [])
    wrong_majors = []
    wrong_count = 0
    for prob in problems:
        if any(not it.get("ok", True) for it in prob.get("items", [])):
            major = prob.get("major")
            if major not in wrong_majors:
                wrong_majors.append(major)
        wrong_count += sum(1 for it in prob.get("items", []) if not it.get("ok", True))
    all_correct = wrong_count == 0

    print("=" * 60)
    print(f"总评：{'✅ 全对' if all_correct else f'有 {wrong_count} 处需要检查'}")
    print("=" * 60)

    for prob in problems:
        major = prob.get("major")
        ptype = prob.get("type")
        items = prob.get("items", [])
        has_err = any(not it.get("ok", True) for it in items)
        head = f"第 {major} 大题 [{ptype}]" + ("  ← 有错" if has_err else "  ✓")
        print(f"\n{head}")
        for it in items:
            mark = "✓" if it.get("ok", True) else "✗"
            label = it.get("label", "")
            stu = it.get("student", "")
            cor = it.get("correct", "")
            if it.get("ok", True):
                print(f"   {mark} {label}: {stu}")
            else:
                print(f"   {mark} {label}: 孩子写[{stu}]  正确[{cor}]")

    print("\n" + "-" * 60)
    if all_correct:
        print("→ 面向孩子：真棒，全对啦！🎉")
    else:
        majors = "、".join(str(m) for m in wrong_majors)
        print(f"→ 有错的大题：第 {majors} 大题")
        print("  （表现层将先只说'检查一下第 X 大题哦'，孩子自查后再逐步指到具体小题）")

    print("\n（请对照原图逐条核对：豆包判得准不准？）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
