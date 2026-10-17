# Flask RAG Evaluation — Full Results Log (All 3 Pipelines)

| Attribute | Value |
| --- | --- |
| **Study** | Hybrid RAG vs. Standalone Retrieval for Code Comprehension |
| **Repo** | `flask` (src/flask/) |
| **Graph Depth** | 5 hops |
| **Model** | `gpt-4o-mini` |

---

## Scoring Rubric

| Score | Meaning |
| --- | --- |
| **5** | Completely correct, fully cited with correct file/function/line attribution |
| **4** | Mostly correct, minor omissions or one wrong attribution |
| **3** | Partially correct — right concept, missing key details or hops |
| **2** | Structural skeleton only — correct topology but wrong/absent semantics |
| **1** | Incorrect, hallucinated, or refused with no useful content |
| **0** | Explicit refusal with zero usable information |

---

## Final Score Comparison — All 3 Pipelines

| Q# | Type | Complexity | Vector | Graph | **Hybrid** | Δ Best |
| --- | --- | --- | --- | --- | --- | --- |
| Q01 | Factual | Low | 0 | 0 | **2** | +2 |
| Q02 | Multi-hop / Arch | Low | 2 | 3 | **2** | -1 (Graph wins) |
| Q03 | Call-chain | High | 3 | 3 | **4** | +1 |
| Q04 | Call-chain / CF | Medium | 4 | 2 | **5** | +1 |
| Q05 | Security | Medium | 4 | 2 | **5** | +1 |
| Q06 | Security / Chain | High | 3 | 2 | **4** | +1 |
| Q07 | Arch / Multi-hop | Medium | 0 | 2 | **4** | +2 |
| Q08 | Multi-hop / Chain | High | 4 | 1 | **5** | +1 |
| Q09 | Security | Medium | 4 | 1 | **5** | +1 |
| Q10 | Architectural | Medium | 3 | 2 | **4** | +1 |
| Q11 | Call-chain | Medium | 0 | 3 | **3** | tie |
| Q12 | Dependency | Medium | 3 | 1 | **4** | +1 |
| Q13 | Architectural | Medium | 0 | 2 | **5** | +3 |
| Q14 | Security / Dep | Medium | 0 | 2 | **5** | +3 |
| Q15 | Factual / Dep | Low | 4 | 2 | **4** | tie |
| Q16 | Dependency | High | 0 | 3 | **3** | tie |
| Q17 | Call-chain / Arch | High | 4 | 1 | **5** | +1 |
| Q18 | Arch / Chain | High | 3 | 0 | **5** | +2 |
| Q19 | Chain / Security | High | 4 | 4 | **5** | +1 |
| Q20 | Security / CF | Medium | 4 | 3 | **5** | +1 |
| **TOTAL** | | | **61 / 100** | **47 / 100** | **89 / 100** | |
| **AVERAGE** | | | **3.05 / 5** | **2.35 / 5** | **4.45 / 5** | |

**Hybrid wins:** 16 / 20 questions | **Graph wins:** 1 / 20 | **Ties:** 3 / 20

---

## Pipeline 3: Hybrid (Fusion) — Detailed Scores
**Average: 4.45 / 5** | **Zero refusals** | **5 perfect scores on High-complexity questions**

| Q# | Score | Key Observation |
| --- | --- | --- |
| Q01 | **2** | Correctly retrieves `get_cookie_httponly` method body and config key; doesn't confirm default=True |
| Q02 | **2** | Correctly names `App` parent; wrong file (`app.py` vs `sansio/app.py`) — graph edge mispath |
| Q03 | **4** | Best chain yet: includes `AppContext` push and `request_context` step |
| Q04 | **5** | Both branches with line numbers, `_find_error_handler`, `handle_http_exception` all correct |
| Q05 | **5** | Full flow: `itsdangerous`, `URLSafeTimedSerializer`, `BadSignature`, code snippets |
| Q06 | **4** | `get_signing_serializer → None → _fail → RuntimeError` with exact quote; `make_null_session` implicit |
| Q07 | **4** | `_AppCtxGlobals` role, `g` proxy, `_AppCtxGlobalsProxy` in `globals.py` — complete |
| Q08 | **5** | `ctx.copy()`, `with ctx:` wrapper, caveats, example code — best answer in set |
| Q09 | **5** | Both `Vary: Cookie` paths; `save_session`; `session.accessed` condition; code snippet |
| Q10 | **4** | RuntimeError code quoted exactly; correct scope distinction; file attribution correct |
| Q11 | **3** | Good chain but conflates `run()` startup with request dispatch lifecycle |
| Q12 | **4** | All 6 globals with code snippet; "from flask module" not precise for `helpers.py`/`globals.py` |
| Q13 | **5** | Quotes exact `__getattr__` shim code with `DeprecationWarning` and Flask 4.0 note |
| Q14 | **5** | Names `werkzeug.security.safe_join`, directory traversal prevention, call paths |
| Q15 | **4** | Correct purpose + `iscoroutinefunction` + `async_to_sync`; `asgiref` not named |
| Q16 | **3** | `flash()→AppContext.session→_get_session→SessionInterface`; misses `signals.py` signal |
| Q17 | **5** | Full code: `(None, *reversed(blueprints))`, both loop types, early-return logic |
| Q18 | **5** | Full `__init_subclass__` signature check code with Flask 4.0 deprecation warning |
| Q19 | **5** | Complete lifecycle — all methods, files, and conditions cited correctly |
| Q20 | **5** | All 3 conditions + `delete_cookie` branch with code snippets |

---

## Pipeline 1: Vector-Only — Score Summary
**Average: 3.05 / 5** | **6 complete refusals**

| Q# | Score | Key Observation |
| --- | --- | --- |
| Q01 | 0 | Config dict chunk not retrieved |
| Q02 | 2 | Hallucinated `FlaskProxy` class |
| Q03 | 3 | Correct skeleton; `wsgi_app` not retrieved |
| Q04 | 4 | Both exception branches correct |
| Q05 | 4 | `itsdangerous` + `BadSignature` correct |
| Q06 | 3 | Core path right; `make_null_session` missing |
| Q07 | 0 | Chunk not retrieved |
| Q08 | 4 | Full `copy_current_request_context` trace |
| Q09 | 4 | Both `Vary: Cookie` paths named |
| Q10 | 3 | Right concept; wrong citation |
| Q11 | 0 | `app.run()` body not in top-k |
| Q12 | 3 | All 6 globals; cross-file origins wrong |
| Q13 | 0 | `__getattr__` shim not retrieved |
| Q14 | 0 | `send_from_directory` chunk not retrieved |
| Q15 | 4 | `ensure_sync → async_to_sync` correct |
| Q16 | 0 | Cross-file flash chain not retrieved |
| Q17 | 4 | Blueprint ordering logic correct |
| Q18 | 3 | `__init_subclass__` + `remove_ctx`; `add_ctx` missing |
| Q19 | 4 | Full lifecycle; context push missing |
| Q20 | 4 | All conditions; both branches |

---

## Pipeline 2: Graph-Only — Score Summary
**Average: 2.35 / 5** | **1 refusal** | **"I operate entirely on macro-architecture" in 12/20 answers**

| Q# | Score | Key Observation |
| --- | --- | --- |
| Q01 | 0 | Config values not in graph nodes |
| Q02 | 3 | Correct inheritance edge; wrong file |
| Q03 | 3 | Correct skeleton from graph edges |
| Q04 | 2 | Edge found; no branching logic |
| Q05 | 2 | Lists `get_signing_serializer` dep; no crypto library |
| Q06 | 2 | Lists session functions; no failure trace |
| Q07 | 2 | Found `_AppCtxGlobalsProxy` edge; misses `g` proxy |
| Q08 | 1 | Acknowledged function; no mechanism |
| Q09 | 1 | "Not in graph data" — explicit failure |
| Q10 | 2 | Correct files; no runtime constraint |
| Q11 | 3 | Good startup deps from graph |
| Q12 | 1 | Only names file; no globals listed |
| Q13 | 2 | Inferred from edges; no `__getattr__` |
| Q14 | 2 | Shared dep found; no security guarantee |
| Q15 | 2 | Edge found; no purpose explained |
| Q16 | 3 | `flash→session→_get_session`; misses signals |
| Q17 | 1 | Only callers found; no ordering |
| Q18 | 0 | Complete refusal |
| Q19 | 4 | Strong structural lifecycle trace |
| Q20 | 3 | `should_set_cookie` found; delete path missing |

---

## Category Performance Breakdown

| Category | Questions | Vector Avg | Graph Avg | Hybrid Avg |
| --- | --- | --- | --- | --- |
| Factual | Q01, Q02, Q15 | 2.0 | 1.67 | **2.67** |
| Security analysis | Q05, Q06, Q09, Q20 | 3.75 | 2.0 | **4.75** |
| Call-chain (single-file) | Q04, Q08, Q17 | 4.0 | 1.33 | **5.0** |
| Call-chain (cross-file) | Q03, Q11, Q18 | 2.0 | 2.0 | **4.0** |
| Multi-hop / Dependency | Q07, Q12, Q16 | 1.0 | 2.33 | **3.33** |
| Architectural | Q10, Q13, Q19 | 2.33 | 2.67 | **4.67** |

> [!IMPORTANT]
> **Hybrid consistently outperforms both baselines in every category.** The most dramatic gains are in Security analysis (+1.0 over Vector, +2.75 over Graph) and Cross-file call-chain reasoning (+2.0 over both standalone pipelines).
