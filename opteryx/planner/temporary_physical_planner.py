# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This is a temporary step, which takes logical plans from the V2 planner
and converts them to modified-V1 physical plans.

This should look different when the operators are rewritten for the
Gen 2 execution engine (a later piece of work)
"""

from orso.schema import OrsoTypes

from opteryx import operators
from opteryx.exceptions import UnsupportedSyntaxError
from opteryx.models import ExecutionTree
from opteryx.planner.logical_planner import LogicalPlanStepType


def create_physical_plan(logical_plan, query_properties) -> ExecutionTree:
    plan = ExecutionTree()

    for nid, logical_node in logical_plan.nodes(data=True):
        node_type = logical_node.node_type
        node_config = logical_node.properties
        node: operators.BasePlanNode = None

        # fmt: off
        if node_type == LogicalPlanStepType.Aggregate:
            node = operators.AggregateNode(query_properties, aggregates=node_config["aggregates"])
        elif node_type == LogicalPlanStepType.AggregateAndGroup:
            node = operators.AggregateAndGroupNode(query_properties, groups=node_config["groups"], aggregates=node_config["aggregates"], projection=node_config["projection"])
        #        elif node_type == LogicalPlanStepType.Defragment:
        #            node = operators.MorselDefragmentNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.Distinct:
            node = operators.DistinctNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.Exit:
            node = operators.ExitNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.Explain:
            node = operators.ExplainNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.Filter:
            node = operators.FilterNode(query_properties, filter=node_config["condition"])
        elif node_type == LogicalPlanStepType.FunctionDataset:
            node = operators.FunctionDatasetNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.HeapSort:
            node = operators.HeapSortNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.Join:
            if node_config.get("type") == "inner":
                # We use our own implementation of INNER JOIN
                # We have optimized INTEGER and VARCHAR versions
                if len(node_config["left_columns"]) == 1 and node_config["columns"][0].schema_column.type in {OrsoTypes.INTEGER, OrsoTypes.VARCHAR}:
                    node = operators.InnerJoinSingleNode(query_properties, **node_config)
                else:
                    node = operators.InnerJoinNode(query_properties, **node_config)
            elif node_config.get("type") in ("left outer", "full outer", "right outer", "left anti", "left semi"):
                # We use out own implementation of OUTER JOINS
                node = operators.OuterJoinNode(query_properties, **node_config)
            elif node_config.get("type") == "cross join":
                # Pyarrow doesn't have a CROSS JOIN
                node = operators.CrossJoinNode(query_properties, **node_config)
            else:
                # Use Pyarrow for all other joins
                node = operators.JoinNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.Limit:
            node = operators.LimitNode(query_properties, limit=node_config.get("limit"), offset=node_config.get("offset", 0))
        elif node_type == LogicalPlanStepType.Order:
            node = operators.SortNode(query_properties, order=node_config["order_by"])
        elif node_type == LogicalPlanStepType.Project:
            node = operators.ProjectionNode(query_properties, projection=logical_node.columns)
        elif node_type == LogicalPlanStepType.Scan:
            connector = node_config.get("connector")
            if connector and hasattr(connector, "async_read_blob"):
                node = operators.AsyncReaderNode(query_properties, **node_config)
            else:
                node = operators.ReaderNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.Set:
            node = operators.SetVariableNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.Show:
            if node_config["object_type"] == "VARIABLE":
                node = operators.ShowValueNode(query_properties, kind=node_config["items"][1], value=node_config["items"][1])
            elif node_config["object_type"] == "VIEW":
                node = operators.ShowCreateNode(query_properties, **node_config)
            else:
                raise UnsupportedSyntaxError(f"Unsupported SHOW type '{node_config['object_type']}'")
        elif node_type == LogicalPlanStepType.ShowColumns:
            node = operators.ShowColumnsNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.Subquery:
            node = operators.NoOpNode(query_properties, **node_config)
        elif node_type == LogicalPlanStepType.Union:
            node = operators.UnionNode(query_properties, **node_config)
        else:  # pragma: no cover
            raise Exception(f"something unexpected happed - {node_type.name}")
        # fmt: on

        # DEBUG: from opteryx.exceptions import InvalidInternalStateError
        # DEBUG:
        # DEBUG: try:
        # DEBUG:    config = node.to_json()
        ## DEBUG:    print(config)
        # DEBUG: except Exception as err:
        # DEBUG:    message = f"Internal Error - node '{node}' unable to be serialized"
        # DEBUG:    print(message)
        ## DEBUG:    raise InvalidInternalStateError(message)

        plan.add_node(nid, node)

    for source, destination, relation in logical_plan.edges():
        plan.add_edge(source, destination, relation)

    return plan
