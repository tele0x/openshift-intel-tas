# Intel-TAS (Telemetry Aware Scheduling) on Red Hat OpenShift Container Platform

The Intel-TAS is an extender of the default K8S scheduler that consumes platform metrics and makes intelligent scheduling/descheduling decisions based on defined policies. The Intel-TAS runs within the same cluster. For distributed use cases the architecture will use a centralized control plane with RWN (Remote Worker Node) this way the TAS could intelligently distribute workload.

Example use cases:

- Sustainability awareness for workload placement (power, temperature, weather etc..)
- Guarantee SLAs (an example use case for 5G Network Slicing). (throughput, packets loss, latency)
- Workload placement based on ML models (holistic network/apps view)

Review the following documentation from Intel on how to configure the TAS policies:

- Official [Intel-TAS repo](https://github.com/intel/platform-aware-scheduling/tree/master/telemetry-aware-scheduling)
- [Telemetry Aware Scheduling whitepaper](https://builders.intel.com/docs/networkbuilders/telemetry-aware-scheduling-automated-workload-optimization-with-kubernetes-k8s-technology-guide.pdf)

This repository provides the instructions to run Intel-TAS on Red Hat OpenShift Container Platform.

## Table of Contents

<!-- TOC -->

- [Architecture](#architecture)
- [Summary](#summary)
- [Getting Started](#getting-started)
- [Telemetry](#telemetry)
  - [Activate User Workload Monitoring](#activate-user-workload-monitoring)
  - [Deploy Collectd](#install-collectd-chart)
  - [Deploy Metrics Proxy](#deploy-metrics-proxy)
- [Scheduling](#Scheduling)
  - [Deploy Intel-TAS](#deploy-intel-tas)
  - [Deploy Secondary Scheduler Operator](#deploy-secondary-scheduler-operator)
  - [Deploy Descheduler Operator](#deploy-descheduler-operator)
- [Demo 1](#demo-1)
- [Challenges](#challenges)

<!-- TOC -->

## Architecture

![OpenShift Intel-TAS Architecture](img/OpenShift_Intel-TAS_Architecture.png)

> NOTE: OpenShift already comes with an extensive list of platform metrics available such as temperature, network, cpu, memory  etc.. Collectd allows you additional customization by loading [plugins](https://collectd.org/wiki/index.php/Table_of_Plugins) as needed.

> NOTE: intel-rapl is used to monitor power usage and will not work on VMs, in this case I have 3 baremetal nodes. On a VMs based cluster `intel-rapl` (Running Average Power Limit) will return the following error on the collectd container: [2022-08-02 15:39:18] [error] Unhandled python exception in loading module: OSError: [Errno 2] No such file or directory: '/sys/devices/virtual/powercap/intel-rapl/intel-rapl:0/max_energy_range_uj' Could not read power consumption wraparound value

Other than this specific use case related to power usage you can use the TAS on a VMs based cluster with any other metric.

## Summary

Below the high-level steps to run Intel-TAS on OpenShift

1. Clone this repository
2. Activate UWM (User Workload Monitoring) in OpenShift.
   - Creates a Thanos instance for user metrics 
3. Install collectd helm chart to monitor power and other platform metrics.
   - Deploy SCC (SecurityContextConstraints)
   - Create `telemetry` namespace and label it
   - `Daemonset` and `ServiceMonitor`, RBAC for prometheus to scrape on the `telemetry` namespace
4. Deploy Custom Metrics Proxy.
   - Important to set correctly the PROMETHEUS variables in deployment.yaml
5. Deploy Intel-TAS using the helm charts
6. Deploy Secondary Scheduler Operator
   - Check the OpenShift version for correct procedure
7. Deploy Descheduler Operator
8. Run the demo

## Getting Started

Clone this repository.

```
# git clone https://github.com/tele0x/openshift-intel-tas.git
# cd openshift-intel-tas
```

## Telemetry

Steps and components required to provide telemetry information to the TAS.

### Activate User Workload Monitoring

Enable monitoring for user-defined projects in addition to the default platform monitoring provided by OpenShift. This feature allows to use the monitoring stack from OpenShift for your workload/applications.

Apply enable_user_workload.yaml. The namespace `openshift-user-workload-monitoring` will be automatically created.

```
# oc apply -f telemetry/user_workload_monitoring/user_workload_enable.yaml
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-monitoring-config
  namespace: openshift-monitoring
data:
  config.yaml: |
    enableUserWorkload: true
```

Check `prometheus-user-workload` pods are created under `openshift-user-workload-monitoring` namespace.

```
# oc get pods -n openshift-user-workload-monitoring
NAME                                  READY   STATUS    RESTARTS   AGE
prometheus-operator-594b5c8b9-2sj4d   2/2     Running   0          38d
prometheus-user-workload-0            5/5     Running   1          38d
prometheus-user-workload-1            5/5     Running   1          38d
thanos-ruler-user-workload-0          3/3     Running   0          38d
thanos-ruler-user-workload-1          3/3     Running   0          38d
```

Create an empty config:

```
# oc apply -f telemetry/user_workload_monitoring/user_workload_config.yaml
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: user-workload-monitoring-config
  namespace: openshift-user-workload-monitoring
data:
  config.yaml: |
```

Verify configuration is loaded successfully:

```
# oc logs prometheus-user-workload-0 -n openshift-user-workload-monitoring | grep config
level=info ts=2022-06-12T21:16:51.704Z caller=main.go:975 msg="Completed loading of configuration file" filename=/etc/prometheus/config_out/prometheus.env.yaml totalDuration=19.732179ms remote_storage=3.67µs web_handler=1.03µs query_engine=1.574µs scrape=3.926427ms scrape_sd=6.437638ms notify=269.528µs notify_sd=3.159647ms rules=71.163µs
```

### Deploy Collectd

Create `telemetry` namespace and add label required by user-workload-monitoring.

```
# oc create ns telemetry
# oc label namespace telemetry openshift.io/cluster-monitoring=true
```

Apply `SecurityContextConstraints`,  required because collectd requires privileged access.

```
# oc create -f telemetry/collectd/collectd_scc.yaml
```

Install helm chart

```
# cd telemetry/collectd/chart/
# helm install telemetry -n telemetry .

NAME: telemetry
LAST DEPLOYED: Wed Jul 20 13:26:20 2022
NAMESPACE: telemetry
STATUS: deployed
REVISION: 1
TEST SUITE: None
NOTES:
Installing collectd.

The release is named telemetry.

To use the helm release:

  $ helm status telemetry
  $ helm get all telemetry
```

Verify pods are running:

```
# oc get pods -n telemetry
NAME             READY   STATUS    RESTARTS   AGE
collectd-bqcgd   2/2     Running   0          35s
collectd-q5m74   2/2     Running   0          35s
collectd-xzhtt   2/2     Running   0          35s

# oc logs -f collectd-bqcgd -c collectd -n telemetry
[2022-06-12 22:31:47] plugin_load: plugin "logfile" successfully loaded.
[2022-06-12 22:31:47] logfile: invalid loglevel [debug] defaulting to 'info'
[2022-06-12 22:31:47] [info] plugin_load: plugin "cpu" successfully loaded.
[2022-06-12 22:31:47] [info] plugin_load: plugin "interface" successfully loaded.
[2022-06-12 22:31:47] [info] plugin_load: plugin "load" successfully loaded.
[2022-06-12 22:31:47] [info] plugin_load: plugin "memory" successfully loaded.
[2022-06-12 22:31:47] [info] plugin_load: plugin "syslog" successfully loaded.
[2022-06-12 22:31:47] [info] plugin_load: plugin "network" successfully loaded.
[2022-06-12 22:31:47] [info] plugin_load: plugin "write_prometheus" successfully loaded.
[2022-06-12 22:31:47] [info] plugin_load: plugin "hugepages" successfully loaded.
[2022-06-12 22:31:47] [info] plugin_load: plugin "intel_pmu" successfully loaded.
[2022-06-12 22:31:47] [info] plugin_load: plugin "ipmi" successfully loaded.
[2022-06-12 22:31:47] [info] plugin_load: plugin "python" successfully loaded.
[2022-06-12 22:31:47] [info] write_prometheus plugin: Listening on [::]:9103.
....
....
```

Collectd runs as a daemonset, we now have an instance running on each node. Verify metrics are available on the node exporter.

```
# oc get nodes
NAME                         STATUS   ROLES           AGE    VERSION
node7.ocp4rony.dfw.ocp.run   Ready    master,worker   257d   v1.21.1+a620f50
node8.ocp4rony.dfw.ocp.run   Ready    master,worker   257d   v1.21.1+a620f50
node9.ocp4rony.dfw.ocp.run   Ready    master,worker   257d   v1.21.1+a620f50

# curl http://node7.ocp4rony.dfw.ocp.run:9103
# TYPE collectd_memory gauge
collectd_memory{memory="buffered",instance="node7.ocp4rony.dfw.ocp.run"} 1308160000 1658342947277
collectd_memory{memory="cached",instance="node7.ocp4rony.dfw.ocp.run"} 21941870592 1658342947277
collectd_memory{memory="free",instance="node7.ocp4rony.dfw.ocp.run"} 1341911040 1658342947277
collectd_memory{memory="slab_recl",instance="node7.ocp4rony.dfw.ocp.run"} 3035107328 1658342947277
collectd_memory{memory="slab_unrecl",instance="node7.ocp4rony.dfw.ocp.run"} 7315562496 1658342947277
collectd_memory{memory="used",instance="node7.ocp4rony.dfw.ocp.run"} 100132577280 1658342947277
# HELP collectd_package_0_TDP_power_power write_prometheus plugin: 'package_0_TDP_power' Type: 'power', Dstype: 'gauge', Dsname: 'value'
# TYPE collectd_package_0_TDP_power_power gauge
collectd_package_0_TDP_power_power{instance="node7.ocp4rony.dfw.ocp.run"} 90 1658342927385
# HELP collectd_package_0_power_power write_prometheus plugin: 'package_0_power' Type: 'power', Dstype: 'gauge', Dsname: 'value'
# TYPE collectd_package_0_power_power gauge
collectd_package_0_power_power{instance="node7.ocp4rony.dfw.ocp.run"} 29.383655389566 1658342927385
# HELP collectd_package_1_TDP_power_power write_prometheus plugin: 'package_1_TDP_power' Type: 'power', Dstype: 'gauge', Dsname: 'value'
# TYPE collectd_package_1_TDP_power_power gauge
collectd_package_1_TDP_power_power{instance="node7.ocp4rony.dfw.ocp.run"} 90 1658342927386
# HELP collectd_package_1_power_power write_prometheus plugin: 'package_1_power' Type: 'power', Dstype: 'gauge', Dsname: 'value'
# TYPE collectd_package_1_power_power gauge
collectd_package_1_power_power{instance="node7.ocp4rony.dfw.ocp.run"} 24.6633647807335 1658342927386
```

Check `ServiceMonitor` is running. The `ServiceMonitor` creates a new job on prometheus configuration to scrape the data from the exporter

```
# oc get servicemonitor -n telemetry
NAME                        AGE
telemetry-service-monitor   37d
```

Check scraping job is added to the prometheus configuration

```
# oc -n openshift-monitoring get secret prometheus-k8s -ojson | jq -r '.data["prometheus.yaml.gz"]' | base64 -d | gunzip | grep "telemetry"
- job_name: serviceMonitor/telemetry/telemetry-service-monitor/0
      - telemetry
```

Verify Thanos endpoint is now available:
Set variables to access Thanos.

```
SECRET=`oc get secret -n openshift-user-workload-monitoring | grep  prometheus-user-workload-token | head -n 1 | awk '{print $1 }'`
TOKEN=`echo $(oc get secret $SECRET -n openshift-user-workload-monitoring -o json | jq -r '.data.token') | base64 -d`
THANOS_QUERIER_HOST=`oc get route thanos-querier -n openshift-monitoring -o json | jq -r '.spec.host'`
```

Let's try to pull a metric and see if it exists:

```
# curl -X GET -kG "https://$THANOS_QUERIER_HOST/api/v1/query?" --data-urlencode "query=collectd_package_0_power_power" -H "Authorization: Bearer $TOKEN" | jq .
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  1193  100  1193    0     0  25382      0 --:--:-- --:--:-- --:--:-- 25382
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {
          "__name__": "collectd_package_0_power_power",
          "container": "collectd",
          "endpoint": "http-collectd",
          "exported_instance": "node7.ocp4rony.dfw.ocp.run",
          "instance": "192.168.116.107:9103",
          "job": "telemetry-service",
          "namespace": "telemetry",
          "pod": "collectd-bqcgd",
          "prometheus": "openshift-monitoring/k8s",
          "service": "telemetry-service"
        },
        "value": [
          1658449342.953,
          "29.8462762011455"
        ]
      },
      {
        "metric": {
          "__name__": "collectd_package_0_power_power",
          "container": "collectd",
          "endpoint": "http-collectd",
          "exported_instance": "node8.ocp4rony.dfw.ocp.run",
          "instance": "192.168.116.108:9103",
          "job": "telemetry-service",
          "namespace": "telemetry",
          "pod": "collectd-xzhtt",
          "prometheus": "openshift-monitoring/k8s",
          "service": "telemetry-service"
        },
        "value": [
          1658449342.953,
          "24.031256867744"
        ]
      },
      {
        "metric": {
          "__name__": "collectd_package_0_power_power",
          "container": "collectd",
          "endpoint": "http-collectd",
          "exported_instance": "node9.ocp4rony.dfw.ocp.run",
          "instance": "192.168.116.109:9103",
          "job": "telemetry-service",
          "namespace": "telemetry",
          "pod": "collectd-q5m74",
          "prometheus": "openshift-monitoring/k8s",
          "service": "telemetry-service"
        },
        "value": [
          1658449342.953,
          "22.8329267201268"
        ]
      }
    ]
  }
}
```

In addition you can check on OpenShift Web Console. Under *Monitoring* -> *Metrics* enter in the expression text area collectd_package_0_power_power and press the "Run Queries" button

![Collectd Metric](img/collectd_metric.png)


## Deploy Metrics Proxy

The metrics-proxy is a component responsible of translating Prometheus queries results into Kubernetes Node Metric. Similar to prometheus-adapter but specific to be used with the TAS.

```
# cd telemetry/metrics_proxy
```

edit `deploy/deployment.yaml` and change the variables for PROMETHEUS_HOST and PROMETHEUS_TOKEN, you can either query directly prometheus or go through Thanos. In this case will just go through Thanos, PROMETHEUS_HOST and PROMETHEUS_TOKEN has to match with the previous variables values for THANOS_QUERIER_HOST and TOKEN.

TODO: Instead of using env variables, use a better method such as secrets.

We can now deploy the metrics-proxy:

```
# oc create -f deploy/
```

Verify metrics-proxy is running:

```
# oc get pods -n openshift-monitoring
NAME                                          READY   STATUS    RESTARTS   AGE
alertmanager-main-0                           5/5     Running   0          160d
alertmanager-main-1                           5/5     Running   0          160d
alertmanager-main-2                           5/5     Running   0          160d
cluster-monitoring-operator-8fc4d666d-l85t7   2/2     Running   0          36d
grafana-54884779f5-82blq                      2/2     Running   0          160d
kube-state-metrics-546c4bdcb9-gx682           3/3     Running   0          160d
metrics-proxy-f95bc9dd7-6jxp7                 1/1     Running   0          2d19h
node-exporter-4jsw8                           2/2     Running   2          259d
node-exporter-kb474                           2/2     Running   2          259d
node-exporter-lsdqg                           2/2     Running   4          259d
openshift-state-metrics-6f75bbb5dc-xz955      3/3     Running   0          160d
prometheus-adapter-79f99745ff-6kp99           1/1     Running   0          2d14h
prometheus-adapter-79f99745ff-krpqd           1/1     Running   0          2d14h
prometheus-k8s-0                              7/7     Running   1          38d
prometheus-k8s-1                              7/7     Running   1          38d
prometheus-operator-64d6cfbdd-k6tk9           2/2     Running   0          160d
telemeter-client-c8d9f487-jdj95               3/3     Running   0          160d
thanos-querier-6957dbc8d4-jh4gh               5/5     Running   0          78d
thanos-querier-6957dbc8d4-jt7wj               5/5     Running   0          3d21h
```

Verify custom metrics APIService is active:

```
# oc get apiservice | grep custom
v1beta1.custom.metrics.k8s.io                 openshift-monitoring/metrics-proxy                           True        36d
v1beta2.custom.metrics.k8s.io                 openshift-monitoring/metrics-proxy                           True        36d
```

Status of "True" means the API is now available, we can test it with this request:

```
# oc get --raw "/apis/custom.metrics.k8s.io/v1beta1/nodes/*/collectd_package_0_power_power" | jq 
{
  "kind": "MetricValueList",
  "apiVersion": "custom.metrics.k8s.io/v1beta1",
  "metadata": {
    "selfLink": "/apis/custom.metrics.k8s.io/v1beta1/nodes/%2A/collectd_package_0_power_power"
  },
  "items": [
    {
      "describedObject": {
        "kind": "Node",
        "name": "node7.ocp4rony.dfw.ocp.run",
        "apiVersion": "/v1"
      },
      "metricName": "collectd_package_0_power_power",
      "timestamp": "2022-07-22T18:19:10Z",
      "value": "29.9018074700547",
      "selector": null
    },
    {
      "describedObject": {
        "kind": "Node",
        "name": "node8.ocp4rony.dfw.ocp.run",
        "apiVersion": "/v1"
      },
      "metricName": "collectd_package_0_power_power",
      "timestamp": "2022-07-22T18:19:10Z",
      "value": "23.79567450213",
      "selector": null
    },
    {
      "describedObject": {
        "kind": "Node",
        "name": "node9.ocp4rony.dfw.ocp.run",
        "apiVersion": "/v1"
      },
      "metricName": "collectd_package_0_power_power",
      "timestamp": "2022-07-22T18:19:10Z",
      "value": "18.820718536048",
      "selector": null
    }
  ]
}
```

Logs from metrics-proxy:

```
# oc logs -f -l app=metrics-proxy -n openshift-monitoring
Retrieve metric: collectd_package_0_power_power
GET URL: https://prometheus-k8s-openshift-monitoring.apps.ocp4rony.dfw.ocp.run/api/v1/query?query=collectd_package_0_power_power
<Response [200]>
Parse data:
{'status': 'success', 'data': {'resultType': 'vector', 'result': [{'metric': {'__name__': 'collectd_package_0_power_power', 'container': 'collectd', 'endpoint': 'http-collectd', 'exported_instance': 'node7.ocp4rony.dfw.ocp.run', 'instance': '192.168.116.107:9103', 'job': 'telemetry-service', 'namespace': 'telemetry', 'pod': 'collectd-bqcgd', 'service': 'telemetry-service'}, 'value': [1659674361.189, '32.0116113817915']}, {'metric': {'__name__': 'collectd_package_0_power_power', 'container': 'collectd', 'endpoint': 'http-collectd', 'exported_instance': 'node8.ocp4rony.dfw.ocp.run', 'instance': '192.168.116.108:9103', 'job': 'telemetry-service', 'namespace': 'telemetry', 'pod': 'collectd-xzhtt', 'service': 'telemetry-service'}, 'value': [1659674361.189, '23.2479306776859']}, {'metric': {'__name__': 'collectd_package_0_power_power', 'container': 'collectd', 'endpoint': 'http-collectd', 'exported_instance': 'node9.ocp4rony.dfw.ocp.run', 'instance': '192.168.116.109:9103', 'job': 'telemetry-service', 'namespace': 'telemetry', 'pod': 'collectd-q5m74', 'service': 'telemetry-service'}, 'value': [1659674361.189, '19.8481904884772']}]}}
status is success
Nodes data: 
[{'describedObject': {'kind': 'Node', 'name': 'node7.ocp4rony.dfw.ocp.run', 'apiVersion': '/v1'}, 'metricName': 'collectd_package_0_power_power', 'timestamp': '2022-08-05T04:39:21Z', 'value': '32.0116113817915', 'selector': None}, {'describedObject': {'kind': 'Node', 'name': 'node8.ocp4rony.dfw.ocp.run', 'apiVersion': '/v1'}, 'metricName': 'collectd_package_0_power_power', 'timestamp': '2022-08-05T04:39:21Z', 'value': '23.2479306776859', 'selector': None}, {'describedObject': {'kind': 'Node', 'name': 'node9.ocp4rony.dfw.ocp.run', 'apiVersion': '/v1'}, 'metricName': 'collectd_package_0_power_power', 'timestamp': '2022-08-05T04:39:21Z', 'value': '19.8481904884772', 'selector': None}]
Response: 
{'kind': 'MetricValueList', 'apiVersion': 'custom.metrics.k8s.io/v1beta2', 'metadata': {'selfLink': '/apis/custom.metrics.k8s.io/v1beta2/nodes/%2A/collectd_package_0_power_power'}, 'items': [{'describedObject': {'kind': 'Node', 'name': 'node7.ocp4rony.dfw.ocp.run', 'apiVersion': '/v1'}, 'metricName': 'collectd_package_0_power_power', 'timestamp': '2022-08-05T04:39:21Z', 'value': '32.0116113817915', 'selector': None}, {'describedObject': {'kind': 'Node', 'name': 'node8.ocp4rony.dfw.ocp.run', 'apiVersion': '/v1'}, 'metricName': 'collectd_package_0_power_power', 'timestamp': '2022-08-05T04:39:21Z', 'value': '23.2479306776859', 'selector': None}, {'describedObject': {'kind': 'Node', 'name': 'node9.ocp4rony.dfw.ocp.run', 'apiVersion': '/v1'}, 'metricName': 'collectd_package_0_power_power', 'timestamp': '2022-08-05T04:39:21Z', 'value': '19.8481904884772', 'selector': None}]}
10.129.0.1 - - [05/Aug/2022 04:39:21] "GET /apis/custom.metrics.k8s.io/v1beta2/nodes/%2A/collectd_package_0_power_power HTTP/1.1" 200 -
```

All the telemetry required by the TAS is now in place.

## Scheduling

This section covers the deployment of the scheduling/descheduling components including the TAS.

### Deploy Intel-TAS

Intel-TAS can be deployed in different ways. In this repository you can find the helm charts that are part of Intel Container Experience Kits.
The TAS version used is 0.1. Intel has released version 0.2 but the possibility of running the TAS in "unsafe" mode with just `http` was removed completely. (work is in progress to get TLS between the scheduler and the TAS on OpenShift).

Another options is to follow instruction on the [platform-aware-scheduling repo](https://github.com/intel/platform-aware-scheduling/tree/master/telemetry-aware-scheduling)

In this case will use the helm chart provided by this repository and we will deploy the TAS in the `default` namespace.

```
# cd scheduling/telemetry-aware-scheduling/
# oc create -f crd/tas-policy-crd.yaml
# helm install telemetry-aware-scheduling -n default .
```

Verify TAS is running `oc get pods -n default | grep telemetry-aware`

A simple policy is provided as an example. Reference to the [TAS documentation](https://github.com/intel/platform-aware-scheduling/tree/master/telemetry-aware-scheduling#policy-definition) for additional `TASPolicy` configuration

```
# oc create -f manifests/tas_policy.yaml -n default
```

```yaml
apiVersion: telemetry.intel.com/v1alpha1
kind: TASPolicy
metadata:
  name: power-policy
spec:
  strategies:
    dontschedule:
      rules:
      - metricname: collectd_package_0_power_power
        operator: GreaterThan
        target: 30
```

Verify policy is read correctly and metrics are shown:


```
# oc logs -l "app.kubernetes.io/instance=tas" -n default
I0727 16:44:24.866051       1 enforce.go:157] "Evaluating power-policy" component="controller"
I0727 16:44:24.866145       1 strategy.go:41] "node7.ocp4rony.dfw.ocp.run collectd_package_0_power_power = 29.118254348" component="controller"
I0727 16:44:24.866183       1 strategy.go:41] "node8.ocp4rony.dfw.ocp.run collectd_package_0_power_power = 23.462413467" component="controller"
I0727 16:44:24.866206       1 strategy.go:41] "node9.ocp4rony.dfw.ocp.run collectd_package_0_power_power = 22.214324721" component="controller"
```

TAS is running and evaluating our `power-policy`. We can now delete the policy and move to the next step. We will apply a new policy in our Demo.

```
# oc delete -f manifests/tas_policy.yaml -n default
```


### Deploy Secondary Scheduler Operator

Secondary Scheduler Operator is used to run a standard kubernetes scheduler that will use the deployed TAS as an extender.

#### OpenShift >= 4.10

For OpenShift versions >= 4.10 go to OperatorHub on OpenShift Web Console, search for "Secondary Scheduler Operator" and install it from there. Once installed you can apply the following two manifests:

```
# oc create -f scheduling/secondary_scheduler_operator/06_configmap.yaml
# oc create -f scheduling/secondary_scheduler_operator/07_secondary-scheduler-operator.cr.yaml
```

#### OpenShift < 4.10

For OpenShift version lower than 4.10 you can use my container image or build your own following instructions at [https://github.com/openshift/secondary-scheduler-operator](https://github.com/openshift/secondary-scheduler-operator).
If you build your own container image change `deploy_secondary_scheduler_operator/05_deployment.yaml` and point it to your registry/image otherwise it will use `quay.io/ferossi/secondary-scheduler-operator`.
We can now deploy the manifests:

```
# oc create -f scheduling/secondary_scheduler_operator/
```

If you get an error on the last file `07_secondary-scheduler-operator.cr.yaml`, that means it didn't have enough time to create the CRD, if that happens just run `oc create -f secondary_scheduler_operator/07_secondary-scheduler-operator.cr.yaml`.

Check namespace `openshift-secondary-scheduler-operator`

```
# oc get pods -n openshift-secondary-scheduler-operator
NAME                                           READY   STATUS    RESTARTS   AGE
secondary-scheduler-5b6f6f55d4-6d6ht           1/1     Running   0          8m2s
secondary-scheduler-operator-d4b6cf5bd-d5kwp   1/1     Running   0          9d
```

### Deploy Descheduler Operator

Descheduler Operator is available for installation on any OpenShift version >= 4.7. It allows control of pod evictions based on defined strategies.
The TAS will evaluate policies and label nodes as violators, the descheduler will evict the pod from the node and re-schedule on available nodes based on the policy rules.

Create namespace:

```
# oc create ns openshift-kube-descheduler-operator
```

Using OpenShift Web Console go under *Operators* -> *OperatorHub*. Search for "descheduler".

![Descheduler Operator Step 1](img/descheduler_step1.png)

Select the created namespace `openshift-kube-descheduler-operator` and press "Install".

![Descheduler Operator Step 2](img/descheduler_step2.png)

View Operator when installation is finished and click create `KubeDescheduler` instance.

![Descheduler Operator Step 3](img/descheduler_step3.png)

Change the default 3600 *Descheduler Interval Seconds*, this is how often the descheduler runs to identify any pod eviction.
Set to 100 seconds in this case and click "Create".

![Descheduler Operator Step 4](img/descheduler_step4.png)

Verify the descheduler named "cluster" is running:

```
# oc get pods -n openshift-kube-descheduler-operator
NAME                                    READY   STATUS    RESTARTS   AGE
cluster-86f55fcd49-z74tj                1/1     Running   0          77s
descheduler-operator-84b6469497-wrlpc   1/1     Running   0          4m10s
```

"cluster" pod now runs the descheduler binary and loads the `DeschedulerPolicy` defined in a configmap mounted on the pod:
Just for reference this is where the configmap is mounted.

```
# oc exec -ti cluster-86f55fcd49-z74tj -n openshift-kube-descheduler-operator /bin/bash
kubectl exec [POD] [COMMAND] is DEPRECATED and will be removed in a future version. Use kubectl exec [POD] -- [COMMAND] instead.
bash-4.4$ ls
bin  boot  certs-dir  dev  etc	home  lib  lib64  lost+found  media  mnt  opt  policy-dir  proc  root  run  sbin  srv  sys  tmp  usr  var
bash-4.4$ cd policy-dir/
bash-4.4$ ls
policy.yaml
```

The configmap is the following:

```
# oc get configmap cluster -n openshift-kube-descheduler-operator -o yaml
```

The default `DeschedulerPolicy` will cover our TAS requirements to deschedule in case of any node affinity.


## Demo 1

Deploy a Pod to test if our deployment works:
Apply the tasdemo_pod.yaml

```
# oc create -f manifests/tasdemo_pod.yaml
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: tasdemo
  namespace: default
  labels:
    app: demo
    telemetry-policy: power-policy
spec:
  containers:
    - name: tasdemo
      image: nginx:1.14.2
      ports:
        - containerPort: 80
      resources:
        limits:
          telemetry/scheduling: 1
  schedulerName: secondary-scheduler
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: power-policy
                operator: NotIn
                values:
                  - violating
```

In order to use our custom scheduler we must define `schedulerName` on the manifest. the name scheduler name was defined in `scheduling/secondary_scheduler_operator/06_configmap.yaml` under `KubeSchedulerConfiguration` object.
To make sure the schedulerName is correct:

```
# oc get secondaryscheduler -n openshift-secondary-scheduler-operator -o yaml
```

Now apply pod manifest:

``` 
# oc create -f pod.yaml
```

Check Scheduler logs:

```
# oc logs -f -l app=secondary-scheduler -n openshift-secondary-scheduler-operator
I0729 14:48:01.029696       1 scheduling_queue.go:869] "About to try and schedule pod" pod="default/tasdemo"
I0729 14:48:01.029748       1 scheduler.go:459] "Attempting to schedule pod" pod="default/tasdemo"
I0729 14:48:01.130520       1 trace.go:205] Trace[907429387]: "Scheduling" namespace:default,name:tasdemo (29-Jul-2022 14:48:01.029) (total time: 100ms):
Trace[907429387]: ---"Snapshotting scheduler cache and node infos done" 0ms (14:48:00.029)
Trace[907429387]: ---"Computing predicates done" 100ms (14:48:00.130)
Trace[907429387]: [100.683772ms] [100.683772ms] END
I0729 14:48:01.130912       1 default_binder.go:51] "Attempting to bind pod to node" pod="default/tasdemo" node="node7.ocp4rony.dfw.ocp.run"
I0729 14:48:01.140091       1 scheduler.go:604] "Successfully bound pod to node" pod="default/tasdemo" node="node7.ocp4rony.dfw.ocp.run" evaluatedNodes=3 feasibleNodes=1
I0729 14:48:01.216217       1 eventhandlers.go:201] "Delete event for unscheduled pod" pod="default/tasdemo"
I0729 14:48:01.216294       1 eventhandlers.go:221] "Add event for scheduled pod" pod="default/tasdemo"
```

As you can see the scheduler attempted to schedule our `tasdemo` pod, since we have an extender configuration it sends first a filter request to the TAS asking which node is available for scheduling.
Check TAS logs:

```
I0729 14:48:01.125362       1 telemetryscheduler.go:164] "Filter request received" component="extender"
I0729 14:48:01.128381       1 strategy.go:35] "node7.ocp4rony.dfw.ocp.run collectd_package_0_power_power = 32.592849848" component="controller"
I0729 14:48:01.128424       1 strategy.go:35] "node8.ocp4rony.dfw.ocp.run collectd_package_0_power_power = 23.418708438" component="controller"
I0729 14:48:01.128452       1 strategy.go:38] "node8.ocp4rony.dfw.ocp.run violating : collectd_package_0_power_power LessThan 30" component="controller"
I0729 14:48:01.128473       1 strategy.go:35] "node9.ocp4rony.dfw.ocp.run collectd_package_0_power_power = 20.168518989" component="controller"
I0729 14:48:01.128493       1 strategy.go:38] "node9.ocp4rony.dfw.ocp.run violating : collectd_package_0_power_power LessThan 30" component="controller"
I0729 14:48:01.128521       1 telemetryscheduler.go:222] "Filtered nodes for scheduling-policy: node7.ocp4rony.dfw.ocp.run " component="extender"
I0729 14:48:02.853721       1 enforce.go:241] "Evaluating scheduling-policy" component="controller"
```

The TAS received the request and evaluated the policy defined in the pod. node7 was selected because the power usage is greater than 30. 

```
# oc get pods -n default -o wide | grep tasdemo
tasdemo                                           1/1     Running   0          3d11h   10.129.1.163   node7.ocp4rony.dfw.ocp.run   <none>           <none>
```

Success!

## Challenges

I experienced several challenges trying to run the Intel-TAS on OpenShift. In the [Challenges](CHALLENGES.md) document you can read detailed explanation about the failed approaches, design choices and how I got it to work on OpenShift.
