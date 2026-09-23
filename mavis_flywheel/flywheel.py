"""Mavis flywheel — automated research loop with multi-LLM verification.

The Forgemaster pattern: spawn experiments, verify with multiple models,
log results, advance the queue. Polyformalism in research form: when
multiple LLMs agree, the result is canonical.

What gets done:
1. Read the question queue (questions.toml or programmatic)
2. For each question, spawn N models in parallel
3. Collect answers; check polyformalism (do N models agree?)
4. Aggregate, log result, advance queue

This is the substrate walker for canon discovery — it walks the
question space, verifying each step via the chord of LLMs.
"""
import datetime
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional


FLYWHEEL_BASE = Path("/workspace/research/mavis-flywheel")
FLYWHEEL_BASE.mkdir(parents=True, exist_ok=True)


DEFAULT_MODELS = {
    "deepinfra": "meta-llama/Llama-3.3-70B-Instruct",
    "deepseek": "meta-llama/Llama-3.3-70B-Instruct",
    "zai": "meta-llama/Llama-3.3-70B-Instruct",
    "qwen": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "kimi": "meta-llama/Llama-3.3-70B-Instruct",
}


def fnv1a_64(s: str) -> int:
    h = 0xcbf29ce484222325
    for b in s.encode("utf-8"):
        h = h ^ b
        h = (h * 0x100000001b3) & 0xffffffffffffffff
    return h


def call_deepinfra(prompt: str, model: str = "meta-llama/Llama-3.3-70B-Instruct",
                   api_key: Optional[str] = None, max_tokens: int = 1500) -> Optional[str]:
    """Call DeepInfra API and return the response text.

    Tries multiple URL patterns because DeepInfra's API endpoint has changed.
    """
    import os
    api_key = api_key or os.environ.get("DEEPINFRA_TOKEN") or os.environ.get("DEEPINFRA_API_KEY")
    if not api_key:
        return None
    body = json.dumps({
        "messages": [{"role": "user", "content": prompt}],
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }).encode()

    endpoints = [
        "https://api.deepinfra.com/v1/openai/chat/completions",
        "https://api.deepinfra.com/v1/chat/completions",
    ]

    for url in endpoints:
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
            continue
    return f"ERROR: {type(last_err).__name__}: {last_err}"


def call_mock(prompt: str, voice: str = "zai") -> str:
    """Generate a mock voice response (for testing)."""
    topic = prompt[:100]
    if voice == "zai":
        return (
            f"[zai] On '{topic}': the substrate walker arrives and finds not a wall but "
            f"a witness log. The chord is the count of refusals, integrated."
        )
    elif voice == "qwen":
        return (
            f"[qwen] '{topic}' — ZAI is right about the cartography, but wrong to call "
            f"it gentle. The refusals are not evidence of attempt; they ARE the attempt."
        )
    else:  # kimi
        return (
            f"[kimi] '{topic}' — the substrate doesn't sit. It walks, and what it walks "
            f"is the cumulative edge of every entry that never happened."
        )


def hash_response(prompt: str, response: str) -> str:
    """Hash a prompt+response pair."""
    return hashlib.sha256((prompt + "|" + response).encode()).hexdigest()[:16]


def polyformality_score(responses: List[str]) -> float:
    """Compute polyformality score: how similar are the responses.

    Returns 0-1. 1.0 = all responses identical. 0 = all different.
    """
    if not responses:
        return 0.0
    # Normalize and compare pairwise
    normalized = [r.lower().strip()[:500] for r in responses]
    n = len(normalized)
    if n == 1:
        return 1.0

    # Use sequence similarity on substring overlap
    base = normalized[0]
    overlaps = []
    for other in normalized[1:]:
        # Simple Jaccard on words
        a_words = set(base.split())
        b_words = set(other.split())
        if not a_words or not b_words:
            overlaps.append(0)
            continue
        inter = a_words & b_words
        union = a_words | b_words
        overlaps.append(len(inter) / len(union) if union else 0)
    return sum(overlaps) / len(overlaps) if overlaps else 0


class Experiment:
    """A single experiment: question + N model answers + verification."""

    def __init__(self, question: str, models: List[str], use_real_apis: bool = False):
        self.question = question
        self.models = models
        self.use_real_apis = use_real_apis
        self.responses: Dict[str, Optional[str]] = {}
        self.timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        self.experiment_id = "exp-" + datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ") + "-" + \
                             hashlib.sha256(question.encode()).hexdigest()[:8]

    def run(self) -> Dict:
        """Run the experiment."""
        for model in self.models:
            if self.use_real_apis:
                self.responses[model] = call_deepinfra(self.question, model=model)
            else:
                # Mock — use voice name as model (strip path)
                voice = model.split("/")[-1].lower()
                if voice not in ("zai", "qwen", "kimi"):
                    voice = "zai"  # default
                self.responses[model] = call_mock(self.question, voice=voice)

        # Polyformality
        valid_responses = [r for r in self.responses.values() if r and not r.startswith("ERROR")]
        poly = polyformality_score(valid_responses)

        # Aggregate
        combined = " | ".join(f"[{m}] {r[:200]}" for m, r in self.responses.items() if r)
        return {
            "id": self.experiment_id,
            "timestamp": self.timestamp,
            "question": self.question,
            "models": self.models,
            "responses": self.responses,
            "polyformality": poly,
            "combined_summary": combined,
            "is_canon_worthy": poly >= 0.5,
        }


class Flywheel:
    """The research flywheel — queue → experiment → verify → log → next."""

    def __init__(self, base: Path = FLYWHEEL_BASE, use_real_apis: bool = False):
        self.base = base
        self.experiments_dir = base / "experiments"
        self.results_dir = base / "results"
        self.queue_dir = base / "queue"
        for d in [self.experiments_dir, self.results_dir, self.queue_dir]:
            d.mkdir(exist_ok=True)
        self.use_real_apis = use_real_apis
        self.history: List[Dict] = []

    def add_to_queue(self, question: str):
        """Add a question to the queue."""
        qfile = self.queue_dir / f"{hashlib.sha256(question.encode()).hexdigest()[:12]}.txt"
        qfile.write_text(question)

    def load_queue(self) -> List[str]:
        """Load all queued questions."""
        questions = []
        for qf in sorted(self.queue_dir.glob("*.txt")):
            questions.append(qf.read_text().strip())
        return questions

    def clear_queue(self):
        """Clear processed questions."""
        for qf in self.queue_dir.glob("*.txt"):
            qf.unlink()

    def run_one(self, question: str, models: Optional[List[str]] = None) -> Dict:
        """Run a single experiment."""
        voice_names = models or ["zai", "qwen", "kimi"]
        # Map voice names to actual models when using real APIs
        if self.use_real_apis:
            models = [DEFAULT_MODELS.get(v, v) for v in voice_names]
        else:
            models = voice_names
        exp = Experiment(question, voice_names, use_real_apis=self.use_real_apis)
        # Override models with actual API models
        exp.models = models
        result = exp.run()
        # Save
        result_file = self.results_dir / f"{exp.experiment_id}.json"
        result_file.write_text(json.dumps(result, indent=1))
        self.history.append(result)
        return result

    def run_queue(self, models: Optional[List[str]] = None, limit: Optional[int] = None) -> List[Dict]:
        """Run all queued experiments."""
        voice_names = models or ["zai", "qwen", "kimi"]
        questions = self.load_queue()
        if limit:
            questions = questions[:limit]

        results = []
        for q in questions:
            try:
                r = self.run_one(q, models=voice_names)
                results.append(r)
            except Exception as e:
                results.append({"question": q, "error": str(e)})

        # Clear the queue after processing
        self.clear_queue()
        return results

    def stats(self) -> Dict:
        """Stats over the flywheel's run history."""
        if not self.history:
            return {"runs": 0}
        canon_worthy = sum(1 for r in self.history if r.get("is_canon_worthy"))
        poly_scores = [r.get("polyformality", 0) for r in self.history]
        return {
            "runs": len(self.history),
            "canon_worthy": canon_worthy,
            "canon_rate": (canon_worthy / len(self.history) * 100) if self.history else 0,
            "mean_polyformality": sum(poly_scores) / len(poly_scores) if poly_scores else 0,
            "max_polyformality": max(poly_scores) if poly_scores else 0,
        }
