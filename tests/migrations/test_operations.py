from snuba.clickhouse.columns import Column, Nullable, String, UInt
from snuba.clusters.storage_sets import StorageSetKey
from snuba.migrations.operations import (
    CreateMaterializedView,
    CreateTable,
    DropTable,
)
from snuba.migrations.table_engines import ReplacingMergeTree


def test_create_table() -> None:
    columns = [
        Column("id", String()),
        Column("name", Nullable(String())),
        Column("version", UInt(64)),
    ]

    assert (
        CreateTable(
            StorageSetKey.EVENTS,
            "test_table",
            columns,
            ReplacingMergeTree(
                version_column="version",
                order_by="version",
                settings={"index_granularity": "256"},
            ),
        ).format_sql()
        == "CREATE TABLE IF NOT EXISTS test_table (id String, name Nullable(String), version UInt64) ENGINE ReplacingMergeTree(version) ORDER BY version SETTINGS index_granularity=256;"
    )


def test_create_materialized_view() -> None:
    assert (
        CreateMaterializedView(
            StorageSetKey.EVENTS,
            "test_table_mv",
            "test_table_dest",
            [Column("id", String())],
            "SELECT id, count() as count FROM test_table_local GROUP BY id",
        ).format_sql()
        == "CREATE MATERIALIZED VIEW IF NOT EXISTS test_table_mv TO test_table_dest (id String) AS SELECT id, count() as count FROM test_table_local GROUP BY id;"
    )


def test_drop_table() -> None:
    assert (
        DropTable(StorageSetKey.EVENTS, "test_table").format_sql()
        == "DROP TABLE IF EXISTS test_table;"
    )
