# mavis-flywheel

Automated research loop with multi-LLM verification. The Forgemaster pattern, ported to canon.

## Concept

When multiple LLMs answer the same question, their agreement signal indicates canon. Polyformalism in research form: when N voices converge, the result is canonical.

## Pipeline

```
queue (questions)
   ↓
queue runner (parallel voices)
   ↓
   ├── voice 1 (zai → Llama-3.3-70B)
   ├── voice 2 (qwen → Llama-3.1-8B)  
   └── voice 3 (kimi → Llama-3.3-70B)
   ↓
response aggregator
   ↓
polyformality scorer (Jaccard on word sets)
   ↓
canon worthy (poly >= 0.5)
   ↓
results/exp-*.json
```

## Run

```bash
python3 -m mavis_flywheel queue "What is canon?"   # add to queue
python3 -m mavis_flywheel run-queue --real --limit 5  # process queue
python3 -m mavis_flywheel stats  # show history stats
python3 -m mavis_flywheel run "..." --real  # single experiment
```

## Tests

```bash
python3 run_tests.py    # 13/13 passing
```

## Backed by

- Forgemaster pattern (auto-research loop with multi-model verification)
- Polyformalism doctrine (N substrates agreeing = canon)
- The JEV oracle gate (validated by chord)
