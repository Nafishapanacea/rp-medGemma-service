import pika
import os

_connection = None
_channel = None

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@192.168.1.103:5672/")

def get_connection_and_channel():
    """
    Returns the active connection and channel.
    Connects to RabbitMQ dynamically if they are closed or uninitialized.
    """
    global _connection, _channel
    
    # Check if active connection and channel are open
    if _connection and _connection.is_open and _channel and _channel.is_open:
        return _connection, _channel
        
    print(f"[RabbitMQ Connection] Connecting to broker at: {RABBITMQ_URL}")
    params = pika.URLParameters(RABBITMQ_URL)
    _connection = pika.BlockingConnection(params)
    _channel = _connection.channel()
    
    print("[RabbitMQ Connection] Connection and channel successfully initialized.")
    return _connection, _channel

def close_connection():
    """
    Safely closes the connection and channel if they exist.
    """
    global _connection, _channel
    print("[RabbitMQ Connection] Safely shutting down active connection and channel...")
    try:
        if _channel and _channel.is_open:
            _channel.close()
    except Exception as e:
        print(f"[RabbitMQ Connection] Error closing channel: {e}")
    try:
        if _connection and _connection.is_open:
            _connection.close()
    except Exception as e:
        print(f"[RabbitMQ Connection] Error closing connection: {e}")
    _connection = None
    _channel = None
