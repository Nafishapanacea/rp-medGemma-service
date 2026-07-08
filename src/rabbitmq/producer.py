import pika
import json
import os
from src.rabbitmq.connection import get_connection_and_channel

EXCHANGE_NAME = "study.aiexchangeresponse"
EXCHANGE_TYPE = "direct"
ROUTING_KEY = "study.result"

def publish_result(study_id: str, result: dict) -> None:
    """
    Publishes the AI inference results back to RabbitMQ.
    """
    connection, channel = get_connection_and_channel()

    # Assert exchange to ensure it exists (idempotent call)
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type=EXCHANGE_TYPE,
        durable=True
    )

    message = {
        "studyId": study_id,
        "result": result
    }
    payload = json.dumps(message)

    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key=ROUTING_KEY,
        body=payload,
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
            content_type="application/json"
        )
    )

    print(f"[RabbitMQ Producer] Successfully published study results. Exchange: '{EXCHANGE_NAME}', Routing Key: '{ROUTING_KEY}', studyId: '{study_id}'")
