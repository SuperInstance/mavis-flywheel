"""CLI for mavis-flywheel."""
import argparse
import json
import sys
from pathlib import Path

from .flywheel import Flywheel, Experiment, polyformality_score


def cmd_queue(args):
    """Add a question to the queue."""
    fw = Flywheel(use_real_apis=args.real)
    fw.add_to_queue(args.question)
    print(f"✓ Queued: {args.question[:80]}")


def cmd_run(args):
    """Run a single experiment."""
    fw = Flywheel(use_real_apis=args.real)
    result = fw.run_one(args.question)
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print(f"Experiment: {result['id']}")
        print(f"Polyformality: {result['polyformality']:.2f}")
        print(f"Canon worthy: {'✓' if result['is_canon_worthy'] else '✗'}")
        print(f"Responses:")
        for m, r in result['responses'].items():
            preview = (r or "(none)")[:150]
            print(f"  [{m}] {preview}")


def cmd_run_queue(args):
    """Run all queued experiments."""
    fw = Flywheel(use_real_apis=args.real)
    results = fw.run_queue(limit=args.limit)
    stats = fw.stats()
    if args.json:
        print(json.dumps({"stats": stats, "results": results}, indent=1))
    else:
        print(f"=== Flywheel run ===")
        print(f"Runs: {stats.get('runs', 0)}")
        print(f"Canon worthy: {stats.get('canon_worthy', 0)}")
        print(f"Mean polyformality: {stats.get('mean_polyformality', 0):.2f}")


def cmd_stats(args):
    """Show flywheel stats."""
    fw = Flywheel()
    print(json.dumps(fw.stats(), indent=1))


def main():
    p = argparse.ArgumentParser(description="mavis-flywheel — automated research loop with multi-LLM verification")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_q = sub.add_parser("queue", help="Add a question to the queue")
    p_q.add_argument("question", help="Question to queue")
    p_q.add_argument("--real", action="store_true", help="Use real DeepInfra API")
    p_q.set_defaults(func=cmd_queue)

    p_r = sub.add_parser("run", help="Run a single experiment immediately")
    p_r.add_argument("question")
    p_r.add_argument("--real", action="store_true")
    p_r.add_argument("--json", action="store_true")
    p_r.set_defaults(func=cmd_run)

    p_rq = sub.add_parser("run-queue", help="Run all queued experiments")
    p_rq.add_argument("--limit", type=int)
    p_rq.add_argument("--real", action="store_true")
    p_rq.add_argument("--json", action="store_true")
    p_rq.set_defaults(func=cmd_run_queue)

    sub.add_parser("stats", help="Show flywheel stats").set_defaults(func=cmd_stats)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
