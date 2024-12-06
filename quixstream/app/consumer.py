from quixstreams import Application
import redis
import json
import requests

redis_client = redis.StrictRedis(
    host='redis-ct', 
    port=6379,         
    decode_responses=True    
)
try:
    redis_client.ping()
    print("Kết nối thành công đến Redis!")
except redis.ConnectionError:
    print("Không thể kết nối đến Redis.")

def storeSession(value):
    print("Tui dang o hadaydyyyyyyyyyyyyyyyyyy")
    if value:
        if value['sid'] is None:
            return
        redis_client.rpush(value['sid'], json.dumps(value))
        count = redis_client.llen(value['sid'])
        # if count % 5 == 0: 
        print("i am here")
        inp = [[json.loads(m)['sid'],json.loads(m)['uid'], json.loads(m)['bid'], json.loads(m)['reward']] for m in redis_client.lrange(value['sid'], -5, -1)]
        try:
            requests.post("http://fast-api:88/predict/", json=inp)
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
                    
def storeAll(value):
    if value:
        redis_client.rpush("ui_history", json.dumps(value))

app = Application(
    broker_address="kafka-ct:9092",
    consumer_group="quix",
    auto_offset_reset="latest",
)

messages_topic = app.topic(name="UserInteraction", value_deserializer="json")

sdf = app.dataframe(topic=messages_topic)

sdf = sdf.update(storeAll)

a2r = {
    "skip" : -1,
    "click" : 1,
    "read" : 2
}

sdf["reward"] = sdf["action"].apply(lambda act: a2r[act])
sdf = sdf.update(print).update(storeSession)


# Run the streaming application
if __name__ == "__main__":
    app.run()