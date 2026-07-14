"""
Stand-in for the Apache Kafka async pipeline described in the architecture
brief. A real deployment publishes the masked payload to a topic, a
consumer group picks it up, calls the external LLM, and publishes the
response to a reply topic. For this single-process demo, an in-memory
queue with the same producer/consumer shape reproduces the interface
without needing a Kafka broker.
"""
import queue
from typing import Callable

_request_queue: "queue.Queue" = queue.Queue()


def enqueue_and_process(payload: str, handler: Callable[[str], str]) -> str:
    """Simulates: producer publishes `payload` to Kafka -> consumer picks it
    up -> calls `handler` (the external LLM call) -> returns the result as
    if it were published back to a reply topic and consumed synchronously."""
    _request_queue.put(payload)
    item = _request_queue.get()
    result = handler(item)
    _request_queue.task_done()
    return result
