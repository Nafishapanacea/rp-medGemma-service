import pika
import json
import os
import time
from datetime import datetime, timezone
from src.rabbitmq.connection import get_connection_and_channel, close_connection
from src.rabbitmq.producer import publish_result
from src.router.router import predict, InferencePayload
from src.configuration.config import DICOM_TEMP_PATH

EXCHANGE_NAME = "study.aiexchange"
EXCHANGE_TYPE = "direct"
ROUTING_KEY = "study.new"
QUEUE_NAME = "medgemma.study.queue"
DLQ_NAME = "medgemma.study.dead.queue"

def handle_failure(ch, method, payload: dict, study_id: str, retry_count: int, error_message: str) -> None:
    """
    Handles a processing failure:
    - If retry_count < 3, increments retryCount and republishes to the study queue.
    - If retry_count >= 3, publishes a detailed payload to the DLQ.
    In both cases, ACKs the original message.
    """
    try:
        if retry_count < 3:
            next_retry = retry_count + 1
            print(f"[RabbitMQ Consumer] Attempt failed for studyId '{study_id}'. Retry count: {retry_count} (< 3). Incrementing to {next_retry} and republishing. Reason: {error_message}")
            
            payload["retryCount"] = next_retry
            
            # Republish the message. Prefer the exchange/routing key from the incoming message, or default to constants
            exchange = method.exchange if method.exchange else EXCHANGE_NAME
            routing_key = method.routing_key if method.routing_key else ROUTING_KEY
            
            ch.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(payload),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # keep the message durable
                    content_type="application/json"
                )
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[RabbitMQ Consumer] Republish complete. Original message ACKed.")
        else:
            print(f"[RabbitMQ Consumer] Attempt failed for studyId '{study_id}'. Retry count: {retry_count} (>= 3). Moving to DLQ. Reason: {error_message}")
            
            dlq_payload = {
                "studyId": study_id,
                "retryCount": retry_count,
                "errorMessage": error_message,
                "failureTimestamp": datetime.now(timezone.utc).isoformat()
            }
            # Merge remaining keys from original payload
            for k, v in payload.items():
                if k not in dlq_payload:
                    dlq_payload[k] = v
                    
            # Publish to medgemma.study.dead.queue via the default exchange ""
            ch.basic_publish(
                exchange="",
                routing_key=DLQ_NAME,
                body=json.dumps(dlq_payload),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # keep the message durable
                    content_type="application/json"
                )
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[RabbitMQ Consumer] DLQ publish complete. Original message ACKed.")
            
    except Exception as err:
        print(f"[RabbitMQ Consumer] Critical error in handle_failure: {err}. Falling back to standard basic_nack.")
        try:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except Exception as nack_err:
            print(f"[RabbitMQ Consumer] Critical: failed to perform fallback nack: {nack_err}")

def process_message(ch, method, properties, body):
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as json_err:
        print(f"[RabbitMQ Consumer] Received malformed JSON payload. Discarding (ACK). Error: {json_err}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    study_id = payload.get("studyId")
    if not study_id:
        print("[RabbitMQ Consumer] Received invalid message payload: missing 'studyId'. Discarding (ACK).")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    retry_count = payload.get("retryCount", 0)
    print(f"[RabbitMQ Consumer] Received studyId: '{study_id}', retryCount: {retry_count}")
    
    try:
        # Assemble standard inference payload object
        # Note: Set callbackUrl=None so it doesn't trigger the REST webhook delivery
        payload_obj = InferencePayload(
            studyId=study_id,
            callbackUrl=None
        )
        
        # Directly invoke the existing prediction workflow in router.py
        response = predict(payload_obj)

        if response.status_code == 200:
            # Parse response to get the file_id
            res_data = json.loads(response.body.decode("utf-8"))
            file_id = res_data.get("file_id")
            
            if not file_id:
                raise ValueError("Prediction response did not return a valid file_id")

            # Load the predictions file written by router.py
            predictions_path = os.path.join(DICOM_TEMP_PATH, file_id, "predictions.json")
            if not os.path.exists(predictions_path):
                raise FileNotFoundError(f"Predictions file not found at path: {predictions_path}")
                
            with open(predictions_path, "r", encoding="utf-8") as f:
                predictions = json.load(f)

            # Cleanup the temp files and directories
            try:
                os.remove(predictions_path)
                dir_path = os.path.join(DICOM_TEMP_PATH, file_id)
                if os.path.exists(dir_path) and not os.listdir(dir_path):
                    os.rmdir(dir_path)
            except Exception as cleanup_err:
                print(f"[RabbitMQ Consumer] Temp prediction folder cleanup error: {cleanup_err}")

            # Publish the parsed predictions to RabbitMQ
            publish_result(study_id, predictions)

            # Successfully processed, ACK the current message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[RabbitMQ Consumer] Successfully processed and published results for studyId: '{study_id}'")
        else:
            # Prediction failed (e.g., HTTP 503 Study not found or PACS unauthorized)
            error_msg = response.body.decode('utf-8')
            reason = f"Non-200 response status: {response.status_code} ({error_msg})"
            handle_failure(ch, method, payload, study_id, retry_count, reason)

    except Exception as e:
        # Unexpected exceptions during message processing (e.g. JSON parsing error, file errors)
        reason = f"Unexpected processing error: {str(e)}"
        handle_failure(ch, method, payload, study_id, retry_count, reason)

def start_consumer():
    print(f"[RabbitMQ Consumer] Starting main consumer loop...")

    while True:
        try:
            connection, channel = get_connection_and_channel()

            # Declare durable exchange (durable direct exchange)
            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type=EXCHANGE_TYPE,
                durable=True
            )

            # Declare durable queues
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.queue_declare(queue=DLQ_NAME, durable=True)

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
