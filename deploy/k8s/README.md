# Demo Kubernetes Deployment

These manifests are intended for a local Kind or Minikube demonstration. They deploy single-node PostgreSQL, RabbitMQ, and Jaeger instances and are not a production high-availability topology.

## Kind example

```bash
docker build -t resilientcart:local .
kind create cluster --name resilientcart
kind load docker-image resilientcart:local --name resilientcart
kubectl apply -k deploy/k8s
kubectl -n resilientcart rollout status deployment/gateway --timeout=180s
kubectl -n resilientcart port-forward service/gateway 8080:8000
```

Open `http://localhost:8080`.

In another terminal, expose supporting interfaces when needed:

```bash
kubectl -n resilientcart port-forward service/jaeger 16686:16686
kubectl -n resilientcart port-forward service/rabbitmq 15672:15672
```

The HPAs require a Kubernetes metrics server. Without one, the application still runs but the HPAs will report that metrics are unavailable.

## Clean up

```bash
kind delete cluster --name resilientcart
```

Before deploying outside a local environment, replace `secret.demo.yaml`, use managed or clustered data services, add network policies and PodDisruptionBudgets, and publish the application image to a trusted registry.
