import pandas as pd
import json
import time
import os
from kafka import KafkaProducer

# === Configure ===
CSV_FILE = r".\final_clickstream\part-00000-3e8f5199-8215-4433-a82f-49399e5800ab-c000.csv"
TOPIC = "ecommerce_clickstream_data"
BOOTSTRAP_SERVERS = "localhost:9092"
OFFSET_FILE = "offset.txt"
BATCH_SIZE = 100
SLEEP_TIME = 2  # second

# === Initialize producer ===
producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
    key_serializer=lambda k: k.encode('utf-8'),   # If key is a string
    enable_idempotence=True,   # Turn on idempotence
    acks='all'
)

# === Read present offset ===
def read_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    return 0

# === Write new offset ===
def write_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

# === Convert rows to JSON (remove null value) ===
def row_to_json(row):
    return row.dropna().to_dict()

# === Main ===
def stream_to_kafka():
    df = pd.read_csv(CSV_FILE)
    total_rows = len(df)

    offset = read_offset()
    print(f"Bắt đầu từ dòng thứ: {offset}")

    while offset < total_rows:
        batch = df.iloc[offset : offset + BATCH_SIZE]

        for _, row in batch.iterrows():
            json_data = row_to_json(row)
            event_name = json_data["event_name"]
            # print(json_data, type(json_data))
            producer.send(TOPIC, key=event_name, value=json_data)
            # print(json_data)
        offset += BATCH_SIZE
        write_offset(offset)
        producer.flush()
        print(f"Đã gửi đến dòng thứ: {offset}")
        
        time.sleep(SLEEP_TIME)
        # break

    print("🎉 Đã gửi hết toàn bộ dữ liệu.")

if __name__ == "__main__":
    stream_to_kafka()

# kafka-run-class kafka.tools.GetOffsetShell --broker-list broker01:9092 --topic ecommerce_clickstream_data --time -1