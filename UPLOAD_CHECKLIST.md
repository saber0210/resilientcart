# GitHub Upload Checklist

- [ ] Extract the ZIP; upload the **contents of the `resilientcart` folder**, not the ZIP itself.
- [ ] Read the architecture and run the services before presenting the project as your work.
- [ ] Change the repository description to: `Event-driven checkout platform demonstrating Saga choreography, transactional outboxes, idempotency, retries, DLQs, and observability.`
- [ ] Replace the copyright holder in `LICENSE` with your name if desired.
- [ ] Run `cp .env.example .env` and `docker compose up --build -d`.
- [ ] Open `http://localhost:8080` and complete both successful and failed-payment demos.
- [ ] Run `pytest -q` and the scripts in the README.
- [ ] Add your real measurements to `BENCHMARKS.md`; never upload invented results.
- [ ] Capture one screenshot of the web demo, one Jaeger trace, and one Grafana dashboard.
- [ ] Create `docs/images/`, add the screenshots, and reference them near the top of `README.md`.
- [ ] Create a new public GitHub repository named `resilientcart` without auto-generating a README.
- [ ] Initialize Git and push using the commands below.
- [ ] Add repository topics: `system-design`, `microservices`, `event-driven`, `rabbitmq`, `postgresql`, `fastapi`, `opentelemetry`, `docker`, `kubernetes`.
- [ ] Pin the repository to your GitHub profile.
- [ ] Use only benchmark claims you can reproduce during an interview.

## Push commands

```bash
cd resilientcart
git init
git add .
git commit -m "Build event-driven checkout platform"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/resilientcart.git
git push -u origin main
```

Your resume link will then be:

```text
https://github.com/YOUR_USERNAME/resilientcart
```
