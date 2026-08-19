# "From One Agent to an AI Engineering Team"
## Demo Plan — Parallel Agents + Git Worktrees + Herdr

---

## Core Idea

**One sentence:** Un supervisor recibe un issue, lo divide en tareas, crea un worktree por tarea, lanza agentes en paralelo y coordina la integración.

**Lo que enseña:**
- Git worktrees para aislamiento (sin clonar el repo)
- Paralelismo real entre agentes independientes
- Dependencias entre tareas (no todo es paralelo)
- Supervisor ≠ Worker (coordina, no codifica)
- Herdr como runtime visual del equipo

---

## Arquitectura de la Demo

```
                    SUPERVISOR AGENT
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
       Agent #1       Agent #2       Agent #3
       Products       Inventory      Customers
           │              │              │
           ▼              ▼              ▼
    worktree/products  worktree/inv  worktree/customers
           │
           └──────────► Agent #4
                         Orders
                           │
                           ▼
                     REVIEW AGENT
                           │
                    ┌──────┴──────┐
                    ▼             ▼
                  PASS          REJECT → Worker fixes
                    │
                    ▼
                  MERGE
```

**Nivel 1 — Paralelo** (independientes):
```
Products   ────────►
Inventory  ────────►
Customers  ────────►
```

**Nivel 2 — Dependiente:**
```
Products ──► Orders
```

El supervisor detecta esta dependencia y no lanza Orders hasta que Products esté listo.

---

## El Repo: Smart Store (este mismo)

El repo ya existe. La gracia es que el supervisor recibe:

```
"Implement the missing endpoints for products, orders and inventory. Add tests."
```

Y decide qué tareas son paralelas y cuáles dependen de otras.

**Worktrees que crea:**
```
feat/products   → Agent implements GET /products, POST /products
feat/inventory  → Agent implements PATCH /inventory/{sku}
feat/customers  → Agent implements GET /customers/{id}
feat/orders     → Agent implements GET /orders/{id}, PATCH /orders/{id}
```

---

## Implementación con Herdr

### Comandos Herdr relevantes

| Comando | Qué hace |
|---------|----------|
| `herdr worktree create --branch feat/products --label "Products"` | Crea git worktree + abre workspace en Herdr |
| `herdr agent start products-agent --kind claude-code --pane <id>` | Lanza Claude Code en ese pane |
| `herdr agent prompt products-agent "<prompt>" --wait` | Envía prompt y bloquea hasta que termina |
| `herdr agent wait products-agent` | Espera a que el agente quede idle/done |
| `herdr agent read products-agent` | Lee el output del agente |
| `herdr workspace list` | Ve todos los workspaces activos |

### Lo que Herdr aporta visualmente

```
┌──────────────────────────────────────────────────────────────┐
│ HERDR                                                        │
├───────────────┬──────────────────────────────────────────────┤
│               │                                              │
│ supervisor ●  │  Supervisor                                  │
│               │  > Decomposing tasks...                      │
│ products  ●   │  > Creating worktrees                        │
│               │                                              │
│ inventory ●   │  > Starting parallel agents                  │
│               │                                              │
│ customers ✓   │  > Tests passed (8 tests)                    │
│               │                                              │
│ orders    ○   │  > Waiting for products...                   │
│               │                                              │
│ reviewer  ○   │                                              │
│               │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

### supervisor.py — estructura real

```python
import asyncio
import subprocess
import json

async def create_worktree_in_herdr(branch: str, label: str) -> str:
    result = subprocess.run(
        ["herdr", "worktree", "create", "--branch", branch, "--label", label],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    return data["workspace_id"]  # Herdr devuelve el workspace_id

async def launch_agent(workspace_id: str, name: str, prompt_file: str) -> None:
    prompt = open(f"scripts/prompts/{prompt_file}").read()
    # Start Claude Code agent in that workspace's pane
    subprocess.run(["herdr", "agent", "start", name, "--kind", "claude-code",
                    "--pane", workspace_id])
    # Send prompt (non-blocking — Herdr maneja el estado)
    subprocess.run(["herdr", "agent", "prompt", name, prompt])

async def wait_for_agent(name: str) -> str:
    subprocess.run(["herdr", "agent", "wait", name])  # bloquea hasta idle/done
    result = subprocess.run(["herdr", "agent", "read", name],
                            capture_output=True, text=True)
    return result.stdout

async def run_supervisor(tasks_file: str) -> None:
    tasks = json.load(open(tasks_file))

    # Nivel 1: lanzar tareas independientes en paralelo
    parallel_group = [t for t in tasks if not t.get("depends_on")]
    await asyncio.gather(*[
        launch_and_run(t) for t in parallel_group
    ])

    # Nivel 2: lanzar tareas dependientes
    dependent_group = [t for t in tasks if t.get("depends_on")]
    for task in dependent_group:
        await launch_and_run(task)

    # Review agent
    await launch_and_run({"name": "reviewer", "prompt": "reviewer.md"})
```

### Archivos a crear

```
scripts/
├── supervisor.py        # Orquestador — usa herdr CLI
├── tasks.json           # Grafo de tareas + dependencias
└── prompts/
    ├── products.md      # "Implement GET /products, POST /products, tests"
    ├── inventory.md     # "Implement PATCH /inventory/{sku}, tests"
    ├── customers.md     # "Implement GET /customers/{id}, tests"
    ├── orders.md        # "Implement GET /orders/{id}, PATCH /orders/{id}, tests"
    └── reviewer.md      # "Review diffs, check tests, open PRs"
```

### tasks.json

```json
[
  {"name": "products",  "branch": "feat/products",  "prompt": "products.md",  "depends_on": null},
  {"name": "inventory", "branch": "feat/inventory", "prompt": "inventory.md", "depends_on": null},
  {"name": "customers", "branch": "feat/customers", "prompt": "customers.md", "depends_on": null},
  {"name": "orders",    "branch": "feat/orders",    "prompt": "orders.md",    "depends_on": ["products"]}
]
```

---

## Flujo de la Demo (10 minutos)

| Tiempo | Qué pasa | Qué explicas |
|--------|----------|--------------|
| 0-1m   | Problema: un agente, secuencial, lento | Motivation |
| 1-3m   | `git worktree list` — múltiples working trees | Aislamiento sin clonar |
| 3-4m   | Herdr: workspace con 4 agentes | El "equipo" como entidad |
| 4-6m   | Supervisor descompone la tarea | Grafo de dependencias |
| 6-8m   | Agentes trabajando en paralelo (Herdr) | Paralelismo real |
| 8-9m   | Conflict controlado en README.md | Por qué necesitamos review agent |
| 9-10m  | Review agent integra y abre PRs | Feedback loop, human in the loop |

---

## El Momento "Wow" de la Demo

Todos los agentes modifican `README.md` simultáneamente.

```
products  → README.md (adds Products section)
inventory → README.md (adds Inventory section)
customers → README.md (adds Customers section)
```

El review agent recibe los tres diffs y tiene que integrarlos.

Esto permite explicar:

> **"El aislamiento resuelve la ejecución. La integración sigue siendo un problema."**

Y el review agent es la solución.

---

## 6 Reglas de Orquestación (Slide al Final)

1. **Tasks bounded** — un agente, una tarea, un worktree
2. **Parallelize only independent work** — detectar dependencias antes de lanzar
3. **Supervisor coordinates, never codes** — plan → delegate → monitor → review → integrate
4. **Agents produce verifiable outputs** — tests passed, files changed, commit hash
5. **Feedback loops** — reviewer puede rechazar y mandar de vuelta al worker
6. **Human in the loop** — architecture, security, production, destructive actions

---

## Lo Que Implementamos en Este Repo

Para la demo mínima viable necesitamos:

```
scripts/
├── supervisor.py        # Orquestador principal
├── tasks.json           # Definición de tareas + dependencias
└── prompts/
    ├── products.md      # Prompt para el agente de products
    ├── inventory.md     # Prompt para el agente de inventory
    ├── customers.md     # Prompt para el agente de customers
    ├── orders.md        # Prompt para el agente de orders
    └── reviewer.md      # Prompt para el review agent
```

El supervisor crea los worktrees, lanza `claude --print` con cada prompt, espera los resultados, y coordina la integración.

**Scope intencional:** Los endpoints que ya existen en el repo son el "antes". Los agentes implementan los que faltan. El reviewer abre los PRs.

---

## Siguiente Paso

1. Crear `scripts/tasks.json` con el grafo de dependencias
2. Crear `scripts/prompts/*.md` — uno por agente
3. Crear `scripts/supervisor.py` — orquestador con Herdr CLI
4. Probar con un worktree primero antes de la demo completa

**Prerequisito:** Herdr instalado y corriendo, con `HERDR_ENV=1` en el entorno.
