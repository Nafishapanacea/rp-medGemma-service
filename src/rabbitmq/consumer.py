import pika
import json
import os
import time
from src.rabbitmq.connection import get_connection_and_channel, close_connection
from src.router.router import predict, InferencePayload

BACKEND_CALLBACK_URL = os.getenv("BACKEND_CALLBACK_URL", "http://192.168.1.103:8000/api/pub/medgemma-callback")
EXCHANGE_NAME = "study.exchange"
EXCHANGE_TYPE = "direct"
ROUTING_KEY = "study.new"
QUEUE_NAME = "medgemma.study.queue"

def process_message(ch, method, properties, body):
    try:
        payload = json.loads(body.decode("utf-8"))
        study_id = payload.get("studyId")
        if not study_id:
            print("[RabbitMQ Consumer] Received invalid message payload: missing 'studyId'. Acking to discard.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        print(f"[RabbitMQ Consumer] Received new studyId: '{study_id}'")
        
        # Assemble standard inference payload object
        payload_obj = InferencePayload(
            studyId=study_id,
            callbackUrl=BACKEND_CALLBACK_URL
        )
        
        # Directly invoke the existing prediction workflow in router.py
        response = predict(payload_obj)

        if response.status_code == 200:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[RabbitMQ Consumer] Successfully processed studyId: '{study_id}'. Response: {response.body.decode('utf-8')}")
        else:
            print(f"[RabbitMQ Consumer] Inference failed with status {response.status_code}: {response.body.decode('utf-8')}. Requeuing message...")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            time.sleep(2)

    except Exception as e:
        print(f"[RabbitMQ Consumer] Error during message processing: {str(e)}")
        # Negative acknowledge the message and requeue it so it can be retried
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        time.sleep(2)

def start_consumer():
    print(f"[RabbitMQ Consumer] Starting main consumer loop...")
    print(f"[RabbitMQ Consumer] Backend Callback URL: {BACKEND_CALLBACK_URL}")

    while True:
        try:
            connection, channel = get_connection_and_channel()

            # Declare durable exchange (durable direct exchange)
            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type=EXCHANGE_TYPE,
                durable=True
            )

            # Declare durable queue
            channel.queue_declare(queue=QUEUE_NAME, durable=True)

            # Bind queue to exchange using the routing key
            channel.queue_bind(
                queue=QUEUE_NAME,
                exchange=EXCHANGE_NAME,
                routing_key=ROUTING_KEY
            )

            # Restrict prefetch capacity to 1 so the consumer processes studies sequentially
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_message)

            print(f"[RabbitMQ Consumer] Successfully registered handlers. Listening on queue '{QUEUE_NAME}'...")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as err:
            print(f"[RabbitMQ Consumer] Broker connection was lost: {err}. Re-establishing connection in 5 seconds...")
            close_connection()
            time.sleep(5)
        except pika.exceptions.AMQPChannelError as err:
            print(f"[RabbitMQ Consumer] Channel error occurred: {err}. Re-opening connection/channel in 5 seconds...")
            close_connection()
            time.sleep(5)
        except Exception as err:
            print(f"[RabbitMQ Consumer] Unexpected consumer loop error: {err}. Restarting loop in 5 seconds...")
            close_connection()
            time.sleep(5)
