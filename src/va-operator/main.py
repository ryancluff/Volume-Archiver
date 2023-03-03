import os
import kopf
import kubernetes
import logging
import yaml

debug = True


def change_state(name, namespace, state):
    cobject_api = kubernetes.client.CustomObjectsApi()

    response = cobject_api.patch_namespaced_custom_object(
        group='volumearchiver.rcluff.com',
        version='v1',
        namespace=namespace,
        plural='backupjobs',
        name=name,
        body={
            'status': {
                'state': state
            }
        }
    )


@kopf.on.startup()
async def startup_fn(logger, **kwargs):
    if debug:
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        logger.info("debugpy debugging enabled")


@kopf.on.create('volumearchiver.rcluff.com', 'v1', 'backupjob')
def backupjob_created(spec, name, namespace, logger, **kwargs):
    result = {
        'replicas': {},
    }

    core_api = kubernetes.client.CoreV1Api()
    apps_api = kubernetes.client.AppsV1Api()
    batch_api = kubernetes.client.BatchV1Api()

    pvc_name = spec.get('pvc')

    pvc = core_api.read_namespaced_persistent_volume_claim(
        namespace=namespace,
        name=pvc_name
    )

    if pvc is None:
        raise kopf.PermanentError(f"PVC does not exist")

    if 'ReadWriteOnce' in pvc.spec.access_modes:
        deployments = apps_api.list_namespaced_deployment(namespace=namespace)

        for deployment in deployments.items:
            for volume in deployment.spec.template.spec.volumes:
                if volume.name == pvc_name:
                    result['replicas'][deployment.metadata.name] = deployment.spec.replicas

        replicas_0 = {
            "spec": {
                "replicas": 0
            }
        }

        for deployment in result['replicas']:
            response = apps_api.patch_namespaced_deployment(
                name=deployment,
                namespace=namespace,
                body=replicas_0
            )
            # logger.info(response)

    change_state(name, namespace, "creating job")
    path = os.path.join(os.path.dirname(__file__),
                        'templates', 'backup-config.yml')
    with open(path, 'rt') as file:
        tmpl = file.read()
        manifest = tmpl.format(namespace=namespace, pvc_name=pvc_name)
        data = yaml.safe_load(manifest)
        data['metadata']['annotations']['volumearchiver.rcluff.com/backupjob'] = name

        kopf.adopt(data)
        response = core_api.create_namespaced_config_map(
            namespace=namespace,
            body=data
        )

    path = os.path.join(os.path.dirname(__file__),
                        'templates', 'backup-job.yml')
    with open(path, 'rt') as file:
        tmpl = file.read()
        manifest = tmpl.format(namespace=namespace, pvc_name=pvc_name)
        data = yaml.safe_load(manifest)
        data['metadata']['annotations']['volumearchiver.rcluff.com/backupjob'] = name

        kopf.adopt(data)
        response = batch_api.create_namespaced_job(
            namespace=namespace,
            body=data
        )

    change_state(name, namespace, "backup running")

    return result


@kopf.on.update('batch', 'v1', 'jobs', field='status.succeeded', value=1, annotations={'volumearchiver.rcluff.com/backupjob': kopf.PRESENT})
def job_succeeded(name, namespace, meta, **_):
    apps_api = kubernetes.client.AppsV1Api()
    cobject_api = kubernetes.client.CustomObjectsApi()

    backupjob_name = meta['annotations']['volumearchiver.rcluff.com/backupjob']

    backupjob = cobject_api.get_namespaced_custom_object(
        group='volumearchiver.rcluff.com',
        version='v1',
        namespace=namespace,
        plural='backupjobs',
        name=backupjob_name
    )

    for deployment in backupjob['status']['backupjob_created']['replicas']:
        replicas = backupjob['status']['backupjob_created']['replicas'][deployment]
        response = apps_api.patch_namespaced_deployment(
            name=deployment,
            namespace=namespace,
            body={
                "spec": {
                    "replicas": replicas
                }
            }
        )

    change_state(name, namespace, "complete")

@kopf.on.update('batch', 'v1', 'jobs', field='status.succeeded', value=1, annotations={'volumearchiver.rcluff.com/backupjob': kopf.PRESENT})
def job_succeeded(name, namespace, meta, **_):
    apps_api = kubernetes.client.AppsV1Api()
    cobject_api = kubernetes.client.CustomObjectsApi()

    backupjob_name = meta['annotations']['volumearchiver.rcluff.com/backupjob']

    backupjob = cobject_api.get_namespaced_custom_object(
        group='volumearchiver.rcluff.com',
        version='v1',
        namespace=namespace,
        plural='backupjobs',
        name=backupjob_name
    )

    for deployment in backupjob['status']['backupjob_created']['replicas']:
        replicas = backupjob['status']['backupjob_created']['replicas'][deployment]
        response = apps_api.patch_namespaced_deployment(
            name=deployment,
            namespace=namespace,
            body={
                "spec": {
                    "replicas": replicas
                }
            }
        )

    change_state(name, namespace, "complete")
