# M4 · Route planner

Builds the distance matrix with OSRM, solves the vehicle routing problem with OR-Tools (time windows, capacity, cold chain, fuel and driver cost) and writes proposed delivery runs for staff to approve.

| | |
| --- | --- |
| Phase | Phase 3 |
| Database access | reads `app.order*`, `app.vehicle`, `app.depot`, `app.setting`; writes `app.delivery`, `app.delivery_stop`, `ops.route_matrix_cache` |
| Runs as | `lozhka-worker-routing` |
| Design | `03_modules.md section 4` in the documentation folder |

Rules: import only from `libs/`, never from another service. Document new tables touched and new settings here.
