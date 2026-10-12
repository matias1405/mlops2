"""Roles de Airflow a medida para separar responsabilidades (corre en airflow-init).

DataScientist = permisos de Viewer + crear DAG Runs. El permiso de editar (y por lo tanto disparar) un
DAG concreto lo da cada DAG con `access_control`; `airflow sync-perm --include-dags` lo aplica.
Resultado: ve todo pero solo dispara datos y entrenamiento; promote/validate_dev quedan para Admin.
"""
from airflow.www.app import cached_app

CUSTOM_ROLES = ("DataScientist",)

app = cached_app()
with app.app_context():
    sm = app.appbuilder.sm
    viewer = sm.find_role("Viewer")
    create_runs = sm.get_permission("can_create", "DAG Runs")
    for name in CUSTOM_ROLES:
        role = sm.find_role(name) or sm.add_role(name)
        for perm in list(viewer.permissions) + [create_runs]:
            if perm not in role.permissions:
                sm.add_permission_to_role(role, perm)
        print(f"rol {name}: {len(role.permissions)} permisos (Viewer + DAG Runs.can_create)")
