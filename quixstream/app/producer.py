import random
import time
from quixstreams import Application

# Create an Application - the main configuration entry point
app = Application(broker_address="kafka-ct:9092", consumer_group="quix")

# Define a topic with chat messages in JSON format
sessions_topic = app.topic(name="UserInteraction", value_serializer="json")

# action mapping: click = 1, read = 2, skip = -1
action_rewards = {"click": 1, "read": 2, "skip": -1}

# Function to generate a random message
def generate_random_message():
    message = {
        "sid": f"s{random.randint(1, 2)}",  # Random session ID
        "uid": random.randint(1, 100),        # Random user ID
        "bid": random.randint(1, 1000),       # Random book ID
        "action": random.choice(["click", "read", "skip"]),  # Random action
        "timestamp": int(time.time()),   # Current timestamp
    }
    return message

def main():
    with app.get_producer() as producer:
        while True:
            # Generate a random message
            message = generate_random_message()
            
            # Serialize and produce the message
            kafka_msg = sessions_topic.serialize(key=message["sid"], value=message)
            print(f'Produce event with key="{kafka_msg.key}" value="{kafka_msg.value}"')
            
            producer.produce(
                topic=sessions_topic.name,
                key=kafka_msg.key,
                value=kafka_msg.value,
            )
            
            # Wait for a random interval between 0.5 and 2 seconds
            time.sleep(0.5)

if __name__ == "__main__":
    main()
