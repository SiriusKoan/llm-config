# Entrypoint Conventions by Framework

Where to look for the route table, the middleware chain, and the process start. Use to find a
candidate fast, then confirm it the normal way: the handler must be reachable from a real
process start.

Grep the scenario's literal string first (a path, a subcommand, an event name). These tables are
the fallback when nothing is quotable, and the confirmation step when something is.

## HTTP — Python

| Framework | Routes declared | Middleware chain | Process start |
|---|---|---|---|
| Django | `urls.py` `urlpatterns`, nested by `include()` from `ROOT_URLCONF` | `settings.MIDDLEWARE`, top-down on request | `wsgi.py` / `asgi.py`; `manage.py runserver` |
| DRF | `routers.register()` + `ViewSet` methods; `@api_view` | Django's, plus `permission_classes` / `authentication_classes` on the view | as Django |
| FastAPI | `@app.get`/`@router.post` decorators; `include_router()` assembles the tree | `@app.middleware`, `Depends()` chains, `dependencies=` on router | `uvicorn main:app`; check `pyproject.toml` scripts / Dockerfile CMD |
| Flask | `@app.route`, `Blueprint` + `register_blueprint` | `@before_request`, WSGI middleware wrapping `app.wsgi_app` | `app.run()`, `flask run`, gunicorn target |

Django's real dispatch order is worth knowing when middleware matters: `MIDDLEWARE` top-down →
URL resolution → view. Auth decisions usually sit in middleware *or* in the view's
`permission_classes`, not both — check both before concluding.

## HTTP — JS / TS

| Framework | Routes declared | Middleware chain | Process start |
|---|---|---|---|
| Express | `app.get()` / `router.post()`; mounted via `app.use('/base', router)` | `app.use()` in **registration order** — order is the semantics | `app.listen()`; `package.json` scripts |
| NestJS | `@Controller('base')` + `@Get()`; modules wire them | `@UseGuards`, `@UseInterceptors`, `@UsePipes`, global in `main.ts` | `main.ts` `NestFactory.create` |
| Next.js | `app/**/route.ts` (App Router) or `pages/api/**` — path *is* the file path | `middleware.ts` at root, `matcher` config | framework-managed |
| Fastify | `fastify.route()` / `register()` plugins | hooks (`onRequest`, `preHandler`) | `fastify.listen()` |

Express mounting is the classic trace-breaker: `app.use('/v1', router)` means the route file's
`'/users'` is really `/v1/users`. Grep the leaf path, then find the mount to reconstruct the full one.

## HTTP — JVM / Ruby / PHP / .NET / Go

| Framework | Routes declared | Middleware chain | Process start |
|---|---|---|---|
| Spring Boot | `@RestController` + `@GetMapping("/path")`; `@RequestMapping` on class prefixes | `Filter`/`HandlerInterceptor`; Spring Security `SecurityFilterChain` bean | `@SpringBootApplication` class `main` |
| Rails | `config/routes.rb` — `resources :x` expands to 7 routes; `rails routes` prints the truth | `ApplicationController` `before_action`, `config/application.rb` middleware stack | `config.ru`, `bin/rails server` |
| Laravel | `routes/web.php`, `routes/api.php` | `app/Http/Kernel.php` groups; `->middleware()` per route | `public/index.php` |
| ASP.NET Core | `[HttpGet("path")]` on controllers, or `app.MapGet()` minimal API | `app.Use...()` in `Program.cs` — order matters | `Program.cs` `main` |
| Go net/http | `mux.HandleFunc("/path", h)` | handler wrapping: `mw(mw(h))` — read inside-out | `main()` `http.ListenAndServe` |
| Go chi / gin / echo | `r.Get("/path", h)`, `r.Route()` subtrees | `r.Use()` in order; `Group()` scopes | `main()` |

`rails routes`, `php artisan route:list`, and Spring's startup mapping log are faster and more
truthful than grepping — run them if the app is runnable.

## Non-HTTP entrypoints

| Kind | Registration | Start |
|---|---|---|
| Celery | `@app.task`; routed by name string in `apply_async('name')` / `send_task` | `celery -A proj worker`; queues in `task_routes` |
| Sidekiq / ActiveJob | `class XJob < ApplicationJob`, `perform_later` | `sidekiq -q queue` |
| Kafka / RabbitMQ / SQS | consumer subscribes by topic/queue **string** — grep it for both producer and consumer | consumer loop in a worker main |
| Cron / scheduler | crontab, `@scheduled`, `celery beat`, k8s `CronJob` spec | scheduler process |
| AWS Lambda | the `handler` field in `template.yaml` / `serverless.yml` / Terraform — the config names the function | runtime invokes it |
| gRPC | `.proto` `service` + `rpc`; server registers a generated base-class impl | `server.add_insecure_port` / `Serve()` |
| GraphQL | resolver map keyed by field name, or `@Resolver` classes; schema SDL names the field | HTTP server underneath |
| CLI (click/typer/argparse) | `@click.command`, `subparsers.add_parser("name")` | `if __name__ == "__main__"`; console_scripts in `pyproject.toml` / `setup.py` |
| CLI (cobra) | `&cobra.Command{Use: "name", Run: fn}` | `rootCmd.Execute()` in `main()` |
| Polling daemon | there is no registration — find the `while True` / ticker loop; grep the interval config name | the daemon main |
| Webhook receiver | an HTTP route, but the branch is on a **payload field** (`event`, `action`, `type`) — grep that field's values | as HTTP |

For queues, buses, and Lambdas the producer and consumer are joined only by a **string**. That
string is the trace's only bridge — grep it in both directions before assuming who sends what.

## Finding the start when nothing above matches

In rough order of reliability:

1. Container / deploy config — `Dockerfile` `CMD`/`ENTRYPOINT`, k8s `command`, Procfile, systemd `ExecStart`. This is what actually runs.
2. Manifest scripts — `package.json` `scripts`, `pyproject.toml` `[project.scripts]`, `justfile`, `Makefile`.
3. `README` "How it works" / architecture section — often names the loop or the flow.
4. Tests — an integration test named after the scenario constructs the entrypoint call. Read its setup.
5. `main`, `__main__`, `index`, `app`, `server`, `cmd/` — grep by convention.
