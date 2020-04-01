import collections
import logging
from typing import Optional, Sequence

import simplejson as json
from confluent_kafka import Producer as ConfluentKafkaProducer

from snuba.datasets.dataset import Dataset
from snuba.datasets.factory import enforce_table_writer
from snuba.processor import ProcessedMessage, ProcessorAction
from snuba.utils.metrics.backends.abstract import MetricsBackend
from snuba.utils.streams.batching import AbstractBatchWorker
from snuba.utils.streams.kafka import KafkaPayload
from snuba.utils.streams.types import Message, Topic

logger = logging.getLogger("snuba.consumer")

# TODO: Remove this abstraction entirely and rely on StreamMessageParser subclasses
# to deal with the Kafka specific fields that are needed when consuming a message.
KafkaMessageMetadata = collections.namedtuple(
    "KafkaMessageMetadata", "offset partition"
)


class InvalidActionType(Exception):
    pass


class ConsumerWorker(AbstractBatchWorker[KafkaPayload, ProcessedMessage]):
    def __init__(
        self,
        dataset: Dataset,
        metrics: MetricsBackend,
        producer: Optional[ConfluentKafkaProducer] = None,
        replacements_topic: Optional[Topic] = None,
        rapidjson_deserialize: bool = False,
        rapidjson_serialize: bool = False,
    ) -> None:
        self.__dataset = dataset
        self.producer = producer
        self.replacements_topic = replacements_topic
        self.metrics = metrics
        self.__writer = enforce_table_writer(dataset).get_writer(
            {"load_balancing": "in_order", "insert_distributed_sync": 1},
            rapidjson_serialize=rapidjson_serialize,
        )
        self.__rapidjson_deserialize = rapidjson_deserialize

    def process_message(
        self, message: Message[KafkaPayload]
    ) -> Optional[ProcessedMessage]:
        metadata = KafkaMessageMetadata(
            offset=message.offset, partition=message.partition.index
        )
        processed = self._process_message_impl(message, metadata)
        if processed is None:
            return None

        if processed.action not in set(
            [ProcessorAction.INSERT, ProcessorAction.REPLACE]
        ):
            raise InvalidActionType("Invalid action type: {}".format(processed.action))

        return processed

    def _process_message_impl(
        self, value: Message[KafkaPayload], metadata: KafkaMessageMetadata,
    ) -> Optional[ProcessedMessage]:
        stream_loader = enforce_table_writer(self.__dataset).get_stream_loader()
        parsed_message = stream_loader.get_parser().parse_message(value)
        if parsed_message is None:
            return None
        return stream_loader.get_processor().process_message(parsed_message, metadata)

    def delivery_callback(self, error, message):
        if error is not None:
            # errors are KafkaError objects and inherit from BaseException
            raise error

    def flush_batch(self, batch: Sequence[ProcessedMessage]):
        """First write out all new INSERTs as a single batch, then reproduce any
        event replacements such as deletions, merges and unmerges."""
        inserts = []
        replacements = []

        for message in batch:
            if message.action == ProcessorAction.INSERT:
                inserts.extend(message.data)
            elif message.action == ProcessorAction.REPLACE:
                replacements.extend(message.data)

        if inserts:
            self.__writer.write(inserts)

            self.metrics.timing("inserts", len(inserts))

        if replacements:
            for key, replacement in replacements:
                self.producer.produce(
                    self.replacements_topic.name,
                    key=str(key).encode("utf-8"),
                    value=json.dumps(replacement).encode("utf-8"),
                    on_delivery=self.delivery_callback,
                )

            self.producer.flush()
