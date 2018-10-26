## Overview
![](https://drive.google.com/uc?id=1DsmJmeIIVFPmYGvf9rZ6f8xgNY1MitwI)

## Why we need [memorystore](https://cloud.google.com/memorystore/)
### Latency vs. Throughput with data tiers
![](https://drive.google.com/uc?id=1OcIYJ02gqUM2AGCT3mgAGrL63DO0jc-d)

### Relieving the bottleneck 
![](https://drive.google.com/uc?id=1zXixdFf2LS-YQEIK_6KkftpSVUBaaOyJ)

## Client

### [netcat](https://en.wikipedia.org/wiki/Netcat)
`nc -v ${HOST} ${PORT}`

### [redis-cli](https://redis.io/topics/rediscli)
* installation under Ubuntu  
  `apt-get install redis-tools`
* connect to redis  
  `redis-cli -h ${HOST} -p 6379`

### [jedis](https://github.com/xetorthio/jedis/wiki)

### [redis-py](https://github.com/andymccurdy/redis-py)

## Data type and commands
* [Strings](https://redis.io/topics/data-types#strings) - Redis Strings are binary safe.
  * [SET key value](https://redis.io/commands/set)
  * [GET key](https://redis.io/commands/get)
  * [APPEND key value](https://redis.io/commands/append)
  
* [Redis keys](https://redis.io/topics/data-types-intro#redis-keys)
  * [EXPIRE key seconds](https://redis.io/commands/expire)
  * [TTL key](https://redis.io/commands/ttl)
  * [SCAN cursor [MATCH pattern] [COUNT count]](https://redis.io/commands/scan)
    * [list of keys](https://redis.io/topics/rediscli#getting-a-list-of-keys)  
      `redis-cli -h $HOST --scan --pattern '*-11*'`
  * [KEYS pattern](https://redis.io/commands/keys) 
    * **notice that** you should always consider ```scan``` instead of ```keys``` to prevent block redis server.
  * [DEL key [key ...]](https://redis.io/commands/del)
    * del keys by specific pattern  
      `redis-cli -h ${HOST} --scan --pattern '*_mod*' | xargs redis-cli  -h ${HOST} del` 
  * [FLUSHALL](https://redis.io/commands/flushall)
  
* [Lists](https://redis.io/topics/data-types#lists) - [Redis lists are implemented via Linked Lists](https://redis.io/topics/data-types-intro#redis-lists)
  * [LPUSH key value [value ...]](https://redis.io/commands/lpush)
  * [RPUSH key value [value ...]](https://redis.io/commands/rpush)
  * [LRANGE key start stop](https://redis.io/commands/lrange)
  * [LTRIM key start stop](https://redis.io/commands/ltrim)

## Key and value schema for data access in VenRaas
* `/${code_name}_gocc/${table_name}/_search?q=${id_key}:${id}` => [json]

* `/${code_name}_mod/${table_name}/_search?q=${id_key}:${id}` => [json]
* `/${code_name}_mod/goods_category_flatten/_search?q=gid:${gid}` => [json, json, ...]
  * `ZRANGE ${key} 0 -1`
* `/${code_name}_mod/breadcrumb/_search?q=gid:${gid}` => [json, json, ...]
  * `ZRANGE ${key} 0 -1`
  
* `/${code_name}_opp/OnlinePref/_search_last_gop_ops?q=ven_guid:${ven_guid}` => [json_action(t), json_action(t-1), ... ]
* `/${code_name}_opp/OnlinePref/_search_last_checkout_gids?q=ven_guid:${ven_guid}` => [{"trans_i": {"ilist": [{"id": "xxx"}], "id": "ooo"}}, ...]  

* `/${code_name}_oua/OnlineUserAlign/_search_last_login_uid?q=ven_guid:${ven_guid}` => [{"uid": "201008168544"}, ...]
* `/${code_name}_oua/OnlineUserAlign/_search_last_ven_guids?q=uid:${uid}` => [{"ven_guid": "202004242347055333a8c010adf2cc"}, ...]
  * `ZREVRANGE ${key} 0 -1` gets ven_guids by the latest first order

where `${id_name}` stands for id field name, e.g.gid, category_code, ..., and `${id}` is the value.

## Reference
* [Cloud Memorystore](https://cloud.google.com/memorystore/)
  * [Google’s Cloud Memorystore for Redis is now GA](https://techcrunch.com/2018/09/19/googles-cloud-memorystore-for-redis-is-now-generally-available/)
* [Connecting to a Redis Instance from a Compute Engine VM](https://cloud.google.com/memorystore/docs/redis/connect-redis-instance-gce)
* [An introduction to Redis data types and abstractions](https://redis.io/topics/data-types-intro)
* [Redis: under the hood](https://pauladamsmith.com/articles/redis-under-the-hood.html)


