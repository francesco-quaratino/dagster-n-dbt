import os
import json

from dagster import AssetExecutionContext, AssetKey
from dagster_dbt import dbt_assets, DbtCliClientResource, DagsterDbtTranslator

from .constants import DBT_DIRECTORY
from ..resources import dbt_resource
# from ..partitions import daily_partition
from ..partitions import monthly_partition


INCREMENTAL_SELECTOR = "config.materialized:incremental"

class CustomizedDagsterDbtTranslator(DagsterDbtTranslator):
    @classmethod
    def get_asset_key(cls, dbt_resource_props: dict) -> AssetKey:
        resource_type = dbt_resource_props["resource_type"]
        name = dbt_resource_props["name"]
        if resource_type == "source":
            return AssetKey(f"taxi_{name}")
        else:
            return super().get_asset_key(dbt_resource_props)
        
    @classmethod
    def get_group_name(cls, dbt_resource_props: dict) -> str:
        project = dbt_resource_props["fqn"][0]
        layer = dbt_resource_props["fqn"][1]
        model = dbt_resource_props["fqn"][2]
        if project == 'analytics':
            return layer
        else:
            # return dbt_resource_props.get("config", {}).get("group")
            return super().get_group_name(dbt_resource_props)

# dbt_manifest_path = os.path.join(DBT_DIRECTORY, "target", "manifest.json")
# dbt_manifest_path = (
#     dbt_resource.cli(["--quiet", "parse"]).wait().target_path.joinpath("manifest.json")
# )

dbt_resource.cli(["--quiet", "parse"]).wait()

if os.getenv("DAGSTER_DBT_PARSE_PROJECT_ON_LOAD"):
    dbt_manifest_path = (
        dbt_resource.cli(
            ["--quiet", "parse"]
        ).wait()
        .target_path.joinpath("manifest.json")
    )
else:
    dbt_manifest_path = os.path.join(DBT_DIRECTORY, "target", "manifest.json")


@dbt_assets(
    manifest=dbt_manifest_path,
    dagster_dbt_translator=CustomizedDagsterDbtTranslator(),
    exclude=INCREMENTAL_SELECTOR,
)
def dbt_analytics(context: AssetExecutionContext, dbt: DbtCliClientResource):
    yield from dbt.cli(
        ["build"], context=context
    ).stream()


@dbt_assets(
    manifest=dbt_manifest_path,
    dagster_dbt_translator=CustomizedDagsterDbtTranslator(),
    select=INCREMENTAL_SELECTOR,     # select only models with INCREMENTAL_SELECTOR
    # partitions_def=daily_partition   # partition those models using daily_partition
    partitions_def=monthly_partition,
)
def incremental_dbt_models(context: AssetExecutionContext, dbt: DbtCliClientResource):
    time_window = context.partition_time_window
    dbt_vars = {
        "min_date": time_window.start.isoformat(),
        "max_date": time_window.end.isoformat()
    }

    yield from dbt.cli(
        ["build", "--vars", json.dumps(dbt_vars)], context=context
    ).stream()
