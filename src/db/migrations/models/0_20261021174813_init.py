from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "queues" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "chat_id" BIGINT NOT NULL,
    "message_id" BIGINT,
    "created_by" BIGINT NOT NULL,
    "capacity" INT NOT NULL,
    "status" VARCHAR(16) NOT NULL,
    "active_key" BIGINT UNIQUE,
    "created_at" TIMESTAMPTZ NOT NULL,
    "closed_at" TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS "queue_slots" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "position" INT NOT NULL,
    "user_id" BIGINT,
    "user_name" VARCHAR(255),
    "username" VARCHAR(255),
    "reserved_at" TIMESTAMPTZ,
    "queue_id" BIGINT NOT NULL REFERENCES "queues" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_queue_slots_queue_i_b52f80" UNIQUE ("queue_id", "position"),
    CONSTRAINT "uid_queue_slots_queue_i_1fea3d" UNIQUE ("queue_id", "user_id")
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztmW1v2jAQgP8KyqdO6iYIr9s3oHRlXWEraJtaVZZJTLAINk2ctqjjv892EvJOG9ZWQP"
    "mW3Pns83N2fOc8KjOqI9P+9NNBDlK+FB4VAmfiIao4LihwPg/EQsDgyJQtb0UTKYIjm1lQ"
    "Y1w6hqaNuEhHtmbhOcOUcClxTFMIqcYbYmIEIodg3g9g1EBsgiyuuL7hYkx09MA7917nUz"
    "DGyNQjnmJdjC3lgC3mUtbCRpewU9lWDDgCGjWdGQnazxdsQsnKABMmpAYiyIIMiRGY5YgZ"
    "CAe9qfqTcp0Nmrhehmx0NIaOyUIzHoFApgDQ6w/BoDMEQMnBSKNE8OWu2hKAIVz4+FlVy+"
    "W6WizXGtVKvV5tFBu8rfQ3qaovXWcCWm5Xkln3a7c3FA5RHkQ3tkKwlDaQQddKBiOgr00g"
    "A3lDEDJ6Og4+9XWB8AVBJIIFuGehCG1RZNvQQLnpR+02CoC3zt83f81CghAYLXKu/ojdYQ"
    "NsHgA4hxpmKfiz2YdM9om8WqrUK41yrbICvpKs45xkajPIHDtJtD2BVjrSwCIGlLv5WkAV"
    "nmXgO6S8FtQZfAAmIgab8NdSbQ3BX83L9lnz8qhU+xBdrj1Po0pVFLLrPZiinF+OqN2LfL"
    "nfTQqT/G5DlqR/wjUMz9D6L7drGeOve6af/Idd/JrwCep9Yi68hbCG9bB70RkMmxc/xHAz"
    "2741Jb/msCM0qpQuYtKj+CZZdVL43R2eFcRr4arf60i81GaGJUcM2g2vFOETdBgFhN4DqI"
    "fWrC/1qUWjblJ7s6CHDV8g5luWO+1IiH0miRiLunA8DdUmQjCC2vQeWjqIaEKnnElZyiHX"
    "8sxOzy+RCSXJZMzDlfGA97OD23zpr3Ff6m93wY6qNItmUjVTZ3EJJLy40L2xxUgJYFn3DD"
    "7NJ+4awCp6L3vhcO127y1MLLvgMwqJHRtZomy6OdxNbM/Bnn03sYri8+uDsMmhPkhJnvwt"
    "kGtZh4wO1w2bpq0SonxJsM8uziJGG9Vn28Y+Upqp1eozajPeKrM4k7ok6E04HzDnwszzPm"
    "TdbZSSx0wPSfm2JeXhOLs5W94jI2y1TwfxGxwaiYooFotkIE6phbBBztFCBqPLHYdES/uY"
    "xX8L7lgQsgofLrbg/SqBj6w+Pns+Z8TcE6A5aDdPOsoyu8p8zRqqiSysTZSUAsrTHK+rnm"
    "DQZmv+1L6XUug/E/DsIucOWXZqjZOdrIRM3u7KfreTFbGpchD2mu8h3VKx+Jy/IcVi9u8Q"
    "oYvdyFPCEElJA78N+r2MW9nAJJ7+YY0V/hZMbO9imrAGroARSfp8pkcXzT9x3O3v/VY8mx"
    "MdtNIShLc8zJb/AInkg8E="
)
