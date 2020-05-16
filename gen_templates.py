#!/usr/bin/env python
from kubernetes import client, config
import os
# TODO: use jsonref
import python_jsonschema_objects as pjs
import yaml

def describe_type(typ):
    desc = {}
    if isinstance(typ, pjs.classbuilder.TypeRef):
        return {'__reference__': typ.__doc__}
    for name, info in typ.__propinfo__.items():
        if info is None:
            continue
        proptype = info['type']
        typename = proptype
        if not isinstance(proptype, str):
            if '$ref' in info:
                typename = os.path.basename(info['$ref'])
            else:
                typename = 'object'
        elif proptype == 'array':
            if '$ref' in info['items']:
                item_typename = os.path.basename(info['items']['$ref'])
                item_type = builder._resolved[builder.resolver.base_uri + info['items']['$ref']]
                item_desc = describe_type(item_type)
                typename = f"array({item_typename})"
            else:
                item_typename = info['items']['type']
                item_desc = item_typename

        if 'description' in info:
            description = f"({typename}) {info['description']}"
        else:
            description = f"{typename}"

        if proptype == 'array':
            desc[name] = [description, item_desc]
        elif '$ref' in info:
                obj_desc = {'_description_': description}
                obj_info = describe_type(proptype)
                obj_desc.update(obj_info)
                desc[name] = obj_desc
        else:
            desc[name] = description
        if 'additionalProperties' in info:
            desc['additionalProperties'] = info['additionalProperties'].copy()
    return desc

config.load_kube_config(config_file="~/.kube/config")
api = client.api_client.ApiClient()
resp = api.call_api('/openapi/v2', 'GET', response_type=object)
spec_dict = resp[0]
defs = spec_dict['definitions']
paths = spec_dict['paths']

props = {}
for path, desc in paths.items():
    if 'post' not in desc:
        continue
    post = desc['post']
    if 'parameters' not in post:
        continue
    body = next(param for param in post['parameters'] if param['name'] == 'body')
    ref = body['schema']['$ref']
    name = os.path.basename(ref)
    props[name] = { '$ref': ref }

schema = {
 '$id': 'https://okasamastarr.com/kubernetes_resources.schema.json',
 '$schema': "http://json-schema.org/draft-07/schema#",
 'title': "Kubernetes resources",
 'type': "object",
 'properties': props,
 'definitions': defs
}

schema['definitions']['io.k8s.apiextensions-apiserver.pkg.apis.apiextensions.v1beta1.JSONSchemaPropsOrArray']['type'] = 'object'
schema['definitions']['io.k8s.apiextensions-apiserver.pkg.apis.apiextensions.v1beta1.JSONSchemaPropsOrBool']['type'] = 'object'
schema['definitions']['io.k8s.apiextensions-apiserver.pkg.apis.apiextensions.v1beta1.JSONSchemaPropsOrStringArray']['type'] = 'object'
schema['definitions']['io.k8s.apiextensions-apiserver.pkg.apis.apiextensions.v1beta1.JSON']['type'] = 'object'
schema['definitions']['io.k8s.apiextensions-apiserver.pkg.apis.apiextensions.v1beta1.JSONSchemaProps']['properties'] = {}

builder = pjs.ObjectBuilder(schema)
ns = builder.build_classes()

descriptions = {}
for name, info in ns.KubernetesResources.__propinfo__.items():
    path = os.path.join('templates', *name.split('.')) + '.yaml'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(yaml.dump(describe_type(info['type'])))
