from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Type


class _QueryRegistry:
    """Keep a mapping of SystemQueries to their names"""

    def __init__(self) -> None:
        self.__mapping: Dict[str, Type["SystemQuery"]] = {}

    def register_class(self, cls: Type["SystemQuery"]) -> None:
        existing_class = self.__mapping.get(cls.__name__)
        if not existing_class:
            self.__mapping[cls.__name__] = cls

    def get_class_by_name(self, cls_name: str) -> Optional[Type["SystemQuery"]]:
        return self.__mapping.get(cls_name)

    @property
    def all_queries(self) -> Sequence[Type["SystemQuery"]]:
        return list(self.__mapping.values())


_QUERY_REGISTRY = _QueryRegistry()


@dataclass
class SystemQuery:
    sql: str

    @classmethod
    def to_json(cls) -> Dict[str, Optional[str]]:
        return {
            "sql": cls.sql,
            "description": cls.__doc__,
            "name": cls.__name__,
        }

    def __init_subclass__(cls) -> None:
        _QUERY_REGISTRY.register_class(cls)
        return super().__init_subclass__()

    @classmethod
    def from_name(cls, name: str) -> Optional[Type["SystemQuery"]]:
        return _QUERY_REGISTRY.get_class_by_name(name)

    @classmethod
    def all_queries(cls) -> Sequence[Type["SystemQuery"]]:
        return _QUERY_REGISTRY.all_queries


class CurrentMerges(SystemQuery):
    """Currently executing merges"""

    sql = """
    SELECT
        count(),
        is_currently_executing
    FROM system.replication_queue
    GROUP BY is_currently_executing
    """


class ActivePartitions(SystemQuery):
    """Currently active parts"""

    sql = """
    SELECT
        active,
        count()
    FROM system.parts
    GROUP BY active
    """


class PartsPerTable(SystemQuery):
    """Number of parts grouped by table. Parts should not be in the high thousands."""

    sql = """
    SELECT
        count(),
        table
    FROM system.parts
    GROUP BY table
    ORDER BY count()
    """


class PartitionSizeByTable(SystemQuery):
    """Sum of the size of parts within a partition on a given table."""

    sql = """
    SELECT
        partition,
        table,
        count(),
        formatReadableSize(sum(bytes_on_disk) as bytes) as size
    FROM system.parts
    WHERE active = 1
    GROUP BY partition, table
    ORDER BY partition ASC
    """


class PartSizeWithinPartition(SystemQuery):
    """Gets the size of parts within a specific partition. You'll need to input
    <strong><code>partition = '(90,"2022-01-24")'</code></strong> with the partition you want.

    To get partitions you can use <strong><code>SELECT partition FROM system.parts</code></strong>
    """

    sql = """
    SELECT name, formatReadableSize(bytes_on_disk) as size
    FROM system.parts
    WHERE
        partition = '(90,"2022-01-24")'  AND
        active = 1 AND
        bytes_on_disk > 1000000
    ORDER BY bytes_on_disk DESC
    """
