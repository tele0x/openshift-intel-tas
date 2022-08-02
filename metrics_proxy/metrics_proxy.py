# ========================================================================================
# OCP Metrics Proxy for Intel-TAS (Telemetry-Aware Scheduling) 
# Transform prometheus query output to a Kubernetes Node Metric consumable by the Intel-TAS
#
# Author: Federico 'tele' Rossi <ferossi@redhat.com>

from flask import Flask, request, jsonify, g, url_for, redirect, Response
from werkzeug.routing import BaseConverter
from datetime import datetime
import json, os
import requests

app = Flask(__name__)

PROMETHEUS_HOST = os.environ.get('PROMETHEUS_HOST')
PROMETHEUS_TOKEN = os.environ.get('PROMETHEUS_TOKEN')

# add regex support on route matching
class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]
app.url_map.converters['regex'] = RegexConverter

# discovery check for apiservice
@app.route('/apis/<regex("(custom|external)"):api_type>.metrics.k8s.io/<api_version>')
def discovery(api_type, api_version):
    return {"kind":"APIResourceList","apiVersion":"v1","groupVersion":"metrics.k8s.io/%s" % api_version,"resources":[{"name":"nodes","singularName":"","namespaced":False,"kind":"NodeMetrics","verbs":["get","list"]},{"name":"pods","singularName":"","namespaced":True,"kind":"PodMetrics","verbs":["get","list"]}]}

# endpoint called by the TAS
@app.route('/apis/<regex("(custom|external)"):api_type>.metrics.k8s.io/<api_version>/nodes/*/<metric>')
def metric(api_type, api_version, metric):
    print('Retrieve metric: %s' % metric)
    
    header = {'Authorization': 'Bearer %s' % PROMETHEUS_TOKEN}
    
    try:
        url = 'https://%s/api/v1/query?query=%s' % (PROMETHEUS_HOST, metric)
        print('GET URL: %s' % url)
        client = requests.get(url, headers=header, verify=False)
        print(client)
    except requests.exceptions.RequestException as e:
        print('Unable to connect to %s: %s' % (PROMETHEUS_HOST, str(e)))
        return {'status': 'error', 'msg': 'Unable to connect to %s: %s' % (PROMETHEUS_HOST, str(e))}

    nodes = []
    if client.status_code == 200:
        print('Parse data:')
        data = json.loads(client.text)
        print(data)
        if 'status' in data.keys():
            if data['status'] == 'success':
                print('status is success')
                for node in data['data']['result']:
                    node_obj = {
                                 "describedObject": {
                                   "kind": "Node",
                                   "name": node['metric']['exported_instance'],
                                   "apiVersion": "/v1"
                                 },
                                 "metricName": metric,
                                 "timestamp": datetime.fromtimestamp(node['value'][0]).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 "value": str(node['value'][1]),
                                 "selector": None
                               }
                                 
                    nodes.append(node_obj)
       
        print('Nodes data: ')
        print(nodes)
    
    metric_value_list = {
                          "kind": "MetricValueList",
                          "apiVersion": "custom.metrics.k8s.io/%s" % api_version,
                          "metadata": {
                              "selfLink": "/apis/%s.metrics.k8s.io/%s/nodes/%%2A/%s" % (api_type, api_version, metric)
                          }, "items": nodes 
                        }

    print('Response: ')
    print(metric_value_list)
    return json.dumps(metric_value_list)


if __name__ == "__main__":
    context = ('/var/run/tls/tls.crt', '/var/run/tls/tls.key')
    app.run(host='0.0.0.0', ssl_context=context)
