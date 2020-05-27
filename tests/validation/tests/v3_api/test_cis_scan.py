import pytest
import requests
import time
import os
from rancher import ApiError
from lib.aws import AmazonWebServices
from .common import CLUSTER_MEMBER, run_command
from .common import CLUSTER_OWNER
from .common import CIS_SCAN_PROFILE
from .common import create_kubeconfig
from .common import cluster_cleanup
from .common import execute_kubectl_cmd
from .common import get_user_client
from .common import get_user_client_and_cluster
from .common import get_custom_host_registration_cmd
from .common import get_project_client_for_token
from .common import get_client_for_token
from .common import get_cluster_by_name
from .common import if_test_rbac
from .common import PROJECT_OWNER
from .common import PROJECT_MEMBER
from .common import PROJECT_READ_ONLY
from .common import random_test_name
from .common import rbac_get_user_token_by_role
from .common import USER_TOKEN
from .common import validate_cluster_state
from .common import wait_for_cluster_node_count
from .test_rke_cluster_provisioning import HOST_NAME, \
    POD_SECURITY_POLICY_TEMPLATE, get_cis_rke_config  # NOQA
DATA_SUBDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                           'resource')

scan_results = {
    "rke-cis-1.4": {
        "permissive": {"pass": 63, "skip": 15},
        "hardened": {"pass": 78, "skip": 0},
        "not_applicable": 19, "total": 97, "fail": 0
    },
    "rke-cis-1.5": {
        "permissive": {"pass": 58, "fail": 0, "skip": 14},
        "hardened": {"pass": 72, "fail": 0, "skip": 0},
        "not_applicable": 20, "total": 92, "fail": 0
    }
}
DEFAULT_TIMEOUT = 120
cluster_detail = {
    "cluster": None, "nodes": None, "name": None
}


def test_cis_scan_run_scan():
    cluster = cluster_detail["cluster"]
    scan_detail = run_scan(cluster, USER_TOKEN, "hardened")
    report_link = scan_detail["links"]["report"]
    verify_cis_scan_report(
        report_link, token=USER_TOKEN,
        test_total=scan_results[CIS_SCAN_PROFILE]["total"],
        tests_passed=scan_results[CIS_SCAN_PROFILE]["hardened"]["pass"],
        tests_skipped=0
    )


def test_cis_scan_skip_test_ui():
    client = get_user_client()
    cluster = cluster_detail["cluster"]
    # run security scan
    scan_detail = run_scan(cluster, USER_TOKEN, "hardened")
    report_link = scan_detail["links"]["report"]
    verify_cis_scan_report(
        report_link, token=USER_TOKEN,
        test_total=scan_results[CIS_SCAN_PROFILE]["total"],
        tests_passed=scan_results[CIS_SCAN_PROFILE]["hardened"]["pass"],
        tests_skipped=scan_results[CIS_SCAN_PROFILE]["hardened"]["skip"]
    )

    # get system project
    system_project = cluster.projects(name="System")["data"][0]
    system_project_id = system_project["id"]
    print(system_project)
    p_client = get_project_client_for_token(system_project, USER_TOKEN)

    # check config map is NOT generated for first scan
    try:
        p_client.list_configMap(projectId=system_project_id,
                                namespaceId="security-scan")
    except ApiError as e:
        assert e.error.status == 404, "Config Map is generated for first scan"

    # delete security-scan-cf config if present
    security_scan_config = \
        p_client.list_configMap(projectId=system_project_id,
                                namespaceId="security-scan",
                                id="security-scan:security-scan-cfg",
                                name="security-scan-cfg")
    print(security_scan_config)
    if len(security_scan_config["data"]) != 0:
        p_client.delete(security_scan_config["data"][0])
    # skip action as on UI
    cm_data = {"config.json": "{\"skip\":{\"rke-cis-1.4\":[\"1.1.2\"]}}"}
    p_client.create_configMap(projectId=system_project_id,
                              name="security-scan-cfg",
                              namespaceId="security-scan",
                              id="security-scan:security-scan-cfg",
                              data=cm_data)
    # run security scan
    scan_detail_2 = run_scan(cluster, USER_TOKEN, "hardened")
    client.reload(scan_detail_2)
    report_link = scan_detail_2["links"]["report"]
    report = verify_cis_scan_report(
        report_link,
        token=USER_TOKEN,
        test_total=scan_results[CIS_SCAN_PROFILE]["total"],
        tests_passed=scan_results[CIS_SCAN_PROFILE]["hardened"]["pass"] - 1,
        tests_skipped=scan_results[CIS_SCAN_PROFILE]["hardened"]["skip"] + 1
    )
    print(report["results"][0]["checks"][0]["state"])
    assert report["results"][0]["checks"][0]["state"] == "skip", \
        "State of the test is not as expected"

    """As part of clean up
    delete security-scan-cf config
    """
    security_scan_config = \
        p_client.list_configMap(projectId=system_project_id,
                                namespaceId="security-scan",
                                id="security-scan:security-scan-cfg",
                                name="security-scan-cfg")
    print(security_scan_config)
    if len(security_scan_config["data"]) != 0:
        p_client.delete(security_scan_config["data"][0])


def test_cis_scan_skip_test_api():
    client = get_user_client()
    cluster = cluster_detail["cluster"]
    # run security scan
    scan_detail = run_scan(cluster, USER_TOKEN, "hardened")
    report_link = scan_detail["links"]["report"]
    verify_cis_scan_report(
        report_link, token=USER_TOKEN,
        test_total=scan_results[CIS_SCAN_PROFILE]["total"],
        tests_passed=scan_results[CIS_SCAN_PROFILE]["hardened"]["pass"],
        tests_skipped=scan_results[CIS_SCAN_PROFILE]["hardened"]["skip"]
    )

    # skip test 1.1.3
    cluster.runSecurityScan(overrideSkip=["1.1.3"],
                            profile="hardened",
                            overrideBenchmarkVersion="rke-cis-1.4")
    cluster = client.reload(cluster)
    cluster_scan_report_id = cluster["currentCisRunName"]
    print(cluster_scan_report_id)
    scan_detail = wait_for_scan_active(cluster_scan_report_id, client)
    wait_for_cis_pod_remove(cluster, cluster_scan_report_id)
    report_link = scan_detail["links"]["report"]
    report = verify_cis_scan_report(
        report_link,
        token=USER_TOKEN,
        test_total=scan_results[CIS_SCAN_PROFILE]["total"],
        tests_passed=scan_results[CIS_SCAN_PROFILE]["hardened"]["pass"] - 1,
        tests_skipped=scan_results[CIS_SCAN_PROFILE]["hardened"]["skip"] + 1
    )
    assert report["results"][0]["checks"][1]["state"] == "skip", \
        "State of the test is not as expected"


def test_cis_scan_edit_cluster():
    aws_nodes = cluster_detail["nodes"]
    client = get_user_client()
    cluster = cluster_detail["cluster"]
    # Add 2 etcd nodes to the cluster
    for i in range(0, 2):
        aws_node = aws_nodes[3 + i]
        aws_node.execute_command("sudo sysctl -w vm.overcommit_memory=1")
        aws_node.execute_command("sudo sysctl -w kernel.panic=10")
        aws_node.execute_command("sudo sysctl -w kernel.panic_on_oops=1")
        docker_run_cmd = get_custom_host_registration_cmd(client,
                                                          cluster,
                                                          ["etcd"],
                                                          aws_node)
        aws_node.execute_command(docker_run_cmd)
    wait_for_cluster_node_count(client, cluster, 5)
    validate_cluster_state(client, cluster, intermediate_state="updating")
    cluster = client.reload(cluster)

    # run CIS Scan
    scan_detail = run_scan(cluster, USER_TOKEN, "hardened")
    report_link = scan_detail["links"]["report"]
    report = verify_cis_scan_report(
        report_link,
        token=USER_TOKEN,
        test_total=scan_results[CIS_SCAN_PROFILE]["total"],
        tests_passed=scan_results[CIS_SCAN_PROFILE]["hardened"]["pass"] - 2,
        tests_skipped=scan_results[CIS_SCAN_PROFILE]["hardened"]["skip"],
        tests_failed=scan_results[CIS_SCAN_PROFILE]["fail"] + 2
    )
    print(report["results"][3]["checks"][18])
    assert report["results"][3]["checks"][18]["state"] == "mixed"

    # edit nodes and run command
    for i in range(0, 2):
        aws_node = aws_nodes[3 + i]
        aws_node.execute_command("sudo useradd etcd")

    # run CIS Scan
    scan_detail = run_scan(cluster, USER_TOKEN, "hardened")
    report_link = scan_detail["links"]["report"]
    report = verify_cis_scan_report(
        report_link,
        token=USER_TOKEN,
        test_total=scan_results[CIS_SCAN_PROFILE]["total"],
        tests_passed=scan_results[CIS_SCAN_PROFILE]["hardened"]["pass"],
        tests_skipped=scan_results[CIS_SCAN_PROFILE]["hardened"]["skip"]
    )
    print(report["results"][3]["checks"][18]["state"])
    assert report["results"][3]["checks"][18]["state"] == "pass"


@if_test_rbac
def test_rbac_run_scan_cluster_owner():
    client, cluster = get_user_client_and_cluster()
    user_token = rbac_get_user_token_by_role(CLUSTER_OWNER)
    # run a permissive scan run
    scan_detail = run_scan(cluster, user_token)
    report_link = scan_detail["links"]["report"]
    verify_cis_scan_report(
        report_link,
        token=USER_TOKEN,
        test_total=scan_results[CIS_SCAN_PROFILE]["total"],
        tests_passed=scan_results[CIS_SCAN_PROFILE]["permissive"]["pass"],
        tests_skipped=scan_results[CIS_SCAN_PROFILE]["permissive"]["skip"]
    )


@if_test_rbac
def test_rbac_run_scan_cluster_member():
    client, cluster = get_user_client_and_cluster()
    user_token = rbac_get_user_token_by_role(CLUSTER_MEMBER)
    run_scan(cluster, user_token, can_run_scan=False)


@if_test_rbac
def test_rbac_run_scan_project_owner():
    client, cluster = get_user_client_and_cluster()
    user_token = rbac_get_user_token_by_role(PROJECT_OWNER)
    run_scan(cluster, user_token, can_run_scan=False)


@if_test_rbac
def test_rbac_run_scan_project_member():
    client, cluster = get_user_client_and_cluster()
    user_token = rbac_get_user_token_by_role(PROJECT_MEMBER)
    run_scan(cluster, user_token, can_run_scan=False)


@if_test_rbac
def test_rbac_run_scan_project_read_only():
    client, cluster = get_user_client_and_cluster()
    user_token = rbac_get_user_token_by_role(PROJECT_READ_ONLY)
    run_scan(cluster, user_token, can_run_scan=False)


@pytest.fixture(scope='module', autouse="True")
def create_project_client(request):
    run_command("jq --version")
    assert False
    aws_nodes = \
        AmazonWebServices().create_multiple_nodes(
            3, random_test_name(HOST_NAME))
    cluster_detail["nodes"] = aws_nodes
    node_roles = [
        ["controlplane"], ["etcd"], ["worker"]
    ]
    rke_config_temp = get_cis_rke_config()
    client = get_user_client()
    cluster = client.create_cluster(
        name=random_test_name(),
        driver="rancherKubernetesEngine",
        rancherKubernetesEngineConfig=rke_config_temp,
        defaultPodSecurityPolicyTemplateId=POD_SECURITY_POLICY_TEMPLATE
    )
    assert cluster.state == "provisioning"
    if CIS_SCAN_PROFILE == 'rke-cis-1.4':
        for i in range(0, 3):
            aws_node = aws_nodes[i]
            aws_node.execute_command("sudo sysctl -w vm.overcommit_memory=1")
            aws_node.execute_command("sudo sysctl -w kernel.panic=10")
            aws_node.execute_command("sudo sysctl -w kernel.panic_on_oops=1")
            if node_roles[i] == ["etcd"]:
                aws_node.execute_command("sudo useradd etcd")
            docker_run_cmd = \
                get_custom_host_registration_cmd(client,
                                                 cluster,
                                                 node_roles[i],
                                                 aws_node)
            aws_node.execute_command(docker_run_cmd)
    elif CIS_SCAN_PROFILE == 'rke-cis-1.5':
        for i in range(0, 3):
            aws_node = aws_nodes[i]
            aws_node.execute_command("sudo sysctl -w vm.overcommit_memory=1")
            aws_node.execute_command("sudo sysctl -w kernel.panic=10")
            aws_node.execute_command("sudo sysctl -w vm.panic_on_oom=0")
            aws_node.execute_command("sudo sysctl -w kernel.panic_on_oops=1")
            aws_node.execute_command("sudo sysctl -w "
                                     "kernel.keys.root_maxbytes=25000000")
            if node_roles[i] == ["etcd"]:
                aws_node.execute_command("sudo groupadd -g 52034 etcd")
                aws_node.execute_command("sudo useradd -u 52034 -g 52034 etcd")
            docker_run_cmd = \
                get_custom_host_registration_cmd(client,
                                                 cluster,
                                                 node_roles[i],
                                                 aws_node)
            aws_node.execute_command(docker_run_cmd)
    time.sleep(5)
    cluster = validate_cluster_state(client, cluster)

    # the worklods under System project to get active
    time.sleep(20)
    if CIS_SCAN_PROFILE == 'rke-cis-1.5':
        create_kubeconfig(cluster)
        network_policy_file = DATA_SUBDIR + "/default-allow-all.yaml"
        account_update_file = DATA_SUBDIR + "/account_update.yaml"
        all_ns = execute_kubectl_cmd(
            "get namespaces -A -o json | jq -r '.items[].metadata.name'",
            json_out=False,
            stderr=True
        )
        for ns in all_ns.split():
            execute_kubectl_cmd("apply -f {0} -n {1}".
                                format(network_policy_file, ns))
            execute_kubectl_cmd('patch serviceaccount default'
                                ' -n {0} -p "$(cat {1})"'.
                                format(ns, account_update_file))

    cluster_detail["cluster"] = cluster

    def fin():
        cluster_cleanup(client, cluster, aws_nodes)

    request.addfinalizer(fin)


def verify_cis_scan_report(
        report_link, token, test_total,
        tests_passed, tests_skipped,
        tests_failed=scan_results[CIS_SCAN_PROFILE]["fail"],
        tests_na=scan_results[CIS_SCAN_PROFILE]["not_applicable"]):
    head = {'Authorization': 'Bearer ' + token}
    response = requests.get(report_link, verify=False, headers=head)
    report = response.json()
    assert report["total"] == test_total, \
        "Incorrect number of tests run"
    assert report["pass"] == tests_passed, \
        "Incorrect number of tests passed"
    assert report["fail"] == tests_failed, \
        "Incorrect number of failed tests"
    assert report["skip"] == tests_skipped, \
        "Incorrect number of tests skipped"
    assert report["notApplicable"] == tests_na, \
        "Incorrect number of tests marked Not Applicable"
    return report


def run_scan(cluster, user_token, profile="permissive", can_run_scan=True):
    client = get_client_for_token(user_token)
    cluster = get_cluster_by_name(client, cluster.name)
    if can_run_scan:
        cluster.runSecurityScan(profile=profile,
                                overrideBenchmarkVersion=CIS_SCAN_PROFILE)
        cluster = client.reload(cluster)
        cluster_scan_report_id = cluster["currentCisRunName"]
        print(cluster_scan_report_id)
        scan_detail = wait_for_scan_active(cluster_scan_report_id, client)
        wait_for_cis_pod_remove(cluster, cluster_scan_report_id)
        return scan_detail
    else:
        assert "runSecurityScan" not in list(cluster.actions.keys()), \
            "User has Run CIS Scan permission"


def wait_for_scan_active(cluster_scan_report_id,
                         client,
                         timeout=DEFAULT_TIMEOUT):
    scan_detail_data = client.list_clusterScan(name=cluster_scan_report_id)
    scan_detail = scan_detail_data.data[0]
    # wait until scan is active
    start = time.time()
    state_scan = scan_detail["state"]
    while state_scan != "pass" and state_scan != "fail":
        if time.time() - start > timeout:
            raise AssertionError(
                "Timed out waiting for state of scan report to get to active")
        time.sleep(.5)
        scan_detail_data = client.list_clusterScan(name=cluster_scan_report_id)
        scan_detail = scan_detail_data.data[0]
        state_scan = scan_detail["state"]
        print(state_scan)
    scan_detail_data = client.list_clusterScan(name=cluster_scan_report_id)
    scan_detail = scan_detail_data.data[0]
    return scan_detail


def wait_for_cis_pod_remove(cluster,
                            cluster_scan_report_id,
                            timeout=DEFAULT_TIMEOUT):
    system_project = cluster.projects(name="System")["data"][0]
    p_client = get_project_client_for_token(system_project, USER_TOKEN)
    pod = p_client.list_pod(namespaceId="security-scan",
                            name="security-scan-runner-" +
                                 cluster_scan_report_id)
    start = time.time()
    while len(pod["data"]) != 0:
        if time.time() - start > timeout:
            raise AssertionError(
                "Timed out waiting for removal of security scan pod")
        time.sleep(.5)
        pod = p_client.list_pod(namespaceId="security-scan",
                                name="security-scan-runner-" +
                                     cluster_scan_report_id)
        time.sleep(.5)
