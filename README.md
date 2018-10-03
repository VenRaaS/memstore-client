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
  
`redis-cli -h ${HOST} -p 6379`

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
  * [KEYS pattern](https://redis.io/commands/keys) 
    * **notice that** you should always consider ```scan``` instead of ```keys``` to prevent block redis server.
  * [DEL key [key ...]](https://redis.io/commands/del)
    * `redis-cli -h ${HOST} --scan --pattern '*_mod*' | xargs redis-cli  -h ${HOST} del` del keys with specific pattern
  * [FLUSHALL](https://redis.io/commands/flushall)
  
* [Lists](https://redis.io/topics/data-types#lists) - [Redis lists are implemented via Linked Lists](https://redis.io/topics/data-types-intro#redis-lists)
  * [LPUSH key value [value ...]](https://redis.io/commands/lpush)
  * [RPUSH key value [value ...]](https://redis.io/commands/rpush)
  * [LRANGE key start stop](https://redis.io/commands/lrange)
  * [LTRIM key start stop](https://redis.io/commands/ltrim)

## Key and value schema for data access in Venraas
* `${code_name}_mod.${table_name}.${id_name}.${id}` => "id:score, ... "
* `${code_name}_opp.${table_name}.${id_name}.${id}` => [json_action(t), json_action(t-1), ... ]
* `${code_name}_oua.${table_name}.${id_name}.${id}` => [json, ... ]
* `${code_name}_gocc.${table_name}.${id_name}.${id}` => "json"

where `${id_name}` stands for id field name, e.g.gid, category_code, ..., and `${id}` is the value.

## Reference
* [Cloud Memorystore](https://cloud.google.com/memorystore/)
  * [Google’s Cloud Memorystore for Redis is now GA](https://techcrunch.com/2018/09/19/googles-cloud-memorystore-for-redis-is-now-generally-available/)
* [Connecting to a Redis Instance from a Compute Engine VM](https://cloud.google.com/memorystore/docs/redis/connect-redis-instance-gce)

