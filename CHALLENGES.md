# Challenges

Through out this project I hit a lot of road blocks that made me change the approach to get the TAS working on OpenShift.

- Scraping Metrics
- Prometheus Adapter
- Scheduler Extender

## Scraping Metrics

The TAS requires telemetry information for policy consumption, telemetry provided using a [metrics pipeline](https://github.com/intel/platform-aware-scheduling/blob/master/telemetry-aware-scheduling/docs/custom-metrics.md). 
OpenShift provides a pre-integrated monitoring stack based on Prometheus, the idea for this project was to re-use the supported stack from OpenShift without having to redeploy another Prometheus Operator instance. 
OpenShift platform components are Platform Operators (or Cluster Operators), even core kubernetes components (apart the kubelet), The [CMO](https://github.com/openshift/cluster-monitoring-operator) (Cluster Monitoring Operator) unless specified is managed by the [CVO](https://github.com/openshift/cluster-version-operator) (Cluster Version Operator), CVO purpose is to check with the OCP update service to see the valid updates and update paths based on current component versions and information in the graph. When CVO detects a new compatible update, it will use the release image for that update and upgrades the cluster.

To implement the Metrics Pipeline from the Intel documentation we need to add an [additionalScrapeConfig](https://github.com/prometheus-operator/prometheus-operator/blob/main/Documentation/additional-scrape-config.md), but the cluster-monitoring-operator (based on Prometheus Operator) doesn't allow to change that configuration unless you set the Operator in Unmanaged mode. 
When an Operator is unmanaged it cannot be upgraded, for example if you are doing a cluster upgrade it will fail on the cluster-monitoring-operator, this is not desirable from both supportability and life cycle management perspective.

Since I tried this approach, for information purpose, here below more details

### Disable CVO for cluster-monitoring-operator and apply additionalScrapeConfigs

```
# oc patch clusterversion version --type=merge -p '{"spec": {"overrides":[{"kind": "Deployment", "name": "cluster-monitoring-operator", "namespace": "openshift-monitoring", "unmanaged": true, "group": "apps"}]}}'
# oc scale --replicas=0 deployment/cluster-monitoring-operator
```

Remember to scale the deployment to 0 or our custom configuration will be still overwritten.

Create now a file called prometheus-additional.yaml:

```
- job_name: 'kubernetes-collectd-node-exporter'
  bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
  scheme: http
  kubernetes_sd_configs:
  - role: node
  relabel_configs:
  - source_labels: [__address__]
    regex: ^(.*):\d+$
    target_label: __address__
    replacement: $1:9103
    # Host name
  - source_labels: [__meta_kubernetes_node_name]
    target_label: node
```

Convert to base64 and create the following secret named `additional-scrape-configs`:

```yaml
apiVersion: v1
data:
  prometheus-additional.yaml: LSBqb2JfbmFtZTogJ2t1YmVybmV0ZXMtY29sbGVjdGQtbm9kZS1leHBvcnRlcicKICB0bHNfY29uZmlnOgogICAgY2FfZmlsZTogL2V0Yy9wcm9tZXRoZXVzL2NvbmZpZ21hcHMvc2VydmluZy1jZXJ0cy1jYS1idW5kbGUvc2VydmljZS1jYS5jcnQKICBiZWFyZXJfdG9rZW5fZmlsZTogL3Zhci9ydW4vc2VjcmV0cy9rdWJlcm5ldGVzLmlvL3NlcnZpY2VhY2NvdW50L3Rva2VuCiAgc2NoZW1lOiBodHRwCiAga3ViZXJuZXRlc19zZF9jb25maWdzOgogIC0gcm9sZTogbm9kZQogIHJlbGFiZWxfY29uZmlnczoKICAtIHNvdXJjZV9sYWJlbHM6IFtfX2FkZHJlc3NfX10KICAgIHJlZ2V4OiBeKC4qKTpcZCskCiAgICB0YXJnZXRfbGFiZWw6IF9fYWRkcmVzc19fCiAgICByZXBsYWNlbWVudDogJDE6OTEwMwogICAgIyBIb3N0IG5hbWUKICAtIHNvdXJjZV9sYWJlbHM6IFtfX21ldGFfa3ViZXJuZXRlc19ub2RlX25hbWVdCiAgICB0YXJnZXRfbGFiZWw6IG5vZGUK
kind: Secret
metadata:
  name: additional-scrape-configs
  namespace: openshift-monitoring
type: Opaque
```

Apply the secret to the cluster and verify the configuration is loaded correctly on Prometheus.

```
# oc -n openshift-monitoring get secret prometheus-k8s -ojson | jq -r '.data["prometheus.yaml.gz"]' | base64 -d | gunzip | less
```

Search for `additionalScrapeConfigs` and you should see:

```yaml
  additionalScrapeConfigs:
    name: additional-scrape-configs
    key: prometheus-additional.yaml
```

If you don't set the Operator in Unmanaged mode and scale the deployment to 0, it will show the config and then it will disappear again once it reconcile, just few minutes.

The scrape config basically pulls the metrics from our collectd exporter running on the nodes on port 9103

This part was working on the cluster what I just couldn't get it to work was the configuration for the prometheus adapter.

## Prometheus Adapter

....

## Scheduler Extender

Intel-TAS is implemented using a [scheduler extender](https://github.com/kubernetes/design-proposals-archive/blob/main/scheduling/scheduler_extender.md), basically webhooks to filter/prioritize node selection, configured in [KubeSchedulerConfiguration](https://kubernetes.io/docs/reference/config-api/kube-scheduler-config.v1beta2/). 

.....
