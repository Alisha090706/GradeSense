"""
Class Insight Agent — pydantic-wrapped port of the original
class_insight_agent.py. This is the seed of the broader Analytics Agent;
Phase 8 generalizes it from one-assignment-at-a-time to course-level and
topic-level aggregation, reading from AnalyticsSnapshot instead of being
called ad hoc.
"""
import json
import re
from collections import defaultdict

from pydantic import BaseModel

from app.agents.base import Agent
from app.agents import llm_client

SYSTEM_PROMPT = """You are analyzing an entire class's automated code-grading results to find
shared misconceptions. You will be given the assignment description, and for every student,
which specific automated tests they failed and any crash/timeout info. Group students into
named misconception clusters (e.g. "Off-by-one error in loop bounds", "Missing edge-case
guard"). Only include a cluster if 2+ students share the pattern. For each cluster, list the
cluster name, a one-sentence explanation of the underlying reasoning error, and the list of
affected student IDs. Also list any one-off outliers separately. Respond ONLY as valid JSON:
{"clusters": [{"name": str, "explanation": str, "student_ids": [str]}],
"outliers": [{"student_id": str, "issue": str}]}. No prose outside the JSON."""

_EXPECTED_GOT_RE = re.compile(r"expected ([\-\d.]+|'.*?'), got ([\-\d.]+|'.*?')")
_DEMO_HINTS = {
    ("find_second_largest", "fsl_duplicates"): "Did not de-duplicate values before selecting the second largest",
}


class InsightInput(BaseModel):
    per_student_feedback: list[dict]
    assignment_description: str = ""


class Cluster(BaseModel):
    name: str
    explanation: str
    student_ids: list[str]


class Outlier(BaseModel):
    student_id: str
    issue: str


class InsightOutput(BaseModel):
    clusters: list[Cluster]
    outliers: list[Outlier]


def _classify_failure(detail):
    err = detail.get("error") or ""
    category = detail["category"]
    test_id = detail["id"]

    if "missing required function" in err:
        return "Required function missing or misnamed (structure error)"

    hint = _DEMO_HINTS.get((category, test_id))
    if hint:
        return hint

    if "IndexError" in err or "KeyError" in err:
        exc = "IndexError" if "IndexError" in err else "KeyError"
        return f"Missing input-validation guard in '{category}' — crashes with {exc} instead of a clean error"

    m = re.search(r"expected (\w+) but got return value", err)
    if m:
        return f"Missing guard clause in '{category}' — should raise {m.group(1)} but doesn't"

    m = _EXPECTED_GOT_RE.search(err)
    if m:
        try:
            expected, got = float(m.group(1)), float(m.group(2))
            if got > expected:
                return f"'{category}': result too high (possible double-counting / off-by-one)"
            if got < expected:
                return f"'{category}': result too low (possible missed case / off-by-one exclusion)"
        except ValueError:
            return f"'{category}': returns an incorrect value"

    if ":" in err:
        exc_type = err.split(":")[0].strip()
        if exc_type and exc_type[0].isupper():
            return f"Unexpected {exc_type} raised in '{category}'"

    return f"'{category}': logic error"


def _offline_cluster(per_student_feedback):
    cluster_members = defaultdict(set)
    outliers = []

    for s in per_student_feedback:
        if s["exec_status"] == "timeout":
            cluster_members["Infinite loop / non-terminating logic"].add(s["student_id"])
            continue
        if s["exec_status"] == "crash" and not s.get("failing_details"):
            cluster_members["Submission does not import/run at all (syntax error)"].add(s["student_id"])
            continue
        if not s["failing_tests"]:
            continue

        labels_for_student = set()
        for detail in s.get("failing_details", []):
            label = _classify_failure(detail)
            if label:
                labels_for_student.add(label)
        if labels_for_student:
            for label in labels_for_student:
                cluster_members[label].add(s["student_id"])
        else:
            outliers.append({"student_id": s["student_id"], "issue": "Unclassified failure pattern"})

    clusters = []
    leftover_outliers = []
    for name, members in cluster_members.items():
        if len(members) >= 2:
            clusters.append({
                "name": name,
                "explanation": f"{len(members)} students share this pattern in their submission.",
                "student_ids": sorted(members),
            })
        else:
            leftover_outliers.extend({"student_id": m, "issue": name} for m in members)

    clusters.sort(key=lambda c: -len(c["student_ids"]))
    return {"clusters": clusters, "outliers": outliers + leftover_outliers}


class ClassInsightAgent(Agent[InsightInput, InsightOutput]):
    name = "class_insight_agent"

    def run(self, payload: InsightInput) -> InsightOutput:
        if llm_client.is_live():
            summaries = [
                {"student_id": s["student_id"], "exec_status": s["exec_status"],
                 "failing_tests": s["failing_tests"], "score": s["score"]}
                for s in payload.per_student_feedback
            ]
            user_prompt = (f"Assignment description: {payload.assignment_description}\n\n"
                            f"Per-student summaries:\n{summaries}")
            text = llm_client.complete(SYSTEM_PROMPT, user_prompt, max_tokens=1200)
            if text:
                try:
                    return InsightOutput(**json.loads(text))
                except Exception:
                    pass  # fall through to offline clustering

        return InsightOutput(**_offline_cluster(payload.per_student_feedback))
