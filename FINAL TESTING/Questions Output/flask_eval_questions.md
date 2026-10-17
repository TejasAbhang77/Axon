# Flask Codebase — RAG Evaluation Question Bank
**Research Study:** Hybrid RAG vs. Standalone Retrieval for Code Comprehension  
**Source Repository:** `data/repos/flask/src/flask/`  
**Generated For:** Comparative benchmarking of Vector-Only, Graph-Only, and Hybrid RAG pipelines  
**Total Questions:** 20

---

> [!NOTE]
> All questions are derived strictly from the Flask source code as read from the repository. No external knowledge, hallucinated APIs, or behaviors outside the codebase have been introduced.

---

## Question Taxonomy

| Type | Description |
| --- | --- |
| **Factual** | Single-hop lookup of a specific value, class, or definition |
| **Multi-hop** | Requires traversing multiple files or function calls to reach the answer |
| **Call-chain reasoning** | Requires tracing a precise execution sequence through the codebase |
| **Architectural** | Requires understanding the design role of a module or class hierarchy |
| **Security analysis** | Focuses on security-sensitive code paths, key handling, or cookie behavior |
| **Dependency tracing** | Requires identifying what a component depends on or what depends on it |

---

## Evaluation Questions

---

### Q01
**Question:** What is the default value of `SESSION_COOKIE_HTTPONLY` in the Flask application's configuration, and in which file is this default defined?

**Question Type:** Factual  
**Expected Retrieval Complexity:** Low  
**Evaluation Rationale:** Tests whether a pipeline can precisely locate a single configuration key-value pair inside `app.py`'s `default_config` `ImmutableDict`. Vector retrieval should succeed here using keyword matching on the config key. Graph retrieval is expected to fail as this is a pure data lookup, not a structural relationship. This baseline question establishes a lower bound for all three pipelines.

---

### Q02
**Question:** Which class does `Flask` directly inherit from, and which file defines that parent class?

**Question Type:** Multi-hop / Architectural  
**Expected Retrieval Complexity:** Low  
**Evaluation Rationale:** Requires identifying `Flask` in `app.py`, then locating its parent `App` in `sansio/app.py`. Graph-only retrieval should excel here as the inheritance edge is a pure structural relationship. Vector retrieval may succeed if it retrieves the class definition chunk. Hybrid is expected to explain the design intent (sansio layer) using both.

---

### Q03
**Question:** What is the complete call chain from an incoming HTTP request to the invocation of a registered view function in Flask's WSGI layer?

**Question Type:** Call-chain reasoning  
**Expected Retrieval Complexity:** High  
**Evaluation Rationale:** Requires tracing: `__call__` → `wsgi_app` → `AppContext.push` → `full_dispatch_request` → `preprocess_request` → `dispatch_request` → `view_functions[rule.endpoint]`. This is a deep, multi-hop call chain spanning `app.py` and `ctx.py`. The graph-only pipeline should identify the structural edges but lack semantic context. The hybrid pipeline is expected to outperform both by fusing the call graph with docstring-level explanations.

---

### Q04
**Question:** When `full_dispatch_request` catches an exception from `dispatch_request`, which method does it call to handle it, and what does that method do with `HTTPException` subclasses versus other exceptions?

**Question Type:** Call-chain reasoning / Control-flow  
**Expected Retrieval Complexity:** Medium  
**Evaluation Rationale:** Tests whether pipelines can trace the branching logic inside `handle_user_exception` in `app.py`. This requires understanding the conditional difference between `HTTPException` (forwarded to `handle_http_exception`) and generic `Exception` (handler lookup via `_find_error_handler`). Hybrid pipeline is expected to provide the most complete answer by combining graph edges with semantic code understanding.

---

### Q05
**Question:** How does `SecureCookieSessionInterface.open_session` validate an incoming session cookie, and what cryptographic library does it rely on?

**Question Type:** Security analysis / Dependency tracing  
**Expected Retrieval Complexity:** Medium  
**Evaluation Rationale:** Requires tracing `open_session` in `sessions.py`, through `get_signing_serializer`, which constructs an `itsdangerous.URLSafeTimedSerializer`. Tests whether pipelines can identify the external library dependency (`itsdangerous`) and explain its role in signature validation (guarding against `BadSignature`). Vector retrieval may surface the docstring; graph retrieval shows the call to `get_signing_serializer`. Hybrid is expected to produce the most complete security-aware answer.

---

### Q06
**Question:** What happens if `SECRET_KEY` is not set in the Flask application configuration when a session cookie is requested? Trace the code path that leads to this failure mode.

**Question Type:** Security analysis / Call-chain reasoning  
**Expected Retrieval Complexity:** High  
**Evaluation Rationale:** Requires a multi-hop trace: `AppContext._get_session` → `SessionInterface.open_session` → `SecureCookieSessionInterface.open_session` → `get_signing_serializer` (returns `None`) → `open_session` returns `None` → `make_null_session` is called → `NullSession._fail` raises `RuntimeError`. Critically tests whether pipelines can trace a failure path across three classes in `ctx.py` and `sessions.py`. Hybrid pipeline is expected to win because graph traversal finds the call chain and vector search finds the `NullSession` error message.

---

### Q07
**Question:** What is the role of the `_AppCtxGlobals` class in Flask, and how is an instance of it made accessible to the developer during a request?

**Question Type:** Architectural / Multi-hop  
**Expected Retrieval Complexity:** Medium  
**Evaluation Rationale:** Requires connecting `_AppCtxGlobals` in `ctx.py` to its instantiation inside `AppContext.__init__` (as `self.g`), and then understanding that it is accessed via the `g` proxy from `globals.py`. Tests cross-file architectural understanding. Graph retrieval should find structural instantiation edges. Vector retrieval may surface the docstring. Hybrid is expected to provide the most coherent architectural explanation.

---

### Q08
**Question:** How does `copy_current_request_context` ensure that a background task spawned from a view function can still access `flask.request` and `flask.session`?

**Question Type:** Multi-hop / Call-chain reasoning  
**Expected Retrieval Complexity:** High  
**Evaluation Rationale:** Tests understanding of `copy_current_request_context` in `ctx.py`, which copies the active `AppContext` and wraps the function in a `with ctx:` block. Requires understanding context variable isolation (`contextvars`), the `AppContext.copy()` method, and the lifecycle of context variables. The hybrid pipeline is expected to outperform because graph structure traces the method calls and vector semantics explain the concurrency warning in the docstring.

---

### Q09
**Question:** When does Flask add a `Vary: Cookie` header to an HTTP response, and which function in `sessions.py` is responsible for this behavior?

**Question Type:** Security analysis / Factual  
**Expected Retrieval Complexity:** Medium  
**Evaluation Rationale:** Requires identifying `save_session` in `SecureCookieSessionInterface`, which checks `session.accessed` to add `response.vary.add("Cookie")`. Tests whether pipelines can combine factual attribute retrieval (`accessed` flag) with understanding the security implication (caching layer defense against session data leakage). Graph retrieval gives the structural path; vector gives the semantic meaning. Hybrid is expected to explain both the mechanism and its intent.

---

### Q10
**Question:** What is the difference between `after_this_request` and `app.after_request`, and what runtime constraint does `after_this_request` enforce?

**Question Type:** Architectural / Factual  
**Expected Retrieval Complexity:** Medium  
**Evaluation Rationale:** Requires reading the docstring and implementation of `after_this_request` in `ctx.py`, which checks `ctx.has_request` and raises a `RuntimeError` if not inside a request context. Contrasting with `app.after_request` (registered on the app for all requests) requires cross-file architectural awareness. Tests whether vector-only retrieval can surface the contextual difference between global and per-request decorators, which the graph pipeline would struggle to differentiate semantically.

---

### Q11
**Question:** Trace the call chain that Flask follows when `app.run()` is invoked, up to the point where the underlying Werkzeug server is started.

**Question Type:** Call-chain reasoning  
**Expected Retrieval Complexity:** Medium  
**Evaluation Rationale:** Requires reading `Flask.run()` in `app.py` — including its check for `FLASK_RUN_FROM_CLI`, the call to `cli.load_dotenv()`, debug flag resolution, `cli.show_server_banner()`, and finally `werkzeug.serving.run_simple()`. Tests sequential reasoning across multiple conditional branches within a single method. Graph-only pipeline is expected to find the outbound call edges; vector retrieval finds the docstring. Hybrid is expected to provide the most complete narrative answer.

---

### Q12
**Question:** Which functions are registered as Jinja2 global variables when `create_jinja_environment` is called, and which files do those functions originate from?

**Question Type:** Dependency tracing / Multi-hop  
**Expected Retrieval Complexity:** Medium  
**Evaluation Rationale:** Requires reading `Flask.create_jinja_environment` in `app.py` and identifying that `url_for`, `get_flashed_messages`, `config`, `request`, `session`, and `g` are injected. Then requires tracing imports back to `helpers.py` and `globals.py`. Tests whether pipelines can perform import-level dependency tracing. Graph retrieval excels at tracing imports structurally; vector retrieval may miss the origin files. Hybrid is expected to clearly attribute each variable to its source module.

---

### Q13
**Question:** What architectural decision in Flask 3.2 merged `RequestContext` into `AppContext`, and what backward-compatibility mechanism was put in place for code that still references `RequestContext`?

**Question Type:** Architectural / Factual  
**Expected Retrieval Complexity:** Medium  
**Evaluation Rationale:** Requires reading the module-level `__getattr__` function at the bottom of `ctx.py`, which emits a `DeprecationWarning` when `RequestContext` is accessed and returns `AppContext`. Tests whether pipelines can surface historically significant architectural changes documented in module-level functions rather than classes or docstrings. Vector retrieval should find the deprecation message; graph retrieval may miss the `__getattr__` function. Hybrid is expected to provide the richest answer combining the structural note and the semantic deprecation context.

---

### Q14
**Question:** How does `send_from_directory` in `helpers.py` differ from directly calling `send_file`, and what security guarantee does it provide?

**Question Type:** Security analysis / Dependency tracing  
**Expected Retrieval Complexity:** Medium  
**Evaluation Rationale:** Requires reading `send_from_directory` in `helpers.py`, which delegates to `werkzeug.utils.send_from_directory` via `_prepare_send_file_kwargs`. The security guarantee is path sanitization using `safe_join` (documented in the docstring). Tests whether pipelines can surface a security-relevant docstring distinction between two related functions and trace the delegation chain. Vector retrieval excels at docstring-level comparisons; graph retrieval traces the call delegation.

---

### Q15
**Question:** What is the purpose of the `ensure_sync` method in the `Flask` class, and what does it call when it receives an `async def` function?

**Question Type:** Factual / Dependency tracing  
**Expected Retrieval Complexity:** Low  
**Evaluation Rationale:** Requires reading `Flask.ensure_sync` in `app.py`, which checks `iscoroutinefunction` and delegates to `async_to_sync`, which in turn imports and calls `asgiref.sync.async_to_sync`. Tests a two-hop lookup that bridges Flask's synchronous WSGI interface with async support. This question has a clear factual answer but also a dependency (on `asgiref`) that requires cross-file tracing. Establishes the utility of combining semantic search with structural call edges.

---

### Q16
**Question:** What is the complete dependency chain from `flask.flash()` to storing data in the session, including which global proxies are accessed and in which files they are defined?

**Question Type:** Dependency tracing / Multi-hop  
**Expected Retrieval Complexity:** High  
**Evaluation Rationale:** Requires tracing `flash()` in `helpers.py` → `session.get("_flashes", [])` (via `globals.py` proxy) → `session["_flashes"] = flashes` → `message_flashed.send(...)` (via `signals.py`). This is a full multi-hop chain across `helpers.py`, `globals.py`, and `signals.py`. The graph-only pipeline should find structural edges but lack the semantic explanation of why data is written this way (avoiding mutable structure sync issues documented in the comment). Hybrid is expected to provide the best answer.

---

### Q17
**Question:** How does `preprocess_request` determine which before-request functions to run, and in what order does it process them when a Blueprint is involved?

**Question Type:** Call-chain reasoning / Architectural  
**Expected Retrieval Complexity:** High  
**Evaluation Rationale:** Requires locating `preprocess_request` in `sansio/app.py` (or `app.py`) and understanding that it iterates over `(None,)` followed by `reversed(ctx.request.blueprints)`, calling all registered `before_request_funcs` for each name. Tests multi-level architectural understanding: the general app level vs. blueprint-specific hooks, and the significance of the reversed blueprint order. Graph-only retrieval should trace the function call to `before_request_funcs`; vector retrieval finds the docstring. Hybrid is expected to explain the ordering rationale.

---

### Q18
**Question:** If a Flask subclass overrides `dispatch_request` without including `ctx: AppContext` as its first parameter, what happens at class definition time, and which mechanism triggers this behavior?

**Question Type:** Architectural / Call-chain reasoning  
**Expected Retrieval Complexity:** High  
**Evaluation Rationale:** Requires reading `Flask.__init_subclass__` in `app.py`, which inspects method signatures of overridden methods using `inspect.signature`. If the second parameter (after `self`) is not annotated as `AppContext` or named `ctx`, it emits a `DeprecationWarning` and wraps the method with `remove_ctx` / `add_ctx` decorators to preserve backward compatibility. This is a deeply embedded metaclass-style mechanism that only the hybrid pipeline is expected to explain fully — graph traversal finds the `remove_ctx`/`add_ctx` call edges, and vector search finds the deprecation warning semantics.

---

### Q19
**Question:** Describe the full lifecycle of a session cookie from the moment a request arrives until the response is sent back to the client, citing the specific methods and files involved.

**Question Type:** Call-chain reasoning / Security analysis  
**Expected Retrieval Complexity:** High  
**Evaluation Rationale:** Requires a full multi-hop trace spanning `ctx.py` (`AppContext.push` → `_get_session` → `si.open_session`) and `app.py` (`finalize_request` → `process_response`) to `sessions.py` (`save_session`, `should_set_cookie`, `get_expiration_time`, `get_signing_serializer`, `response.set_cookie`). This end-to-end security lifecycle question is the most demanding in the evaluation set. The graph-only pipeline is expected to recover the call chain skeleton; vector-only may recover the semantic meaning of individual methods. Only the hybrid pipeline is expected to synthesize a complete, accurate, and well-attributed lifecycle answer.

---

### Q20
**Question:** What conditions must be true for `SecureCookieSessionInterface.save_session` to actually write a `Set-Cookie` header to the response, and what happens when the session is modified to be empty?

**Question Type:** Security analysis / Control-flow  
**Expected Retrieval Complexity:** Medium  
**Evaluation Rationale:** Requires reading the conditional logic inside `save_session` in `sessions.py`: if `not session` (empty) AND `session.modified`, then `delete_cookie` is called; if not empty, `should_set_cookie` determines whether to write the cookie (based on `modified` or `permanent` + `SESSION_REFRESH_EACH_REQUEST`). Tests whether pipelines can trace branching control-flow within a single security-critical method and articulate the different behavioral outcomes. Vector retrieval should surface the method body; graph retrieval shows the call to `should_set_cookie`. Hybrid is expected to clearly explain all branches and their security implications.

---

## Summary Table

| Q# | Question Focus | Type | Complexity | Primary File(s) |
| --- | --- | --- | --- | --- |
| Q01 | Default `SESSION_COOKIE_HTTPONLY` value | Factual | Low | `app.py` |
| Q02 | Flask class inheritance hierarchy | Multi-hop / Architectural | Low | `app.py`, `sansio/app.py` |
| Q03 | Full request-to-view-function call chain | Call-chain reasoning | High | `app.py`, `ctx.py` |
| Q04 | Exception handling branching in `full_dispatch_request` | Call-chain / Control-flow | Medium | `app.py` |
| Q05 | Session cookie cryptographic validation | Security analysis | Medium | `sessions.py` |
| Q06 | Missing `SECRET_KEY` failure path | Security / Call-chain | High | `sessions.py`, `ctx.py` |
| Q07 | Role of `_AppCtxGlobals` and `g` proxy | Architectural / Multi-hop | Medium | `ctx.py`, `globals.py` |
| Q08 | `copy_current_request_context` background task safety | Multi-hop / Call-chain | High | `ctx.py` |
| Q09 | `Vary: Cookie` header and `session.accessed` | Security analysis | Medium | `sessions.py` |
| Q10 | `after_this_request` vs `app.after_request` | Architectural | Medium | `ctx.py` |
| Q11 | `app.run()` call chain to Werkzeug server | Call-chain reasoning | Medium | `app.py` |
| Q12 | Jinja2 global variables injection and origins | Dependency tracing | Medium | `app.py`, `helpers.py`, `globals.py` |
| Q13 | `RequestContext` → `AppContext` merger in Flask 3.2 | Architectural | Medium | `ctx.py` |
| Q14 | `send_from_directory` security guarantee vs `send_file` | Security / Dependency | Medium | `helpers.py` |
| Q15 | `ensure_sync` and async view support | Factual / Dependency | Low | `app.py` |
| Q16 | `flash()` to session storage dependency chain | Dependency tracing | High | `helpers.py`, `globals.py`, `signals.py` |
| Q17 | `preprocess_request` blueprint hook ordering | Call-chain / Architectural | High | `sansio/app.py` |
| Q18 | `__init_subclass__` method signature enforcement | Architectural / Call-chain | High | `app.py` |
| Q19 | Full session cookie request-to-response lifecycle | Call-chain / Security | High | `ctx.py`, `app.py`, `sessions.py` |
| Q20 | `save_session` `Set-Cookie` write conditions | Security / Control-flow | Medium | `sessions.py` |

---

## Evaluation Protocol Notes

- **Scoring Dimensions:** Accuracy, Completeness, Source Attribution, Reasoning Depth (4-point Likert scale per dimension)
- **Expected Pipeline Rankings:**
  - **Low complexity questions (Q01, Q02, Q15):** Vector ≈ Hybrid > Graph
  - **Medium complexity questions (Q04, Q05, Q09, Q10, Q11, Q12, Q13, Q14, Q17, Q20):** Hybrid > Vector ≥ Graph
  - **High complexity questions (Q03, Q06, Q07, Q08, Q16, Q18, Q19):** Hybrid >> Vector > Graph
- **Reproducibility:** All questions are tied to specific, versioned source files in the Flask repository. Answers can be ground-truthed by manual code inspection.
