from pyspark.sql import SparkSession 
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, TimestampType
from pyspark.sql.functions import from_json, col, to_date, coalesce, lit
from dotenv import dotenv_values
import pathlib
import time

script_path = pathlib.Path(__file__).parent.resolve()
config = dotenv_values(f"{script_path.parent}/.env")

# Initialize SparkSession
spark = (SparkSession
        .builder
        .config("spark.ui.port", "4040")
        .appName("Kafka-Spark-Clickhouse")
        .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

df_read_stream = (spark
                .readStream
                .format("kafka")
                .option("kafka.bootstrap.servers", config["KAFKA_BOOTSTRAP_SERVERS"])
                .option("subscribe", config["KAFKA_TOPIC"])
                .option("startingOffsets", "earliest")
                .option("maxOffsetsPerTrigger", 1000)
                .load())

df = df_read_stream.withColumn("value", col("value").cast("string")).select("value")
json_schema = StructType([
    StructField("session_id", StringType(), True),
    StructField("event_id", StringType(), True),
    StructField("event_name", StringType(), True),
    StructField("event_time", TimestampType(), True),
    StructField("traffic_source", StringType(), True),
    StructField("add_to_cart_product_id", StringType(), True),
    StructField("add_to_cart_quantity", StringType(), True),
    StructField("add_to_cart_masterCategory", StringType(), True),
    StructField("add_to_cart_subCategory", StringType(), True),
    StructField("search_keywords", StringType(), True),
    StructField("booking_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("gender", StringType(), True),
    StructField("birthdate", StringType(), True),
    StructField("purchased_product_id", StringType(), True),
    StructField("purchased_quantity", StringType(), True),
    StructField("purchased_masterCategory", StringType(), True),
    StructField("purchased_subCategory", StringType(), True),
    StructField("item_price", FloatType(), True),
    StructField("payment_method", StringType(), True),
    StructField("payment_status", StringType(), True)
])

df_json_converted = df.withColumn("value", from_json(col("value"), schema=json_schema)).select("value.*")

df_json_converted = (df_json_converted
                    .withColumn("add_to_cart_product_id", col("add_to_cart_product_id").cast("int"))
                    .withColumn("customer_id", col("customer_id").cast("int"))
                    .withColumn("add_to_cart_quantity", col("add_to_cart_quantity").cast("int"))
                    .withColumn("purchased_product_id", col("purchased_product_id").cast("int"))
                    .withColumn("purchased_quantity", col("purchased_quantity").cast("int"))
                    .withColumn("birthdate", to_date(col("birthdate"), "yyyy-MM-dd"))
                    )

df_coalesce = (df_json_converted
                .withColumn("product_id", coalesce(col("add_to_cart_product_id"), col("purchased_product_id")))
                .withColumn("quantity", coalesce(col("add_to_cart_quantity"), col("purchased_quantity")))
                .withColumn("masterCategory", coalesce(col("add_to_cart_masterCategory"), col("purchased_masterCategory")))
                .withColumn("subCategory", coalesce(col("add_to_cart_subCategory"), col("purchased_subCategory")))
            )
df_coalesce = df_coalesce.select(
    "session_id", 
    "event_id",
    "event_name", 
    "event_time", 
    "traffic_source", 
    "search_keywords",
    "booking_id", 
    "customer_id", 
    "gender", 
    "birthdate", 
    "item_price", 
    "payment_method", 
    "payment_status", 
    'product_id',
    'quantity',
    'masterCategory',
    'subCategory'
    )

driver="com.clickhouse.jdbc.ClickHouseDriver"
username = config["CLICKHOUSE_USERNAME"]
password = config["CLICKHOUSE_PASSWORD"]
host = config["CLICKHOUSE_HOST"]
port = config["CLICKHOUSE_PORT"]
database = config["CLICKHOUSE_DATABASE"]

def write_to_clickhouse(batch_df, batch_id):    
    if batch_df.rdd.isEmpty():
        return
    # print("Number of partition:", batch_df.rdd.getNumPartitions())
    # .option("batchsize", "8192") \
    start = time.time()
    batch_df.withColumn("batch_id", lit(batch_id)).write \
        .format("jdbc") \
        .option("url", f"jdbc:clickhouse://{host}:{port}/{database}") \
        .option("dbtable", config["CLICKHOUSE_TABLE"]) \
        .option("user", username) \
        .option("password", password) \
        .option("driver", driver) \
        .mode("append") \
        .save()
    end = time.time()

    print(f"[Batch {batch_id}] Write time: {end - start:.2f} seconds")
    


query = df_coalesce.coalesce(1).writeStream \
    .foreachBatch(write_to_clickhouse) \
    .outputMode("append") \
    .option("checkpointLocation", "/checkpoints/checkpointLocation") \
    .trigger(processingTime="20 seconds")\
    .start()

query.awaitTermination()



# spark-submit --master spark://spark-master:7077 --deploy-mode client --jars /jars/clickhouse-jdbc-0.6.5.jar,/jars/commons-pool2-2.11.1.jar,/jars/kafka-clients-3.5.0.jar,/jars/spark-sql-kafka-0-10_2.12-3.5.0.jar,/jars/spark-token-provider-kafka-0-10_2.12-3.5.0.jar /job/spark_app.py

# docker compose stop spark-worker-1 spark-worker-2 spark-master broker01 broker02

# create table temp_dedup engine=MergeTree order by(event_name, event_time) as select distinct * from ecommerce_clickstream_data where batch_id=121;

# insert into ecommerce_clickstream_data select * from temp_dedup;

# git rm -r --cached path/to/yourfile
# git reset --soft HEAD~3 - Xóa 3 commit gần nhất và các thay đổi trong 3 commit đó được giữ trong staging area

# Stream
# query = (df_coalesce
#     .writeStream
#     .outputMode("append")
#     .format("console")
#     .start())

# query.awaitTermination()

# CREATE TABLE ecommerce_clickstream_data
# (
#     `session_id` String,
#     `event_id` String,
#     `event_name` String,
#     `event_time` DateTime,
#     `traffic_source` Nullable(String),
#     `search_keywords` Nullable(String),
#     `booking_id` Nullable(String),
#     `customer_id` Nullable(String),
#     `gender` Nullable(String),
#     `birthdate` Nullable(Date32),
#     `item_price` Nullable(Float32),
#     `payment_method` Nullable(String),
#     `payment_status` Nullable(String),
#     `product_id` Nullable(Int32),
#     `quantity` Nullable(Int32),
#     `masterCategory` Nullable(String),
#     `subCategory` Nullable(String),
#     `batch_id` Int32  
# )
# ENGINE = MergeTree
# ORDER BY (event_name, event_time);